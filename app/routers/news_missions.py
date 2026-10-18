"""§14 «Новини» (ледачий чанк `CxyTFJYr`, endpoint `/news`) та «Місії» (чанк `Bxt9wog3`,
endpoint `/missions`) — MYSTAT_API.md §14.

Шляхи підтверджені кодом бандлів фронтенду (✅); формати тіл/відповідей відновлені
за непрямими ознаками (⚠️). Пагінація новин — Laravel-стиль: номери сторінок
приходять заголовками відповіді `X-Pagination-Current-Page` / `X-Pagination-Page-count`.
"""
import math
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx
from ..models.common import ApiError
from ..proxy import MODE, forward, handle

router = APIRouter(prefix="/v1/mystat/{branch_alias}", dependencies=[Depends(auth_ctx)])

# ── Заглушки (⚠️ структура за непрямих ознак) ────────────────────────────

_SAMPLE_NEWS: list[dict[str, Any]] = [
    {
        "id": 1201,
        "title": "Обновление MyStat 4.18",
        "body": "В разделе «Расписание» теперь можно смотреть записи уроков…",
        "cover": "assets/images/news/cover-1201.jpg",
        "published_at": "2026-08-21 09:00:00",
        "is_viewed": False,
    },
    {
        "id": 1187,
        "title": "Хакатон STEP IT Weekend",
        "body": "Реєстрація відкрита до кінця місяця — збирай команду!",
        "cover": "assets/images/news/cover-1187.jpg",
        "published_at": "2026-08-14 12:30:00",
        "is_viewed": True,
    },
]

_SAMPLE_MISSIONS: list[dict[str, Any]] = [
    # Форма елемента — по mapMission з чанка Bxt9wog3 ✅
    {
        "id": 301,
        "mission": {
            "id": 11,
            "name": "Місяць без запізнень",
            "category": "Super",
            "description": "Не спізнюйся на пари 30 днів поспіль.",
            "deadline": "2026-08-31 23:59:59",
            "cristals": 50,
        },
        "coins": 0,
        "imageUrl": "mission-super-punctual.png",
        "status": "OnReview",
        "date_pending": "2026-08-24 10:00:00",
        "date_rejected": None,
    },
    {
        "id": 302,
        "mission": {
            "id": 12,
            "name": "Ідеальна домашка",
            "category": "Base",
            "description": "Здай 5 домашніх робіт з першої спроби.",
            "deadline": "2026-09-15 23:59:59",
            "cristals": 20,
        },
        "coins": 20,
        "imageUrl": "mission-base-homework.png",
        "status": "OnReview",
        "date_pending": None,
        "date_rejected": None,
    },
]


# ── Вхідні моделі ────────────────────────────────────────────────────────────


class SetMarkIn(BaseModel):
    """Оцінка новини користувачем: `{news_id, mark}`."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"news_id": 1201, "mark": 5}]})

    news_id: int = Field(description="ID новини з GET /news.")
    mark: int = Field(ge=1, le=5, description="Оцінка від 1 до 5.")


class SetViewTimeIn(BaseModel):
    """Фіксація часу перегляду новини: `{news_id, seconds}`."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"news_id": 1201, "seconds": 42}]})

    news_id: int = Field(description="ID новини з GET /news.")
    seconds: int = Field(ge=0, description="Скільки секунд новина була відкрита.")


# ── News ──────────────────────────────────────────────────────────────────────


@router.get(
    "/news",
    tags=["News"],
    summary="Стрічка новин (page/per_page + заголовки X-Pagination)",
    responses={200: {"description": "Масив новин; пагінація — у заголовках X-Pagination-*."}, 401: {"model": ApiError}},
)
async def news_list(
    request: Request,
    response: Response,
    branch_alias: str,
    page: int = Query(1, ge=1, description="Номер сторінки (з 1)."),
    per_page: int = Query(15, ge=1, le=100, description="Записів на сторінку."),
) -> Any:
    """**GET /v1/mystat/{alias}/news?page=1&per_page=15** ✅⚠️

    Стрічка новин. Реальний URL:
    `https://mystat.itstep.org/v1/mystat/{alias}/news?page=1&per_page=15`.

    - Пагінація **Laravel-стиль**: номер поточної і число сторінок приходять
      **заголовками відповіді** `X-Pagination-Current-Page` / `X-Pagination-Page-count`
      (не в тілі!) — тому обробник оголошує `response: Response`.
    - Елемент списку ⚠️: `{id, title, body, cover, published_at, is_viewed}`;
      `cover` — відносний шлях ассета від origin.
    """
    if MODE == "proxy":
        # Пагінація й X-Pagination-* вже в відповіді upstream — нічого не перераховуємо.
        return await forward(request)
    data = await handle(request, sample=_SAMPLE_NEWS)
    items: list[Any] = data if isinstance(data, list) else []
    last_page = max(1, math.ceil(len(items) / per_page))
    current = min(page, last_page)
    response.headers["X-Pagination-Current-Page"] = str(current)
    response.headers["X-Pagination-Page-count"] = str(last_page)
    return items[(current - 1) * per_page : current * per_page]


@router.get("/news/{news_id:int}", tags=["News"], summary="Новина за ID", responses={404: {"model": ApiError}})
async def news_detail(request: Request, branch_alias: str, news_id: int) -> Any:
    """**GET /v1/mystat/{alias}/news/{id}** ✅⚠️

    Повний об'єкт новини (`{…поля списку}`); 404 — якщо новини немає
    (раніше мок завжди відповідав 200 з чужою новиною під запитаним id).
    """
    found = next((n for n in _SAMPLE_NEWS if n["id"] == news_id), None)
    if found is None and MODE != "proxy":
        raise HTTPException(
            status_code=404,
            detail=[{"field": "news_id", "message": "Новость не найдена"}],
        )
    fallback = _SAMPLE_NEWS[0] | {"id": news_id}
    return await handle(request, sample=next((n for n in _SAMPLE_NEWS if n["id"] == news_id), fallback))


@router.post("/news/set-mark", tags=["News"], summary="Поставити оцінку новини (1..5)")
async def set_mark(body: SetMarkIn, request: Request, branch_alias: str) -> Any:
    """**POST /v1/mystat/{alias}/news/set-mark** ✅⚠️ — body `{news_id, mark}`."""
    return await handle(request, sample={"status": "ok", "news_id": body.news_id, "mark": body.mark})


@router.post("/news/set-view-time", tags=["News"], summary="Надіслати час перегляду новини")
async def set_view_time(body: SetViewTimeIn, request: Request, branch_alias: str) -> Any:
    """**POST /v1/mystat/{alias}/news/set-view-time** ✅⚠️ — body `{news_id, seconds}`.

    Фронт рапортує, скільки секунд новина провисіла відкритою (аналітика переглядів).
    """
    return await handle(request, sample={"status": "ok"})


# ── Missions ──────────────────────────────────────────────────────────────────


@router.get(
    "/missions/get-list",
    tags=["Missions"],
    summary="Список місій (фронт сам ділить на Super/Base)",
    responses={401: {"model": ApiError}},
)
async def missions_list(
    request: Request,
    branch_alias: str,
    category: Optional[Literal["Super", "Base"]] = Query(None, description="⚠️ Фронтом НЕ передається (фільтрує локально); залишено для зручності мока."),
    ctx: AuthCtx = Depends(auth_ctx),
) -> Any:
    """**GET /v1/mystat/{alias}/missions/get-list** ✅

    Реальний шлях — `getMissions()` → `GET ${endpoint}/get-list` = `/missions/get-list`.

    ⚠️ На проді філії `pl` зараз **404** — модуль місій вимкнено.
    Поля елемента ✅ (mapMission з бандла):
    `{id, mission{id,name,category,description,deadline,cristals}, coins, imageUrl,
    status, date_pending, date_rejected}`; енам `MissionStatus`: `OnReview`, `Rejected`.
    """
    data = await handle(request, sample=_SAMPLE_MISSIONS)
    if MODE != "proxy" and category and isinstance(data, list):
        data = [m for m in data if (m.get("mission") or {}).get("category") == category]
    return data


@router.post(
    "/missions/send-to-review/{mission_id}",
    tags=["Missions"],
    summary="Надіслати місію на перевірку",
    responses={401: {"model": ApiError}},
)
async def send_mission_to_review(
    request: Request, branch_alias: str, mission_id: int, ctx: AuthCtx = Depends(auth_ctx)
) -> Any:
    """**POST /v1/mystat/{alias}/missions/send-to-review/{mission_id}** ✅

    `submitMission(t,e)` → `POST /missions/send-to-review/${t}`, тіло `e` ⚠️
    (імовірно коментар/файли відповіді місії).
    Після надсилання статус місії стає `OnReview`; відхилені позначені `Rejected`.
    """
    return await handle(
        request,
        sample={"status": "ok", "mission_status": "OnReview", "id": mission_id},
    )
