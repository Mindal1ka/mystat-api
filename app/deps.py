"""Автентифікація та стандартні заголовки MyStat.

JWT декодується без перевірки підпису — для мока/проксі цього достатньо;
справжній бекенд верифікує HS256-підпис сам."""
import base64
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import DEFAULT_ALIAS, DEFAULT_LANG, VERIFY_EXP

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="access_token з логіна — plain-text JWT (HS256), живе рівно 30 днів.",
    bearerFormat="JWT",
)


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_jwt_unverified(token: str) -> dict[str, Any]:
    try:
        return json.loads(_b64url_decode(token.split(".")[1]))
    except Exception:
        return {}


def make_fake_jwt(**claims: Any) -> str:
    """Зібрати фейковий JWT (підпис-заглушка) з коректним набором claims прод-токена."""
    header = {"typ": "JWT", "alg": "HS256"}
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": "https://auth.itstep.org/api/auth/login",
        "iat": now,
        "nbf": now,
        "exp": now + 2_592_000,  # рівно 30 днів, як у проді
        "jti": "mock-jti",
        "sub": 100001,
        "id": 100001,
        "id_user_storage": 5000001,
        "email": "student@student.itstep.org",
        "username": "student",
        "name": "Ім'я Прізвище",
        "branch_id": 4,
        "project_id": 50,
        "lang": DEFAULT_LANG,
        "profile": "student",
        "module": "mystat",
        "branch_alias": DEFAULT_ALIAS,
    }
    payload.update(claims)
    enc = lambda o: base64.urlsafe_b64encode(  # noqa: E731
        json.dumps(o, ensure_ascii=False).encode()
    ).decode().rstrip("=")
    return f"{enc(header)}.{enc(payload)}.mock-signature"


@dataclass
class AuthCtx:
    raw: Optional[str]
    payload: dict[str, Any]

    @property
    def alias(self) -> str:
        return self.payload.get("branch_alias") or DEFAULT_ALIAS

    @property
    def lang(self) -> str:
        return self.payload.get("lang") or DEFAULT_LANG

    @property
    def logbook_id(self):
        """JWT.sub / JWT.id — запис студента в журналі. НЕ плутати з id_user_storage!"""
        return self.payload.get("sub") or self.payload.get("id")

    @property
    def id_user_storage(self):
        """Те, що йде в заголовок X-UserId."""
        return self.payload.get("id_user_storage")

    @property
    def profile(self) -> str:
        return self.payload.get("profile", "student")


def _is_expired(payload: dict[str, Any]) -> bool:
    """Опційна перевірка exp (MYSTAT_VERIFY_EXP=1). Підпис і далі НЕ перевіряється."""
    if not VERIFY_EXP:
        return False
    exp = payload.get("exp")
    return isinstance(exp, (int, float)) and exp < time.time()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=[{"field": "summary", "message": "Не авторизован: нужен Bearer access_token"}],
        headers={"WWW-Authenticate": "Bearer"},
    )


def auth_ctx(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthCtx:
    """Обов'язкова авторизація. Кнопка Authorize у Swagger UI заповнює заголовок для всіх запитів."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    payload = decode_jwt_unverified(credentials.credentials)
    if _is_expired(payload):
        raise _unauthorized()
    return AuthCtx(raw=credentials.credentials, payload=payload)


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthCtx:
    """Авторизація опціональна (напр. /translate, публічний конфіг)."""
    if credentials is None or not credentials.credentials:
        return AuthCtx(raw=None, payload={})
    payload = decode_jwt_unverified(credentials.credentials)
    if _is_expired(payload):
        return AuthCtx(raw=None, payload={})
    return AuthCtx(raw=credentials.credentials, payload=payload)


def language_header(
    x_language: Optional[str] = Header(
        default=None,
        description="Код мови акаунта (JWT.lang): ru / ua / uk … Проставляється фронтом після логіна.",
    ),
) -> Optional[str]:
    return x_language


def userid_header(
    x_user_id: Optional[str] = Header(
        default=None,
        alias="X-UserId",  # справжня назва заголовка; без alias FastAPI шукав би X-User-Id
        description="id_user_storage (= account.user_profiles[*][*].user_id). Це НЕ logbook_id (JWT.sub)!",
    ),
) -> Optional[str]:
    return x_user_id
