"""§14 Schedule — розклад.

Усі шляхи філійні: `/v1/mystat/{alias}/schedule/*`, як і решта API.
Структури відповідей відповідають живому API (`get-month`, `get-existing-schedule`,
`/video/link`, `/gaming/achieve-info/{id}`).
"""
import calendar
from datetime import date, timedelta
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx
from ..fixtures import FixtureNotFound, fixture
from ..models.common import ApiError
from ..proxy import MODE, handle

router = APIRouter(prefix="/v1/mystat/{branch_alias}", tags=["Schedule"], dependencies=[Depends(auth_ctx)])


# ── Моделі відповідей (за живими даними) ─────────────────────────────────────────


class ScheduleLesson(BaseModel):
    """Урок із get-month. Повний набір полів підтверджений живою відповіддю 🟢."""

    model_config = ConfigDict(extra="allow")

    schedule_id: int = Field(description="ID запису розкладу.", examples=[708228])
    date: str = Field(examples=["2026-05-30"])
    lesson: int = Field(description="Номер пари за день.", examples=[6])
    started_at: str = Field(examples=["15:20:00"])
    finished_at: str = Field(examples=["16:40:00"])
    teacher_name: Optional[str] = Field(default=None, examples=["Викладач Демо"])
    subject_name: Optional[str] = Field(default=None, examples=["Основи програмування"])
    room_name: Optional[str] = Field(default=None, examples=["201 ауд."])
    mark: Optional[Any] = None
    mark_type: Optional[Any] = None
    homeworks: list[Any] = Field(default_factory=list)
    was: Optional[int] = Field(default=None, description="Відвідування: 0/1.")
    lesson_theme: Optional[str] = Field(default=None, examples=["Вступ до циклів"])
    id_spec: Optional[int] = None
    week_day: Optional[str] = Field(default=None, description="День тижня рядком ('1'..'7').")
    task_id: Optional[int] = Field(default=None)
    attendance: Optional[str] = Field(default=None, examples=["67"])
    video_link: Optional[str] = None


class ScheduleMonth(BaseModel):
    """Конверт відповіді get-month 🟢."""

    model_config = ConfigDict(extra="allow")

    data: list[ScheduleLesson]
    start_day: str = Field(examples=["2026-05-25"], description="Понеділок запитаного тижня.")
    end_date: str = Field(examples=["2026-05-31"])
    first_visit_day: str = Field(examples=["2023-10-14"])
    last_visit_day: str = Field(examples=["2026-05-30"])


class ExistingSchedule(BaseModel):
    """Конверт get-existing-schedule 🟢."""

    model_config = ConfigDict(extra="allow")

    schedule: list[dict[str, Any]] = Field(
        description='[{date:"2026-08-01", is_holiday:true} …] на рік уперед.',
    )
    days_until_start_of_holiday: Optional[int] = Field(
        default=None, alias="daysUntilStartOfHoliday"
    )
    exams: list[Any] = Field(default_factory=list)


# ── Ендпоінти ────────────────────────────────────────────────────────────────


@router.get(
    "/schedule/get-existing-schedule",
    summary="Календар робочих днів/свят (+ екзамени)",
    response_model=ExistingSchedule,
    responses={200: {"description": "🟢 структура за живою відповіддю"}, 401: {"model": ApiError}},
)
async def existing_schedule(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    return await handle(request, fixture_name="schedule-existing.json")


@router.get(
    "/schedule/get-month",
    summary="Розклад за тиждень або місяць",
    response_model=ScheduleMonth,
    responses={200: {"description": "🟢 структура за живою відповіддю"}, 401: {"model": ApiError}},
)
async def get_month(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    type: Literal["week", "month"] = Query(default="week", description='Тип вибірки: тиждень або місяць.'),
    date_filter: str = Query(
        description="Опорна дата YYYY-MM-DD: для type=week — ПОНЕДІЛОК тижня; для month — будь-яке/1-ше число.",
        examples=["2026-05-25"],
    ),
) -> Any:
    """**GET /v1/mystat/{alias}/schedule/get-month?type=week&date_filter=2026-05-25** 🟢

    Головний ендпоінт сітки розкладу (вкладка «Розклад»).

    - `type=week` — тиждень, `date_filter` = понеділок;
      `type=month` — місяць, `date_filter` = 1-ше число (перевірено наживо).
    - Відповідь: `{data:[уроки…], start_day, end_date, first_visit_day, last_visit_day}`.
    - Уроки несуть відвідуваність (`was`, `attendance`), оцінку (`mark/mark_type/mark_comments`),
      ДЗ (`homeworks[]`), коментар куратора про відвідування (`task_attendance_comment`)
      і викладача цілком (`task_attendance_comment_created_by`, фото через файловий сервіс).

    > Mock: уроки беруться з фікстури; дни поза фікстурним тижнем — порожні,
    > але start_day/end_date обчислюються з date_filter (раніше на БУДЬ-ЯКУ
    > дату віддавався той самий фікстурний тиждень — розбіжність
    > відповіді із запитом).
    """
    try:
        anchor = date.fromisoformat(str(date_filter)[:10])
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=[{"field": "date_filter",
                     "message": "date_filter must be ISO YYYY-MM-DD"}],
        ) from None

    if type == "week":
        start_day = anchor - timedelta(days=anchor.weekday())
        end_day = start_day + timedelta(days=6)
    else:
        start_day = anchor.replace(day=1)
        last_day = calendar.monthrange(anchor.year, anchor.month)[1]
        end_day = anchor.replace(day=last_day)

    fixture_data: list[dict[str, Any]] = []
    first_visit_day = last_visit_day = ""
    if MODE != "proxy":
        try:
            fix = fixture("schedule-week.json")
            fixture_data = fix.get("data") if isinstance(fix, dict) else None
            first_visit_day = fix.get("first_visit_day") if isinstance(fix, dict) else None
            last_visit_day = fix.get("last_visit_day") if isinstance(fix, dict) else None
        except FixtureNotFound:
            fixture_data = None
        if not isinstance(fixture_data, list):
            fixture_data = []
        # (уроки залишаємо лише всередині запитаного діапазону: мок зберігає
        # один живий тиждень, поза ним даних немає)
        fixture_data = [l for l in fixture_data
                        if isinstance(l, dict)
                        and str(l.get("date") or "")[:10] >= start_day.isoformat()
                        and str(l.get("date") or "")[:10] <= end_day.isoformat()]

    return await handle(
        request,
        sample={
            "data": fixture_data or [],
            "start_day": start_day.isoformat(),
            "end_date": end_day.isoformat(),
            "first_visit_day": first_visit_day or start_day.isoformat(),
            "last_visit_day": last_visit_day or end_day.isoformat(),
        },
    )


@router.get(
    "/video/link",
    summary="Посилання на відеотрансляцію уроку (?id_schedule=)",
    responses={200: {"description": '`{"link":"…"}`'}, 401: {"model": ApiError}},
)
async def video_link(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    id_schedule: int = Query(description="ID запису розкладу (lesson.id_schedule) — підтверджено бандлом."),
) -> Any:
    """**GET /v1/mystat/{alias}/video/link?id_schedule={id_schedule}** ✅🟢

    Маршрут — літерал `/video/link` **БЕЗ префікса `/schedule`**: на неіснуючому
    `id_schedule` сервер відповідає **422**, а варіант `/schedule/video/link` дає 404.
    Відповідь `{link}` підставляється в broadcast-плеєр; обрив стріму → retry getVideoLink до 2 разів.
    """
    return await handle(request, sample={"link": f"https://s.itstep.org/live/{id_schedule}/index.m3u8"})


@router.get(
    "/gaming/achieve-info/{achievement_id}",
    summary="Прогрес досягнення (гейміфікація)",
    responses={
        200: {"description": "⚠️ структура тіла не зафіксована"},
        401: {"model": ApiError, "description": "ендпоінт існує (без токена — 401)"},
    },
)
async def achieve_info(achievement_id: int, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{alias}/gaming/achieve-info/{id}** 🟢

    Прогрес досягнення в гейміфікації. Фронт викликає літералом
    `/kiev/gaming/achieve-info/{id}` — city-префікс захардкоджений.
    На неіснуючому `id` сервер відповідає **500**: потрібен реальний id досягнень
    (джерело — GET /utility/statistic/achievements). Тіло відповіді ⚠️.
    """
    return await handle(
        request,
        sample={"id": achievement_id, "name": "Перші кроки", "current_step": 3, "max_step": 10},
    )
