"""
Serviço de Notificação (Mock) — porta 8005
  POST /notify  → simula envio de e-mail
  GET  /health  → health check

Para rodar:
  python main.py
"""
import time
import logging
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [notification-service] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Notification Service (Mock)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelo ────────────────────────────────────────────────────

class NotificationRequest(BaseModel):
    purchase_id:    int
    transaction_id: str
    user_id:        int
    event_name:     str
    quantity:       int
    total_price:    float
    payment_method: str


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service", "porta": 8005}


@app.post("/notify")
def notify(body: NotificationRequest):
    """
    Mock de envio de e-mail de confirmação.
    Em produção, aqui entraria uma biblioteca como smtplib ou SendGrid.
    """
    logger.info("=" * 55)
    logger.info("📧  SIMULAÇÃO DE E-MAIL ENVIADO")
    logger.info(f"    Para:      user_id={body.user_id}")
    logger.info(f"    Evento:    {body.event_name}")
    logger.info(f"    Qtd:       {body.quantity} ingresso(s)")
    logger.info(f"    Total:     R$ {body.total_price:.2f}")
    logger.info(f"    Pagamento: {body.payment_method}")
    logger.info(f"    ID:        {body.transaction_id}")
    logger.info("=" * 55)

    # Simula latência de envio
    time.sleep(0.3)

    return {"message": "E-mail enviado com sucesso (simulação)"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
