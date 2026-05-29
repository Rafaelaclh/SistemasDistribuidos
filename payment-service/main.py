"""
Serviço de Pagamento (Mock) — porta 8004
  POST /process → processa pagamento
  GET  /health  → health check

Para rodar: python main.py
"""
import time
import random
import logging
import uvicorn

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import get_connection, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [payment-service] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Service (Mock)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PaymentRequest(BaseModel):
    purchase_id: int; transaction_id: str; user_id: int
    event_id: int; event_name: str; quantity: int
    total_price: float; payment_method: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service", "porta": 8004}


@app.post("/process")
def process_payment(
    body: PaymentRequest,
    x_request_id: Optional[str] = Header(default=None),
):
    request_id = x_request_id or "-"
    logger.info(
        f"Processando | purchase_id={body.purchase_id} método={body.payment_method} "
        f"total=R${body.total_price:.2f} | request_id={request_id}"
    )

    time.sleep(random.uniform(0.5, 2.0))

    taxas    = {"pix": 0.92, "boleto": 0.88, "credit_card": 0.80}
    aprovado = random.random() < taxas.get(body.payment_method, 0.85)
    status   = "approved" if aprovado else "rejected"

    try:
        conn = get_connection()
        conn.execute(
            "UPDATE purchases SET status=?, updated_at=datetime('now','localtime') WHERE id=?",
            (status, body.purchase_id)
        )
        conn.commit()
        if not aprovado:
            conn.execute(
                "UPDATE events SET available_tickets = available_tickets + ? WHERE id=?",
                (body.quantity, body.event_id)
            )
            conn.commit()
            logger.info(f"Ingressos devolvidos | event_id={body.event_id} | request_id={request_id}")
        conn.close()
    except Exception as e:
        logger.error(f"Erro no banco: {e} | request_id={request_id}")
        raise HTTPException(500, "Erro interno")

    logger.info(
        f"Pagamento {'APROVADO' if aprovado else 'REJEITADO'} | "
        f"purchase_id={body.purchase_id} | request_id={request_id}"
    )
    return {
        "purchase_id":  body.purchase_id,
        "status":       status,
        "request_id":   request_id,
        "message":      "Aprovado!" if aprovado else "Recusado pela operadora.",
    }


if __name__ == "__main__":
    init_db()
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=False)
