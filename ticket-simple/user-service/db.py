"""
db.py — conexão com MySQL.
Copie este arquivo para dentro de cada pasta de serviço.
"""
import time
import logging
import mysql.connector
from mysql.connector import Error

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "root123",   # ← troque pela sua senha do MySQL
    "database": "tickets_db",
    "autocommit": False,
}

def get_connection():
    for attempt in range(1, 6):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            return conn
        except Error as e:
            logger.warning(f"[DB] Tentativa {attempt}/5 falhou: {e}")
            time.sleep(2)
    raise RuntimeError("Não foi possível conectar ao banco após 5 tentativas.")
