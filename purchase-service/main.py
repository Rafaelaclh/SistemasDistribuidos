"""Serviço de Compras — portas 8003 / 8013."""
import sys
import uuid
import time
import logging
import threading
import uvicorn
import requests

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import get_connection, init_db

PORT = 8003
for i, arg in enumerate(sys.argv):
    if arg == "--port" and i + 1 < len(sys.argv):
        PORT = int(sys.argv[i + 1])

logging.basicConfig(
    level=logging.INFO,
    format=f"%(asctime)s [purchase-service:{PORT}] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title=f"Purchase Service :{PORT}")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PAYMENT_URL      = "http://localhost:8004"
NOTIFICATION_URL = "http://localhost:8005"


class PurchaseRequest(BaseModel):
    event_id: int
    quantity: int = 1
    payment_method: str
    transaction_id: Optional[str] = None


def require_auth(x_user_id: Optional[str]) -> int:
    if not x_user_id:
        raise HTTPException(401, "Autenticação necessária.")
    return int(x_user_id)


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
            (f"purchase-service:{PORT}", str(request.url.path), request.method, response.status_code, ms)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
    return response


def chamar_async(url: str, data: dict, nome: str, request_id: str):
    def _run():
        headers = {"Content-Type": "application/json", "X-Request-ID": request_id}
        for tentativa in range(1, 4):
            try:
                requests.post(url, json=data, headers=headers, timeout=5)
                logger.info(f"[{nome}] OK | request_id={request_id}")
                return
            except Exception as e:
                logger.warning(f"[{nome}] Tentativa {tentativa}/3 falhou: {e}")
                time.sleep(2 ** tentativa)
        logger.error(f"[{nome}] Falha após 3 tentativas | request_id={request_id}")
    threading.Thread(target=_run, daemon=True).start()


@app.get("/health")
def health():
    return {"status": "ok", "service": "purchase-service", "porta": PORT}


@app.post("/purchases", status_code=201)
def create_purchase(
    body: PurchaseRequest,
    x_user_id:    Optional[str] = Header(default=None),
    x_request_id: Optional[str] = Header(default=None),
):
    user_id    = require_auth(x_user_id)
    request_id = x_request_id or str(uuid.uuid4())

    if body.payment_method not in ("boleto", "pix", "credit_card"):
        raise HTTPException(400, "payment_method deve ser: boleto, pix ou credit_card")
    if body.quantity < 1:
        raise HTTPException(400, "Quantidade deve ser pelo menos 1")

    transaction_id = body.transaction_id or str(uuid.uuid4())
    logger.info(f"Compra | tx={transaction_id} user={user_id} event={body.event_id} qty={body.quantity}")

    conn = None
    try:
        conn = get_connection()

        existing = conn.execute(
            "SELECT * FROM purchases WHERE transaction_id=?", (transaction_id,)
        ).fetchone()
        if existing:
            conn.close()
            return {
                "message":        "Compra já processada (requisição duplicada)",
                "transaction_id": transaction_id,
                "purchase_id":    existing["id"],
                "status":         existing["status"],
            }

        conn.execute("BEGIN EXCLUSIVE")

        event = conn.execute("SELECT * FROM events WHERE id=?", (body.event_id,)).fetchone()

        if not event:
            conn.rollback()
            conn.close()
            raise HTTPException(404, "Evento não encontrado")

        if event["available_tickets"] < body.quantity:
            conn.rollback()
            conn.close()
            raise HTTPException(409, f"Ingressos insuficientes. Disponível: {event['available_tickets']}")

        conn.execute(
            "UPDATE events SET available_tickets = available_tickets - ? WHERE id=?",
            (body.quantity, body.event_id)
        )

        total = event["price"] * body.quantity
        conn.execute(
            """INSERT INTO purchases
               (transaction_id, user_id, event_id, quantity, total_price, payment_method, status)
               VALUES (?,?,?,?,?,?,'pending')""",
            (transaction_id, user_id, body.event_id, body.quantity, total, body.payment_method)
        )
        purchase_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
        logger.info(f"Compra registrada | id={purchase_id} total=R${total:.2f}")

        payload = {
            "purchase_id":    purchase_id,
            "transaction_id": transaction_id,
            "user_id":        user_id,
            "event_id":       body.event_id,
            "event_name":     event["name"],
            "quantity":       body.quantity,
            "total_price":    total,
            "payment_method": body.payment_method,
        }
        chamar_async(f"{PAYMENT_URL}/process",     payload, "payment-service",      request_id)
        chamar_async(f"{NOTIFICATION_URL}/notify", payload, "notification-service", request_id)

        return {
            "message":        "Compra realizada! Aguardando confirmação do pagamento.",
            "purchase_id":    purchase_id,
            "transaction_id": transaction_id,
            "status":         "pending",
            "total_price":    total,
            "event":          event["name"],
            "request_id":     request_id,
        }

    except HTTPException:
        if conn:
            try: conn.rollback()
            except: pass
        raise
    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
        logger.error(f"Erro inesperado: {e}")
        raise HTTPException(500, "Erro interno")


@app.get("/purchases")
def list_purchases(
    user_id:     Optional[int] = None,
    x_user_id:   Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
):
    auth_user_id = require_auth(x_user_id)
    if x_user_role != "admin":
        user_id = auth_user_id

    try:
        conn = get_connection()
        if user_id:
            rows = conn.execute("""
                SELECT p.*, e.name AS event_name
                FROM purchases p JOIN events e ON p.event_id=e.id
                WHERE p.user_id=? ORDER BY p.created_at DESC
            """, (user_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT p.*, e.name AS event_name
                FROM purchases p JOIN events e ON p.event_id=e.id
                ORDER BY p.created_at DESC
            """).fetchall()
        conn.close()
        return {"purchases": [dict(r) for r in rows], "total": len(rows)}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


@app.get("/purchases/{purchase_id}")
def get_purchase(
    purchase_id: int,
    x_user_id:   Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
):
    auth_user_id = require_auth(x_user_id)

    try:
        conn = get_connection()
        row = conn.execute("""
            SELECT p.*, e.name AS event_name
            FROM purchases p JOIN events e ON p.event_id=e.id
            WHERE p.id=?
        """, (purchase_id,)).fetchone()
        conn.close()
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")

    if not row:
        raise HTTPException(404, "Compra não encontrada")

    if x_user_role != "admin" and row["user_id"] != auth_user_id:
        raise HTTPException(403, "Acesso negado.")

    return dict(row)


if __name__ == "__main__":
    init_db()
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
