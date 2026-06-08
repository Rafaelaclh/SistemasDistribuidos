"""
Serviço de Usuários
  Instância 1: porta 8001
  Instância 2: porta 8011

  POST /register  → cadastro (público)
  POST /login     → login — retorna JWT (público)
  GET  /users     → listar usuários (admin)
  GET  /health    → health check

Para rodar:
  python main.py
  python main.py --port 8011
"""
import sys
import time
import logging
import uvicorn
import bcrypt

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import get_connection, init_db
from auth import criar_token, get_admin_user

PORT = 8001
for i, arg in enumerate(sys.argv):
    if arg == "--port" and i + 1 < len(sys.argv):
        PORT = int(sys.argv[i + 1])

logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [user-service:{PORT}] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title=f"User Service :{PORT}")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "user"

class LoginRequest(BaseModel):
    email: str
    password: str


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start    = time.time()
    response = await call_next(request)
    ms       = int((time.time() - start) * 1000)
    request_id = request.headers.get("x-request-id", "-")
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} "
        f"({ms}ms) | request_id={request_id}"
    )
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO metrics (service, endpoint, method, status_code, latency_ms) VALUES (?,?,?,?,?)",
            (f"user-service:{PORT}", str(request.url.path), request.method, response.status_code, ms)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "user-service", "porta": PORT}


@app.post("/register", status_code=201)
def register(body: RegisterRequest):
    """Cadastra um novo usuário."""
    if body.role not in ("user", "admin"):
        raise HTTPException(400, "Role deve ser 'user' ou 'admin'")
    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
            (body.name, body.email, hashed, body.role)
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        logger.info(f"Usuário criado: id={user_id} email={body.email} role={body.role}")
        return {"message": "Usuário criado com sucesso", "user_id": user_id}
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(409, "E-mail já cadastrado")
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


@app.post("/login")
def login(body: LoginRequest):
    """Login — retorna JWT."""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT id, name, email, password, role FROM users WHERE email=?",
            (body.email,)
        ).fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")

    if not row:
        raise HTTPException(401, "Credenciais inválidas")

    if not bcrypt.checkpw(body.password.encode(), row["password"].encode()):
        raise HTTPException(401, "Credenciais inválidas")

    token = criar_token(row["id"], row["name"], row["role"])
    logger.info(f"Login: id={row['id']} email={row['email']}")
    return {
        "token":   token,
        "user_id": row["id"],
        "name":    row["name"],
        "role":    row["role"],
    }


@app.get("/users")
def list_users(admin=Depends(get_admin_user)):
    """Lista todos os usuários. Apenas admin."""
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, name, email, role, created_at FROM users ORDER BY id"
        ).fetchall()
        conn.close()
        return {"users": [dict(r) for r in rows]}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


if __name__ == "__main__":
    init_db()
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
