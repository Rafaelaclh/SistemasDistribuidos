"""
Serviço de Usuários — porta 8001
  POST /register  → cadastro
  POST /login     → login
  GET  /users     → listar usuários
  GET  /health    → health check

Para rodar:
  python main.py
"""
import time
import logging
import uvicorn
import bcrypt
import mysql.connector

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [user-service] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="User Service")

# Libera CORS para o front conseguir chamar
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelos ───────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "user"

class LoginRequest(BaseModel):
    email: str
    password: str


# ── Middleware de métricas ────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = int((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({ms}ms)")
    # salva métrica no banco
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO metrics (service, endpoint, method, status_code, latency_ms) VALUES (%s,%s,%s,%s,%s)",
            ("user-service", str(request.url.path), request.method, response.status_code, ms)
        )
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass
    return response


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "user-service", "porta": 8001}


@app.post("/register", status_code=201)
def register(body: RegisterRequest):
    if body.role not in ("user", "admin"):
        raise HTTPException(400, "Role deve ser 'user' ou 'admin'")

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s,%s,%s,%s)",
            (body.name, body.email, hashed, body.role)
        )
        conn.commit()
        user_id = cur.lastrowid
        cur.close(); conn.close()
        logger.info(f"Usuário criado: id={user_id} email={body.email}")
        return {"message": "Usuário criado com sucesso", "user_id": user_id}
    except mysql.connector.errors.IntegrityError:
        raise HTTPException(409, "E-mail já cadastrado")
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


@app.post("/login")
def login(body: LoginRequest):
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (body.email,))
        user = cur.fetchone()
        cur.close(); conn.close()
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")

    if not user or not bcrypt.checkpw(body.password.encode(), user["password"].encode()):
        raise HTTPException(401, "E-mail ou senha incorretos")

    logger.info(f"Login: user_id={user['id']} role={user['role']}")
    return {
        "message": "Login realizado",
        "user_id": user["id"],
        "name":    user["name"],
        "role":    user["role"],
    }


@app.get("/users")
def list_users():
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, email, role, created_at FROM users ORDER BY id")
        rows = cur.fetchall()
        cur.close(); conn.close()
        for r in rows:
            r["created_at"] = str(r["created_at"])
        return {"users": rows, "total": len(rows)}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
