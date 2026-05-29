"""
auth.py — Módulo de autenticação JWT compartilhado.
Copiado para cada serviço que precisa verificar tokens.

Fluxo:
  1. Usuário faz POST /login → user-service retorna um JWT
  2. Cliente inclui o token em todas as requisições:
       Authorization: Bearer <token>
  3. O gateway valida o token E repassa os headers X-User-* para
     os serviços internos, que confiam nesses headers (rede interna).
  4. Serviços que exigem role=admin verificam X-User-Role.
"""
import os
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException
from typing import Optional

# Em produção use uma variável de ambiente segura.
JWT_SECRET    = os.environ.get("JWT_SECRET", "ticketflow-secret-dev-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_H  = 8   # horas


def criar_token(user_id: int, name: str, role: str) -> str:
    """Gera um JWT com os dados do usuário."""
    payload = {
        "sub":  str(user_id),
        "name": name,
        "role": role,
        "exp":  datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_H),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verificar_token(token: str) -> dict:
    """Decodifica e valida o JWT. Lança HTTPException em caso de erro."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado. Faça login novamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido.")


# ── Dependências FastAPI ──────────────────────────────────────

def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """
    Dependência: extrai e valida o JWT do header Authorization.
    Usada em rotas que exigem qualquer usuário autenticado.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization header ausente ou inválido. Use: Bearer <token>")
    token = authorization.split(" ", 1)[1]
    return verificar_token(token)


def get_admin_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """
    Dependência: igual a get_current_user, mas exige role='admin'.
    Usada em rotas exclusivas de administrador.
    """
    user = get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(403, "Acesso negado. Apenas administradores podem executar esta ação.")
    return user
