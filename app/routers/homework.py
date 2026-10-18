"""§14 Homework (чанки `DngPB5Fy`, `DVtZKYdc`) — домашні завдання та матеріали.

Правила розділу (див. MYSTAT_API.md §14):
- усі шляхи «філійні»: `/v1/mystat/{branch_alias}/…`;
- статуси — **числовий енам з бандла** (НЕ «done/undone»!):

    HomeworkStatus = { Done:1, Examination:2, UntilExecution:3, Retake:5 }

- фільтри списку — точна карта типів параметрів фронта:

    { type:[], spec_id:[], sort, status, overdue, for_last_year, limit, homework_id }

- пагінація списку — заголовки відповіді `X-Pagination-Current-Page` / `X-Pagination-Page-count`.
"""
import math
from datetime import date
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx
from ..models.common import ApiError
from ..proxy import handle

router = APIRouter(prefix="/v1/mystat/{branch_alias}", tags=["Homework"], dependencies=[Depends(auth_ctx)])

# Фіктивний «total» для мока списку.
_TOTAL_HOMEWORK = 42

HOMEWORK_STATUS_DESC = (
    "Числовий енам з бандла: 1=Done, 2=Examination (на перевірці), "
    "3=UntilExecution (до виконання), 5=Retake (відпрацювання). Значення 4 не існує. "
    "Форма відповіді: status=1|2|3 → {data, _meta:{currentPage, totalPages, "
    "totalCount}}; status=5 → МАСИВ секцій [{status, data, _meta}]. "
    "Вкладений homework_stud.status — окремий енам (наживо видні 1 і 6; "
    "6 = не здано: mark=null, нульова creation_time)."
)


# ── Вхідні / допоміжні моделі ─────────────────────────────────────────


class HomeworkType(BaseModel):
    """Тип домашнього завдання (довідник `/homework/types`)."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(description="ID типу роботи.", examples=[1])
    name: str = Field(description="Назва типу (локаль фронтенду).", examples=["Вправа"])


class GroupSpec(BaseModel):
    """Специфікація групи для фільтрів (`/settings/group-specs`). Точний набір полів ⚠️."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(description="ID специфікації.", examples=[101])
    name: str = Field(description="Людськочитабельна назва.", examples=["Основи програмування"])
    type: Optional[str] = Field(default=None, description="Тип елемента фільтра ⚠️.", examples=["subject"])


# ── Приватні помічники ───────────────────────────────────────────────────────

_STATUS_CYCLE = [3, 2, 1, 5]  # UntilExecution / Examination / Done / Retake


def _homework_item(idx: int) -> dict[str, Any]:
    """Елемент списку ДЗ — набір полів підтверджений живою відповіддю
    і шаблоном фронта ✅ (ospr/is_autotest)."""
    status = _STATUS_CYCLE[idx % len(_STATUS_CYCLE)]
    stud_status = 6 if status != 1 else (5 if idx % 4 == 1 else 1)  # ✅ наживо: 1=здано, 6=не здано; 5 (Retake) всередині Done
    done = stud_status == 1
    return {
        "id": 100_000 + idx,
        "id_spec": 2334,
        "id_teach": 112_233_4600 + idx,
        "id_group": 3001,
        "fio_teach": "Мельник Ольга",
        "theme": "Робота зі списками та циклами",
        "completion_time": f"2026-09-{(idx % 26) + 2:02d}",
        "creation_time": f"2026-09-{(idx % 26) + 1:02d}",
        "overdue_time": f"2026-09-{min((idx % 26) + 3, 28):02d}",
        "file_path": None if idx % 3 else "https://fs3.itstep.org/api/v1/files/DEMOFILE",
        "comment": "",
        "name_spec": "Основи програмування",
        "status": status,
        "homework_stud": {
            "id": 150_000 + idx,
            "file_path": None,
            "mark": 11 if done else (None if stud_status == 6 else 10),
            "creation_time": f"2026-09-{(idx % 26) + 2:02d}" if done else "-0001-11-30",
            "stud_answer": "Посилання на рішення студента (демо)." if done else "",
            "auto_mark": False,
            "status": stud_status,
            "photo_pas": "https://fsx1.itstep.org/api/v1/files/DEMOFILE",
            "fio_stud": "Коваленко Олександр Сергійович",
            "related_homeworks": None,
            "related_materials": None,
            # ✅ наживо ці поля приходять РЯДКАМИ:
            "unlock_expire": "0",
            "is_retake": "0",
            "communication_history": (
                [
                    {"type_name": "homework_student_comment", "comment": "Здав рішення (демо).", "date": f"2026-09-{(idx % 26) + 2:02d} 12:50:25", "file": None, "client_filename": None},
                    {"type_name": "homework_teacher_comment", "comment": "", "mark": "11", "date": f"2026-09-{(idx % 26) + 2:02d} 16:05:35", "file": None, "client_filename": None},
                ]
                if done
                else [{"type_name": "homework_student_comment", "comment": "", "date": None, "file": None, "client_filename": None}]
            ),
        },
        "cover_image": None,
        # підтверджено шаблоном DVtZKYdc:
        "ospr": idx % 2,  # 0=independent_work, 1=practice_work
        "is_autotest": 2 if idx % 5 == 0 else 0,  # 2 -> підпис типу «essay»
        "autotest_status": None,
        "autotest_result": None,
        "is_academic_holiday": 0,
    }


def _homework_page(page: int, per_page: int) -> dict[str, Any]:
    """Конверт пагінації — ЯК УЖИВУЮ:
    {"data": […], "_meta": {currentPage, totalPages, totalCount}} + заголовки X-Pagination-*."""
    last_page = max(1, math.ceil(_TOTAL_HOMEWORK / max(per_page, 1)))
    page = min(max(page, 1), last_page)
    start = (page - 1) * per_page
    count = min(per_page, _TOTAL_HOMEWORK - start)
    return {
        "data": [_homework_item(start + i) for i in range(max(count, 0))],
        "_meta": {"currentPage": page, "totalPages": last_page, "totalCount": _TOTAL_HOMEWORK},
    }


# ── Ендпоінти ─────────────────────────────────────────────────────────────────


@router.get(
    "/homework/list",
    summary="Список домашніх робіт (статуси 1|2|3|5, фільтри як у фронта)",
    responses={
        200: {"description": "✅ жива форма: `{data:[…], _meta:{currentPage, totalPages, totalCount}}`; для `status=5` — масив секцій `[{status, data, _meta}]`. Сторінки дублюються заголовками X-Pagination-*."},
        401: {"model": ApiError, "description": "Немає/прострочений Bearer-токен."},
    },
)
async def homework_list(
    request: Request,
    response: Response,
    ctx: AuthCtx = Depends(auth_ctx),
    page: int = Query(default=1, ge=1, description="Номер сторінки (у карті параметрів фронта відсутній — Laravel приймає на беку ⚠️)."),
    limit: int = Query(default=15, ge=1, le=100, description="Записів на сторінку (саме `limit` — з карти типів фронта, НЕ per_page)."),
    status: Optional[int] = Query(
        default=None,
        description=HOMEWORK_STATUS_DESC,
        json_schema_extra={"enum": [1, 2, 3, 5]},
    ),
    type_: Optional[list[int]] = Query(default=None, alias="type[]", description="Фільтр «матеріали»: 1=homeworkAndTests, 2=practicalWord, 3=essay, -1=tests."),
    spec_id: Optional[list[int]] = Query(default=None, alias="spec_id[]", description="Фільтр за специфікаціями (див. /settings/group-specs)."),
    sort: Optional[str] = Query(default=None, description="Сортування ⚠️ (точні значення не спіймані)."),
    overdue: Optional[int] = Query(default=None, ge=0, le=1, description="1=прострочені (`overdue_homework_details`), 0=не прострочені (`not_overdue`)."),
    for_last_year: Optional[int] = Query(default=None, description="Прапорець «за останній рік» (число у фронті)."),
    homework_id: Optional[int] = Query(default=None, description="Конкретна робота."),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/homework/list** ✅⚠️

    Список домашніх робіт (метод фронта `getHomeworks`).

    - **Прод-URL**: `https://mapi.itstep.org/v1/mystat/{alias}/homework/list?status=3&page=1`;
    - **Статуси — числовий енам**: `1=Done, 2=Examination, 3=UntilExecution, 5=Retake`
      (таби UI: «До виконання»→3, «На перевірці»→2, «Виконано»→1);
    - карта параметрів фронта: `type[], spec_id[], sort, status, overdue(0|1),
      for_last_year, limit, homework_id`; `page` у неї не входить, але Laravel-бек його приймає;
    - елемент `data[*]` ✅: `{id, id_spec, id_teach, id_group,
      fio_teach, theme, completion_time, creation_time, overdue_time, file_path,
      comment, name_spec, status, cover_image, ospr(0|1), is_autotest(2→«essay»),
      autotest_status, autotest_result, is_academic_holiday,
      homework_stud{id, file_path, mark, creation_time, stud_answer, auto_mark, status,
      photo_pas, fio_stud, related_homeworks, related_materials, unlock_expire:"0",
      is_retake:"0", communication_history[]}}`.

    > Mock: генерує сторінку з `total=42`, статуси цикляться 3→2→1→5;
    > заголовки `X-Pagination-*` проставляються завжди.
    """
    # Фільтри карти фронта застосовуються ДО пулу з 42 елементів. Раніше вони
    # ігнорувались: status=1 віддав суміш 3/2/1/5, а spec_id[]/type[]/
    # homework_id/overdue не мали ефекту — порушення контракту фільтрів.
    pool = [_homework_item(i) for i in range(_TOTAL_HOMEWORK)]

    if homework_id is not None:
        pool = [x for x in pool if x["id"] == homework_id]
    if spec_id:
        pool = [x for x in pool if x["id_spec"] in spec_id]
    if type_:
        def _matches_type(item: dict[str, Any], t: int) -> bool:
            # (мапінг приблизний — це мок; точні значення не зняті)
            if t == -1:
                return bool(item.get("is_autotest"))
            if t == 3:
                return item.get("is_autotest") == 2
            if t == 2:
                return item.get("ospr") == 0
            return True  # 1 = homeworkAndTests — все

        pool = [x for x in pool if any(_matches_type(x, t) for t in type_)]
    if status is not None and status != 5:
        pool = [x for x in pool if x["status"] == status]
    if overdue is not None:
        today = date.today().isoformat()
        if overdue == 1:
            pool = [x for x in pool
                    if x["status"] == 3
                    and str(x.get("overdue_time") or "") < today]
        else:
            pool = [x for x in pool
                    if not (x["status"] == 3
                            and str(x.get("overdue_time") or "") < today)]

    def _paginate(items: list[dict[str, Any]]) -> dict[str, Any]:
        lp = max(1, math.ceil(len(items) / max(limit, 1)))
        pg = min(max(page, 1), lp)
        start = (pg - 1) * limit
        return {
            "data": items[start:start + limit],
            "_meta": {"currentPage": pg, "totalPages": lp,
                      "totalCount": len(items)},
        }

    if status == 5:
        # ✅ ОСОБЛИВІСТЬ ПРОДА: status=5 приходить МАСИВОМ секцій
        # [{status, data, _meta}], а не об'єктом-конвертом.
        sample: Any = [{"status": s, **_paginate([x for x in pool
                                                  if x["status"] == s])}
                       for s in (3, 5)]
    else:
        sample = _paginate(pool)
    payload = await handle(request, sample=sample)

    # заголовки пагінації — від ФІЛЬТРОВАНОГО total, а не від «42»
    last_page = max(1, math.ceil(len(pool) / max(limit, 1)))
    headers = {
        "X-Pagination-Current-Page": str(min(max(page, 1), last_page)),
        "X-Pagination-Page-count": str(last_page),
    }
    if isinstance(payload, Response):  # proxy-режим: доповнити заголовки готової відповіді
        for key, value in headers.items():
            payload.headers.setdefault(key, value)
        return payload
    response.headers.update(headers)
    return payload


@router.get(
    "/homework/materials",
    summary="Матеріали до домашніх робіт (фільтр type[]: 1/2/3/-1)",
    responses={
        200: {"description": "Список матеріалів ⚠️."},
        401: {"model": ApiError},
    },
)
async def homework_materials(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    type_: Optional[list[int]] = Query(default=None, alias="type[]", description="1=homeworkAndTests, 2=practicalWord, 3=essay, -1=tests."),
    homework_id: Optional[int] = Query(default=None, description="ID домашнього завдання."),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/homework/materials** ✅⚠️

    Матеріали (метод `getMaterials(params)`); фронт ділить їх на «домашки» і «тести»
    за фільтром `type[]` (значення `-1` = тести).

    - **Прод-URL**: `https://mapi.itstep.org/v1/mystat/{alias}/homework/materials?type[]=1`;
    - тіло відповіді ⚠️: список `{id, title, type, files:[{id,name,url}], created_at}`.
    """
    return await handle(
        request,
        sample=[
            {
                "id": 555_001,
                "title": "Умова задачі (PDF)",
                "type": "file",
                "files": [{"id": 700_100, "name": "task.pdf", "url": "https://fsx3.itstep.org/api/v1/files/task"}],
                "created_at": "2026-09-01T10:00:00.000Z",
            },
            {
                "id": 555_002,
                "title": "Розбір на відеоуроці",
                "type": "video",
                "files": [],
                "created_at": "2026-09-02T12:30:00.000Z",
            },
        ],
    )


@router.get(
    "/homework/types",
    summary="Довідник типів домашніх робіт",
    responses={200: {"model": list[HomeworkType]}, 401: {"model": ApiError}},
)
async def homework_types(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/homework/types** ✅

    Типи робіт для фільтрів списку (`getHomeworkTypes()`).

    - **Прод-URL**: `https://mapi.itstep.org/v1/mystat/{alias}/homework/types`;
    - відповідь: плоский список `[{"id":1,"name":"Вправа"}, …]`.
    """
    return await handle(
        request,
        sample=[
            {"id": 1, "name": "Вправа"},
            {"id": 2, "name": "Домашнє завдання"},
            {"id": 3, "name": "Самостійна робота"},
            {"id": 4, "name": "Контрольна робота"},
        ],
    )


@router.get(
    "/settings/group-specs",
    summary="Специфікації групи (для фільтрів)",
    responses={200: {"model": list[GroupSpec]}, 401: {"model": ApiError}},
)
async def group_specs(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/settings/group-specs** ✅⚠️

    Специфікації групи — джерело значень для `spec_id[]` списку ДЗ.

    - **Прод-URL**: `https://mapi.itstep.org/v1/mystat/{alias}/settings/group-specs`;
    - тіло відповіді ⚠️: список `{id, name, type, …}`.
    """
    return await handle(
        request,
        sample=[
            {"id": 101, "name": "Основи програмування", "type": "subject"},
            {"id": 102, "name": "Python Advanced", "type": "subject"},
            {"id": 103, "name": "Модуль 1", "type": "module"},
        ],
    )


@router.post(
    "/homework/create",
    summary="Здати роботу: коментар + файли (multipart/form-data), ліміт файлу 25 МБ",
    responses={
        200: {"description": "Результат здачі ⚠️ ({status, homework_id, uploaded[…]})."},
        401: {"model": ApiError},
    },
)
async def homework_create(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    comment: str = Form(default="", description="Коментар студента до рішення."),
    files: Optional[list[UploadFile]] = File(default=None, description="Файли рішення; ліміт одного файлу 25 МБ (константа з бандла)."),
) -> Any:
    """**POST /v1/mystat/{branch_alias}/homework/create** ✅⚠️

    Здача рішення (`sendHomework(body, params)`): `multipart/form-data`,
    поля `comment` + `files[]`.

    - **Прод-URL**: `https://mapi.itstep.org/v1/mystat/{alias}/homework/create`;
    - файли кладуться в каталог **`homeworkDirId`** з file-token (§8);
    - ліміт розміру файлу **25 МБ** (`25*1024*1024`) — константа з чанка;
    - тіло відповіді ⚠️: `{status:"ok", homework_id, uploaded:[{name,size}]}`.
    """
    uploaded = [
        {"name": f.filename or f"file-{i}", "size": getattr(f, "size", None) or 0}
        for i, f in enumerate(files or [], start=1)
    ]
    return await handle(
        request,
        sample={"status": "ok", "homework_id": 100_043, "comment": comment, "uploaded": uploaded},
    )


@router.delete(
    "/homework/delete/{homework_id}",
    summary="Видалити здане рішення",
    responses={200: {"description": "Підтвердження видалення ⚠️."}, 401: {"model": ApiError}},
)
async def homework_delete(homework_id: int, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**DELETE /v1/mystat/{branch_alias}/homework/delete/{id}** ✅⚠️

    Видалення зданого рішення (`deleteHomework(id, params)`).

    - **Прод-URL**: `https://mapi.itstep.org/v1/mystat/{alias}/homework/delete/12345`;
    - після видалення робота повертається в статус `UntilExecution=3` ⚠️.
    """
    return await handle(request, sample={"status": "ok", "deleted": homework_id})


@router.get(
    "/materials/id/{material_id}",
    summary="Матеріал за числовим ID",
    responses={200: {"description": "Об'єкт матеріалу ⚠️."}, 401: {"model": ApiError}},
)
async def material_by_id(material_id: int, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/materials/id/{id}** ✅⚠️

    Картка матеріалу за числовим ідентифікатором (`getMaterial(b)`
    — шлях БЕЗ префікса `/homework`, від кореня гілки).

    - **Прод-URL**: `https://mapi.itstep.org/v1/mystat/{alias}/materials/id/555001`;
    - порівняй з UUID-варіантом `materials/uuid/{uuid}/{sub}` із §14.
    """
    return await handle(
        request,
        sample={
            "id": material_id,
            "title": "Конспект лекції №5",
            "type": "file",
            "url": "https://fsx3.itstep.org/api/v1/files/DEMOFILE",
            "created_at": "2026-09-03T09:00:00.000Z",
        },
    )


@router.get(
    "/homework/{homework_id}",
    summary="Картка домашньої роботи за ID (getHomeworkInfo)",
    responses={200: {"description": "Об'єкт роботи ⚠️."}, 401: {"model": ApiError}},
)
async def homework_info(homework_id: int, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/homework/{id}** ✅

    Фронт: `getHomeworkInfo(b)` → `GET /homework/${b}`.

    - **Прод-URL**: `https://mapi.itstep.org/v1/mystat/{alias}/homework/100001`;
    - тіло відповіді ⚠️: розширений об'єкт роботи (умова, файли рішення,
      `homework_stud{…}`, коментар викладача) — точна структура не знімалася.

    > Маршрут оголошений ПІСЛЯ статичних `/homework/list|materials|types`,
    > інакше FastAPI з'їв би їх у `{id}` (урок з files.py).
    """
    item = _homework_item(homework_id % _TOTAL_HOMEWORK)
    item["id"] = homework_id
    return await handle(request, sample=item)
