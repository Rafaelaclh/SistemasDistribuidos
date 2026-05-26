"""
Serviço de Eventos — porta 8002
  GET  /events        → listar eventos
  GET  /events/{id}   → detalhar evento
  POST /events        → criar evento (admin)
  PUT  /events/{id}   → editar preço / quantidade
  GET  /health        → health check

Para rodar:
  python main.py
"""
import time
import logging
import uvicorn

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [event-service] %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Event Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelos ───────────────────────────────────────────────────

class CreateEventRequest(BaseModel):
    name: str
    event_date: str          # "2026-08-15 20:00:00"
    price: float
    available_tickets: int
    created_by: int          # user_id do admin

class UpdateEventRequest(BaseModel):
    price: Optional[float] = None
    available_tickets: Optional[int] = None


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
            ("event-service", str(request.url.path), request.method, response.status_code, ms)
        )
        conn.commit(); cur.close(); conn.close()
    except Exception:
        pass
    return response


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "event-service", "porta": 8002}


@app.get("/events")
def list_events():
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT e.id, e.name, e.event_date, e.price, e.available_tickets,
                   e.created_at, u.name AS created_by_name
            FROM events e JOIN users u ON e.created_by = u.id
            ORDER BY e.event_date ASC
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        for r in rows:
            r["event_date"] = str(r["event_date"])
            r["created_at"] = str(r["created_at"])
            r["price"] = float(r["price"])
        return {"events": rows, "total": len(rows)}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


@app.get("/events/{event_id}")
def get_event(event_id: int):
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT e.id, e.name, e.event_date, e.price, e.available_tickets,
                   e.created_at, u.name AS created_by_name
            FROM events e JOIN users u ON e.created_by = u.id
            WHERE e.id = %s
        """, (event_id,))
        row = cur.fetchone()
        cur.close(); conn.close()
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")

    if not row:
        raise HTTPException(404, "Evento não encontrado")

    row["event_date"] = str(row["event_date"])
    row["created_at"] = str(row["created_at"])
    row["price"] = float(row["price"])
    return row


@app.post("/events", status_code=201)
def create_event(body: CreateEventRequest):
    if body.price <= 0:
        raise HTTPException(400, "Preço deve ser maior que zero")
    if body.available_tickets <= 0:
        raise HTTPException(400, "Quantidade deve ser maior que zero")
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO events (name, event_date, price, available_tickets, created_by) VALUES (%s,%s,%s,%s,%s)",
            (body.name, body.event_date, body.price, body.available_tickets, body.created_by)
        )
        conn.commit()
        event_id = cur.lastrowid
        cur.close(); conn.close()
        logger.info(f"Evento criado: id={event_id} nome={body.name}")
        return {"message": "Evento criado", "event_id": event_id}
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


@app.put("/events/{event_id}")
def update_event(event_id: int, body: UpdateEventRequest):
    if body.price is None and body.available_tickets is None:
        raise HTTPException(400, "Informe preço ou quantidade para atualizar")
    try:
        conn = get_connection()
        cur = conn.cursor()
        if body.price is not None and body.available_tickets is not None:
            cur.execute("UPDATE events SET price=%s, available_tickets=%s WHERE id=%s",
                        (body.price, body.available_tickets, event_id))
        elif body.price is not None:
            cur.execute("UPDATE events SET price=%s WHERE id=%s", (body.price, event_id))
        else:
            cur.execute("UPDATE events SET available_tickets=%s WHERE id=%s",
                        (body.available_tickets, event_id))

        if cur.rowcount == 0:
            conn.close()
            raise HTTPException(404, "Evento não encontrado")

        conn.commit(); cur.close(); conn.close()
        logger.info(f"Evento atualizado: id={event_id}")
        return {"message": "Evento atualizado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro: {e}")
        raise HTTPException(500, "Erro interno")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
