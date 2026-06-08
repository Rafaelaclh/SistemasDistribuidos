"""db.py — Banco de dados SQLite compartilhado."""
import sqlite3
import os
import bcrypt

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "banco.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL UNIQUE,
            password   TEXT NOT NULL,
            role       TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT NOT NULL,
            event_date        TEXT NOT NULL,
            price             REAL NOT NULL,
            available_tickets INTEGER NOT NULL,
            created_by        INTEGER NOT NULL,
            created_at        TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL UNIQUE,
            user_id        INTEGER NOT NULL,
            event_id       INTEGER NOT NULL,
            quantity       INTEGER NOT NULL DEFAULT 1,
            total_price    REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'pending',
            created_at     TEXT DEFAULT (datetime('now','localtime')),
            updated_at     TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id)  REFERENCES users(id),
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            service     TEXT NOT NULL,
            endpoint    TEXT NOT NULL,
            method      TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            latency_ms  INTEGER NOT NULL,
            recorded_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    conn.commit()

    exists = conn.execute("SELECT id FROM users WHERE email='admin@tickets.com'").fetchone()
    if not exists:
        try:
            hashed = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
            conn.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
                ("Administrador", "admin@tickets.com", hashed, "admin")
            )
            conn.commit()
            print("[DB] Admin criado: admin@tickets.com / admin123")
        except Exception:
            conn.rollback()
            print("[DB] Admin já existe (race condition ignorada).")

    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    if count == 0:
        admin = conn.execute("SELECT id FROM users WHERE email='admin@tickets.com'").fetchone()
        if admin:
            exemplos = [
                ("Show do Metallica - São Paulo", "2026-08-15 20:00:00", 350.00, 100),
                ("Festival de Jazz - Floripa",    "2026-09-01 18:00:00", 120.00,  50),
                ("Jogo Flamengo x Palmeiras",     "2026-07-20 16:00:00",  80.00, 200),
            ]
            for ev in exemplos:
                conn.execute(
                    "INSERT INTO events (name, event_date, price, available_tickets, created_by) VALUES (?,?,?,?,?)",
                    (*ev, admin[0])
                )
            conn.commit()
            print("[DB] Eventos de exemplo criados.")

    conn.close()
    print(f"[DB] Banco pronto: {DB_PATH}")
