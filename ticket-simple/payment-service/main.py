"""
Serviço de Pagamento (Mock) — porta 8004
  POST /process  → processa pagamento (chamado pelo purchase-service)
  GET  /health   → health check

Simula aprovação/rejeição do pagamento e atualiza o status no banco.

Para rodar:
  python main.py
"""
import time
import random
import logging
import uvicorn

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [payment-service] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Service (Mock)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelo ────────────────────────────────────────────────────

class PaymentRequest(BaseModel):
    purchase_id:    int
    transaction_id: str
    user_id:        int
    event_id:       int
    event_name:     str
    quantity:       int
    total_price:    float
    payment_method: str


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service", "porta": 8004}


@app.post("/process")
def process_payment(body: PaymentRequest):
    """
    Mock de gateway de pagamento.
    Simula um tempo de processamento e decide aleatoriamente se aprova.
    Taxa de aprovação:
      PIX         → 92%
      Boleto      → 88%
      Cartão      → 80%
    """
    logger.info(
        f"Processando pagamento | purchase_id={body.purchase_id} "
        f"método={body.payment_method} total=R${body.total_price:.2f}"
    )

    # Simula latência do gateway externo
    time.sleep(random.uniform(0.5, 2.0))

    # Decide aprovação por método de pagamento
    taxas = {"pix": 0.92, "boleto": 0.88, "credit_card": 0.80}
    taxa = taxas.get(body.payment_method, 0.85)
    aprovado = random.random() < taxa

    novo_status = "approved" if aprovado else "rejected"

    # Atualiza no banco
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE purchases SET status = %s WHERE id = %s",
            (novo_status, body.purchase_id)
        )
        conn.commit()
        cur.close(); conn.close()
    except Exception as e:
        logger.error(f"Erro ao atualizar status: {e}")
        raise HTTPException(500, "Erro interno")

    # Se rejeitado, devolve ingresso ao estoque
    if not aprovado:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE events SET available_tickets = available_tickets + %s WHERE id = %s",
                (body.quantity, body.event_id)
            )
            conn.commit()
            cur.close(); conn.close()
            logger.info(f"Ingressos devolvidos ao estoque | event_id={body.event_id} qty={body.quantity}")
        except Exception as e:
            logger.error(f"Erro ao devolver estoque: {e}")

    logger.info(
        f"Pagamento {'APROVADO ✓' if aprovado else 'REJEITADO ✗'} | "
        f"purchase_id={body.purchase_id} tx={body.transaction_id}"
    )

    return {
        "purchase_id":    body.purchase_id,
        "transaction_id": body.transaction_id,
        "status":         novo_status,
        "message":        "Pagamento aprovado!" if aprovado else "Pagamento recusado pela operadora."
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
