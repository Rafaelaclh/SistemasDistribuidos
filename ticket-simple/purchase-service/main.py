"""
Serviço de Compras — porta 8003  ⭐ O mais importante
  POST /purchases          → comprar ingresso
  GET  /purchases          → listar compras (?user_id=N)
  GET  /purchases/{id}     → detalhar compra
  GET  /health             → health check

Implementa:
  ✅ Controle de concorrência — SELECT FOR UPDATE (evita overselling)
  ✅ Idempotência            — transaction_id único (evita compra dupla)
  ✅ Resiliência             — retry com backoff no banco
  ✅ Comunicação assíncrona  — chama payment-service em thread separada

Para rodar:
  python main.py
"""
import uuid
import time
import logging
import threading
import uvicorn
import requests
import mysql.connector

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [purchase-service] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Purchase Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PAYMENT_SERVICE_URL    = "http://localhost:8004"
NOTIFICATION_SERVICE_URL = "http://localhost:8005"


# ── Modelo ────────────────────────────────────────────────────

class PurchaseRequest(BaseModel):
    user_id: int
    event_id: int
    quantity: int = 1
    payment_method: str        # "boleto" | "pix" | "credit_card"
    transaction_id: Optional[str] = None


# ── Middleware ────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = int((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({ms}ms)")
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO metrics (service, endpoint, method, status_code, latency_ms) VALUES (%s,%s,%s,%s,%s)",
            ("purchase-service", str(request.url.path), request.method, response.status_code, ms)
        )
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass
    return response


# ── Comunicação assíncrona com outros serviços ────────────────

def notify_payment(data: dict):
    """
    Chama o serviço de pagamento em background (thread separada).
    Isso simula comunicação assíncrona: o usuário recebe resposta
    imediatamente e o pagamento é processado depois.
    """
    def _call():
        for attempt in range(1, 4):
            try:
                r = requests.post(
                    f"{PAYMENT_SERVICE_URL}/process",
                    json=data, timeout=5
                )
                logger.info(f"[Payment] Resposta: {r.status_code}")
                return
            except Exception as e:
                logger.warning(f"[Payment] Tentativa {attempt}/3 falhou: {e}")
                time.sleep(2 ** attempt)
        logger.error("[Payment] Falha após 3 tentativas — pagamento não processado")

    threading.Thread(target=_call, daemon=True).start()


def notify_notification(data: dict):
    """Chama o serviço de notificação em background."""
    def _call():
        for attempt in range(1, 4):
            try:
                requests.post(
                    f"{NOTIFICATION_SERVICE_URL}/notify",
                    json=data, timeout=5
                )
                return
            except Exception as e:
                logger.warning(f"[Notification] Tentativa {attempt}/3 falhou: {e}")
                time.sleep(2 ** attempt)

    threading.Thread(target=_call, daemon=True).start()


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "purchase-service", "porta": 8003}


@app.post("/purchases", status_code=201)
def create_purchase(body: PurchaseRequest):
    """
    Fluxo de compra com controle de concorrência e idempotência.

    1. Verifica se transaction_id já existe (idempotência)
    2. Abre transação e bloqueia a linha do evento (SELECT FOR UPDATE)
    3. Verifica estoque disponível
    4. Decrementa estoque + registra compra
    5. Faz commit e libera o lock
    6. Dispara pagamento e notificação em background (assíncrono)
    """
    if body.payment_method not in ("boleto", "pix", "credit_card"):
        raise HTTPException(400, "payment_method deve ser: boleto, pix ou credit_card")
    if body.quantity < 1:
        raise HTTPException(400, "Quantidade deve ser pelo menos 1")

    transaction_id = body.transaction_id or str(uuid.uuid4())
    logger.info(f"Nova compra | tx={transaction_id} user={body.user_id} event={body.event_id} qty={body.quantity}")

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        # ── 1. IDEMPOTÊNCIA ───────────────────────────────────
        cur.execute("SELECT * FROM purchases WHERE transaction_id = %s", (transaction_id,))
        existing = cur.fetchone()
        if existing:
            logger.warning(f"Compra duplicada detectada | tx={transaction_id}")
            cur.close(); conn.close()
            return {
                "message": "Compra já processada (requisição duplicada detectada)",
                "transaction_id": transaction_id,
                "purchase_id": existing["id"],
                "status": existing["status"]
            }

        # ── 2. LOCK NO EVENTO (controle de concorrência) ──────
        # SELECT FOR UPDATE garante que apenas uma transação por vez
        # lê e modifica este registro — sem overselling!
        cur.execute("SELECT * FROM events WHERE id = %s FOR UPDATE", (body.event_id,))
        event = cur.fetchone()

        if not event:
            conn.rollback()
            raise HTTPException(404, "Evento não encontrado")

        if event["available_tickets"] < body.quantity:
            conn.rollback()
            logger.warning(
                f"Estoque insuficiente | event={body.event_id} "
                f"disponível={event['available_tickets']} pedido={body.quantity}"
            )
            raise HTTPException(
                409,
                f"Ingressos insuficientes. Disponível: {event['available_tickets']}"
            )

        # ── 3. ATUALIZA ESTOQUE ───────────────────────────────
        cur.execute(
            "UPDATE events SET available_tickets = available_tickets - %s WHERE id = %s",
            (body.quantity, body.event_id)
        )

        # ── 4. REGISTRA COMPRA ────────────────────────────────
        total = float(event["price"]) * body.quantity
        cur.execute(
            """INSERT INTO purchases
               (transaction_id, user_id, event_id, quantity, total_price, payment_method, status)
               VALUES (%s,%s,%s,%s,%s,%s,'pending')""",
            (transaction_id, body.user_id, body.event_id,
             body.quantity, total, body.payment_method)
        )
        purchase_id = cur.lastrowid

        # ── 5. COMMIT → libera o lock ─────────────────────────
        conn.commit()
        cur.close(); conn.close()

        logger.info(f"Compra registrada | id={purchase_id} total=R${total:.2f}")

        # ── 6. DISPARA SERVIÇOS EXTERNOS (assíncrono) ─────────
        payload = {
            "purchase_id":    purchase_id,
            "transaction_id": transaction_id,
            "user_id":        body.user_id,
            "event_id":       body.event_id,
            "event_name":     event["name"],
            "quantity":       body.quantity,
            "total_price":    total,
            "payment_method": body.payment_method,
        }
        notify_payment(payload)
        notify_notification(payload)

        return {
            "message":        "Compra realizada! Aguardando confirmação do pagamento.",
            "purchase_id":    purchase_id,
            "transaction_id": transaction_id,
            "status":         "pending",
            "total_price":    total,
            "event":          event["name"],
        }

    except HTTPException:
        raise
    except mysql.connector.Error as e:
        if conn: conn.rollback()
        logger.error(f"Erro de banco: {e}")
        raise HTTPException(500, "Erro interno no banco de dados")
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Erro inesperado: {e}")
        raise HTTPException(500, "Erro interno")


@app.get("/purchases")
def list_purchases(user_id: Optional[int] = None):
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        if user_id:
            cur.execute("""
                SELECT p.*, e.name AS event_name
                FROM purchases p JOIN events e ON p.event_id = e.id
                WHERE p.user_id = %s ORDER BY p.created_at DESC
            """, (user_id,))
        else:
            cur.execute("""
                SELECT p.*, e.name AS event_name
                FROM purchases p JOIN events e ON p.event_id = e.id
                ORDER BY p.created_at DESC
            """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        for r in rows:
            r["created_at"]  = str(r.get("created_at",""))
            r["updated_at"]  = str(r.get("updated_at",""))
            r["total_price"] = float(r.get("total_price", 0))
        return {"purchases": rows, "total": len(rows)}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


@app.get("/purchases/{purchase_id}")
def get_purchase(purchase_id: int):
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT p.*, e.name AS event_name
            FROM purchases p JOIN events e ON p.event_id = e.id
            WHERE p.id = %s
        """, (purchase_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")

    if not row:
        raise HTTPException(404, "Compra não encontrada")

    row["created_at"]  = str(row.get("created_at",""))
    row["updated_at"]  = str(row.get("updated_at",""))
    row["total_price"] = float(row.get("total_price", 0))
    return row


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
