"""
auth.py — Módulo de autenticação JWT compartilhado.
Copie para cada serviço que precisa verificar tokens.
"""
import os
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException
from typing import Optional

JWT_SECRET    = os.environ.get("JWT_SECRET", "ticketflow-secret-dev-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = 8


def criar_token(user_id: int, name: str, role: str) -> str:
    payload = {
        "sub":  str(user_id),
        "name": name,
        "role": role,
        "exp":  datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_H),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado. Faça login novamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido.")


def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization header ausente ou inválido.")
    token = authorization.split(" ", 1)[1]
    return verificar_token(token)


def get_admin_user(authorization: Optional[str] = Header(default=None)) -> dict:
    user = get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(403, "Acesso negado. Apenas administradores.")
    return user
