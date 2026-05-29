"""
API Gateway + Load Balancer — porta 8000
================================================
Ponto único de entrada do sistema. Todas as requisições
do frontend passam por aqui.

Funções:
  - Roteia /users/*    → user-service  (8001 ou 8011)
  - Roteia /events/*   → event-service (8002 ou 8012)
  - Roteia /purchases/*→ purchase-service (8003 ou 8013)
  - Load Balancer round-robin entre as instâncias de cada serviço
  - Logs de todas as requisições (observabilidade)
  - Health check de todos os serviços
  - Tracing distribuído via X-Request-ID propagado a todos os serviços
  - Validação de JWT e repasse de X-User-* para serviços internos

Para rodar: python main.py
"""
import time
import uuid
import logging
import itertools
import httpx
import uvicorn
import os
import jwt

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

JWT_SECRET    = os.environ.get("JWT_SECRET", "ticketflow-secret-dev-2026")
JWT_ALGORITHM = "HS256"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [api-gateway] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Instâncias de cada serviço (Load Balancer) ────────────────
SERVICE_INSTANCES = {
    "users":     ["http://localhost:8001", "http://localhost:8011"],
    "events":    ["http://localhost:8002", "http://localhost:8012"],
    "purchases": ["http://localhost:8003", "http://localhost:8013"],
}
_counters = {k: 0 for k in SERVICE_INSTANCES}


def get_next_instance(service: str) -> str:
    """Round-robin: alterna entre as instâncias disponíveis."""
    instances = SERVICE_INSTANCES[service]
    idx = _counters[service] % len(instances)
    _counters[service] += 1
    return instances[idx]


# ── Rotas que exigem autenticação e/ou role admin ─────────────
# Formato: (method, prefixo_path, role_exigida)
#   role_exigida = "admin" → apenas admins
#   role_exigida = "user"  → qualquer usuário logado
#   role_exigida = None    → rota pública
ROUTE_RULES = [
    # Eventos — leitura é pública; escrita exige admin
    ("POST",   "/events",  "admin"),
    ("PUT",    "/events",  "admin"),
    ("DELETE", "/events",  "admin"),
    # Compras — exige usuário logado
    ("POST",   "/purchases", "user"),
    ("GET",    "/purchases", "user"),
]


def get_required_role(method: str, path: str):
    """Retorna a role exigida para a combinação método+path, ou None se pública."""
    for rule_method, rule_prefix, role in ROUTE_RULES:
        if method == rule_method and path.startswith(rule_prefix):
            return role
    return None


def extrair_usuario_do_token(authorization: str | None) -> dict | None:
    """Decodifica o JWT sem lançar exceção — retorna None se inválido."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ", 1)[1]
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


async def proxy(request: Request, service: str, path: str):
    """Encaminha a requisição para o serviço correto."""
    # ── TRACING: gera ou repassa X-Request-ID ────────────────
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

    # ── AUTENTICAÇÃO / AUTORIZAÇÃO ───────────────────────────
    full_path  = f"/{path}" if path else f"/{service}"
    route_path = f"/{service}{('/' + path) if path else ''}"
    required_role = get_required_role(request.method, f"/{service}")

    auth_header = request.headers.get("authorization")
    user_payload = extrair_usuario_do_token(auth_header)

    if required_role:
        if not user_payload:
            raise HTTPException(401, "Autenticação necessária. Faça login e use o token retornado.")
        if required_role == "admin" and user_payload.get("role") != "admin":
            raise HTTPException(403, "Acesso negado. Apenas administradores podem executar esta ação.")

    # ── PROXY ────────────────────────────────────────────────
    target = get_next_instance(service)
    url    = f"{target}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    logger.info(
        f"[LB] {request.method} /{service}/{path} → {target} "
        f"| request_id={request_id} "
        f"| user={user_payload.get('sub', 'anon') if user_payload else 'anon'}"
    )

    body = await request.body()

    # Headers repassados para o serviço interno
    internal_headers = {
        "Content-Type":   "application/json",
        "X-Request-ID":   request_id,
    }
    if user_payload:
        internal_headers["X-User-ID"]   = str(user_payload.get("sub", ""))
        internal_headers["X-User-Role"] = user_payload.get("role", "user")
        internal_headers["X-User-Name"] = user_payload.get("name", "")

    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.request(
                    method  = request.method,
                    url     = url,
                    headers = internal_headers,
                    content = body,
                )
            response = JSONResponse(
                status_code = resp.status_code,
                content     = resp.json()
            )
            # Propaga o X-Request-ID na resposta para o cliente rastrear
            response.headers["X-Request-ID"] = request_id
            return response
        except httpx.ConnectError:
            logger.warning(
                f"[LB] {target} inacessível, tentativa {attempt}/3, "
                f"alternando instância... | request_id={request_id}"
            )
            target = get_next_instance(service)
            url    = f"{target}/{path}"
            if request.url.query:
                url += f"?{request.url.query}"
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"[LB] Erro inesperado: {e} | request_id={request_id}")
            raise HTTPException(502, f"Erro no gateway: {e}")

    raise HTTPException(503, f"Serviço '{service}' indisponível após 3 tentativas.")


# ── Rotas ─────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway", "porta": 8000}


@app.get("/status")
async def status():
    """Verifica status de todos os serviços."""
    resultado = {}
    todos = [
        ("user-service-1",       "http://localhost:8001"),
        ("user-service-2",       "http://localhost:8011"),
        ("event-service-1",      "http://localhost:8002"),
        ("event-service-2",      "http://localhost:8012"),
        ("purchase-service-1",   "http://localhost:8003"),
        ("purchase-service-2",   "http://localhost:8013"),
        ("payment-service",      "http://localhost:8004"),
        ("notification-service", "http://localhost:8005"),
    ]
    async with httpx.AsyncClient(timeout=2.0) as client:
        for nome, url in todos:
            try:
                r = await client.get(f"{url}/health")
                resultado[nome] = "online" if r.status_code == 200 else "erro"
            except Exception:
                resultado[nome] = "offline"
    return resultado


# ── Rotas de usuários ─────────────────────────────────────────
@app.api_route("/users/{path:path}", methods=["GET","POST","PUT","DELETE"])
async def route_users(request: Request, path: str):
    return await proxy(request, "users", path)

@app.api_route("/users", methods=["GET","POST"])
async def route_users_root(request: Request):
    return await proxy(request, "users", "")


# ── Rotas de eventos ──────────────────────────────────────────
@app.api_route("/events/{path:path}", methods=["GET","POST","PUT","DELETE"])
async def route_events(request: Request, path: str):
    return await proxy(request, "events", path)

@app.api_route("/events", methods=["GET","POST"])
async def route_events_root(request: Request):
    return await proxy(request, "events", "")


# ── Rotas de compras ──────────────────────────────────────────
@app.api_route("/purchases/{path:path}", methods=["GET","POST","PUT","DELETE"])
async def route_purchases(request: Request, path: str):
    return await proxy(request, "purchases", path)

@app.api_route("/purchases", methods=["GET","POST"])
async def route_purchases_root(request: Request):
    return await proxy(request, "purchases", "")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
