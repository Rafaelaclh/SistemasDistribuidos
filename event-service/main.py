"""
Serviço de Eventos
  Instância 1: porta 8002
  Instância 2: porta 8012

  GET  /events        → listar eventos (público)
  GET  /events/{id}   → detalhar evento (público)
  POST /events        → criar evento (admin)
  PUT  /events/{id}   → editar preço e/ou quantidade (admin)
  GET  /health        → health check

  Autorização via headers internos repassados pelo gateway:
    X-User-ID, X-User-Role, X-User-Name
  O gateway já validou o JWT — o serviço confia nesses headers.

Para rodar:
  python main.py
  python main.py --port 8012
"""
import sys
import time
import logging
import uvicorn

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import get_connection, init_db

PORT = 8002
for i, arg in enumerate(sys.argv):
    if arg == "--port" and i + 1 < len(sys.argv):
        PORT = int(sys.argv[i + 1])

logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [event-service:{PORT}] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title=f"Event Service :{PORT}")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def require_admin(x_user_role: Optional[str] = Header(default=None)):
    """
    Verifica se o header X-User-Role (repassado pelo gateway) é 'admin'.
    O gateway já validou o JWT — aqui apenas checamos a role.
    """
    if x_user_role != "admin":
        raise HTTPException(403, "Acesso negado. Apenas administradores podem executar esta ação.")
    return x_user_role


class CreateEventRequest(BaseModel):
    name: str
    event_date: str
    price: float
    available_tickets: int

class UpdateEventRequest(BaseModel):
    name: Optional[str] = None
    event_date: Optional[str] = None
    price: Optional[float] = None
    available_tickets: Optional[int] = None


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start      = time.time()
    response   = await call_next(request)
    ms         = int((time.time() - start) * 1000)
    request_id = request.headers.get("x-request-id", "-")
    user_id    = request.headers.get("x-user-id", "anon")
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} "
        f"({ms}ms) | request_id={request_id} | user={user_id}"
    )
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO metrics (service, endpoint, method, status_code, latency_ms) VALUES (?,?,?,?,?)",
            (f"event-service:{PORT}", str(request.url.path), request.method, response.status_code, ms)
        )
        conn.commit(); conn.close()
    except Exception:
        pass
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "event-service", "porta": PORT}


@app.get("/events")
def list_events():
    """Lista todos os eventos. Rota pública."""
    try:
        conn = get_connection()
        rows = conn.execute("""
            SELECT e.id, e.name, e.event_date, e.price, e.available_tickets,
                   e.created_at, u.name AS created_by_name
            FROM events e JOIN users u ON e.created_by = u.id
            ORDER BY e.event_date ASC
        """).fetchall()
        conn.close()
        return {"events": [dict(r) for r in rows], "total": len(rows)}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


@app.get("/events/{event_id}")
def get_event(event_id: int):
    """Detalha um evento. Rota pública."""
    try:
        conn = get_connection()
        row  = conn.execute("""
            SELECT e.id, e.name, e.event_date, e.price, e.available_tickets,
                   e.created_at, u.name AS created_by_name
            FROM events e JOIN users u ON e.created_by = u.id
            WHERE e.id=?
        """, (event_id,)).fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")

    if not row:
        raise HTTPException(404, "Evento não encontrado")
    return dict(row)


@app.post("/events", status_code=201)
def create_event(
    body: CreateEventRequest,
    x_user_id:   Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
):
    """Cria um novo evento. Exige role=admin."""
    require_admin(x_user_role)

    if body.price <= 0:
        raise HTTPException(400, "Preço deve ser maior que zero")
    if body.available_tickets <= 0:
        raise HTTPException(400, "Quantidade deve ser maior que zero")

    created_by = int(x_user_id) if x_user_id else 1

    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO events (name, event_date, price, available_tickets, created_by) VALUES (?,?,?,?,?)",
            (body.name, body.event_date, body.price, body.available_tickets, created_by)
        )
        conn.commit()
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        logger.info(f"Evento criado: id={event_id} por admin user_id={created_by}")
        return {"message": "Evento criado", "event_id": event_id}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


@app.put("/events/{event_id}")
def update_event(
    event_id: int,
    body: UpdateEventRequest,
    x_user_role: Optional[str] = Header(default=None),
):
    """Atualiza nome, data, preço e/ou quantidade. Exige role=admin."""
    require_admin(x_user_role)

    campos = {}
    if body.name              is not None: campos["name"]              = body.name
    if body.event_date        is not None: campos["event_date"]        = body.event_date
    if body.price             is not None: campos["price"]             = body.price
    if body.available_tickets is not None: campos["available_tickets"] = body.available_tickets

    if not campos:
        raise HTTPException(400, "Informe ao menos um campo para atualizar")

    try:
        conn = get_connection()
        row  = conn.execute("SELECT id FROM events WHERE id=?", (event_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Evento não encontrado")

        set_clause = ", ".join(f"{k}=?" for k in campos)
        valores    = list(campos.values()) + [event_id]
        conn.execute(f"UPDATE events SET {set_clause} WHERE id=?", valores)
        conn.commit(); conn.close()
        logger.info(f"Evento atualizado: id={event_id} campos={list(campos.keys())}")
        return {"message": "Evento atualizado com sucesso"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


if __name__ == "__main__":
    init_db()
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
