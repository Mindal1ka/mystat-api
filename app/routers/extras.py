"""Сервіси дашборда та «іншого»: Statistic · Contacts+Signal · Payment · Club ·
Nutrition (+students/get-qr-code) · Library · Reviews · Students.

Шляхи ✅ взяті з викликів `getEndpoint(...)` у чанках фронтенду; структури відповідей
звірені з живими пробами реального акаунта (2026-08-24): конверти, типи полів
(зокрема рядкові числа) та порожні форми збігаються з продом. Значення в прикладах —
демонстраційні фікції, що не стосуються реальних акаунтів.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx
from ..models.common import ApiError
from ..proxy import handle

router = APIRouter(
    prefix="/v1/mystat/{branch_alias}",
    tags=["Dashboard & Stats", "Contacts", "Payments+", "Club", "Nutrition", "Library"],
    dependencies=[Depends(auth_ctx)],
)

_FS = "https://fsx3.itstep.org/api/v1/files/DEMOFILE"


class Loose(BaseModel):
    """Довільний JSON (extra=allow) — для тіл, структура яких ще ⚠️."""

    model_config = ConfigDict(extra="allow")


class EvaluateLessonIn(BaseModel):
    """Оцінка заняття та викладача. Поля підтверджені кодом фронта ✅:

    `{mark_lesson: 1..5, mark_teach: 1..5, comment: str, id: <evaluation_lesson_id>}`."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"mark_lesson": 5, "mark_teach": 5, "comment": "Дуже змістовне заняття!", "id": 123456}]})

    mark_lesson: int = Field(ge=1, le=5, description="Оцінка заняття (зірки 1–5).", examples=[5])
    mark_teach: int = Field(ge=1, le=5, description="Оцінка викладача (зірки 1–5).", examples=[5])
    comment: str = Field(default="", description="Коментар; за будь-якої оцінки <=3 фронт вимагає >=6 символів.")
    id: int = Field(description="evaluation_lesson_id з payload сокет-події socket_notification_handler → data.evaluation_lesson_id (НЕ id самого повідомлення).", examples=[123456])


# ── Dashboard / Statistic / Progress ─────────────────────────────────────────


@router.get("/count/homework", summary="Лічильники ДЗ для дашборда", tags=["Dashboard & Stats"])
async def count_homework(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/count/homework** ✅🟢 (`getHomeworkCount(params)`)

    Жива форма: плоский масив `[{counter_type, counter}]` — 6 лічильників за табами ДЗ;
    останній (counter_type=6) — загальна кількість виконаних робіт.
    """
    return await handle(request, sample=[
        {"counter_type": 1, "counter": 4},
        {"counter_type": 2, "counter": 0},
        {"counter_type": 3, "counter": 6},
        {"counter_type": 4, "counter": 0},
        {"counter_type": 5, "counter": 2},
        {"counter_type": 6, "counter": 114},
    ])


def _require_period(period: Optional[str]) -> str:
    """Прод відповідає 400 без `period` (жива перевірка); повторюємо цю поведінку."""
    if not period:
        raise HTTPException(
            status_code=400,
            detail=[{"field": "period", "message": "Обов'язковий параметр period (month | half_year | year)"}],
        )
    return period


def _attendance_month(days: int) -> dict[str, Any]:
    return {str(d): {"was": [], "visits": []} for d in range(1, days + 1)}


@router.get("/statistic/attendance", summary="Відвідуваність (вимагає period)", tags=["Dashboard & Stats"])
async def statistic_attendance(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    period: Optional[str] = Query(default=None, description="Період вибірки: month | half_year | year. БЕЗ нього прод відповідає 400."),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/statistic/attendance?period=month** ✅🟢 (`getAttendance(params)`)

    - **Query**: `period` — обов'язковий (жива перевірка: без нього 400);
    - відповідь: `data` — вкладеність `<рік>.<місяць>.<день> → {was:[], visits:[]}`
      (місяці й дни СТРІЧКОВИМИ ключами), плюс зведені відсотки й тренди:
      `percentOfAttendance`, `countAbsent`, `percentOfAbsent`, `percentOfLate`,
      `attendanceChange` / `lateChange` (енам: unchanged/up/down).
    """
    _require_period(period)
    return await handle(request, sample={
        "data": {
            "2026": {
                "7": _attendance_month(31),
                "8": _attendance_month(31),  # серпень — 31 день (був 24: обрізане «сьогодні»)
            }
        },
        "percentOfAttendance": 0,
        "countAbsent": 0,
        "percentOfAbsent": 0,
        "percentOfLate": 0,
        "attendanceChange": "unchanged",
        "lateChange": "unchanged",
    })


@router.get("/statistic/marks", summary="Оцінки (без period віддає великий зріз)", tags=["Dashboard & Stats"])
async def statistic_marks(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    period: Optional[str] = Query(default=None, description="Опціональний: без period жива відповідь ~94 КБ (повний зріз)."),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/statistic/marks** ✅🟢 (`getRates(params)`)

    Жива форма для студента без оцінок за обраний період — голий МАСИВ `[]`
    (не об'єкт!). Наповнена форма елемента ⚠️ — зняти перехопленням трафіку.
    """
    return await handle(request, sample=[])


@router.get("/statistic/progress", summary="Прогрес за предметами (вимагає period)", tags=["Dashboard & Stats"])
async def statistic_progress(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    period: Optional[str] = Query(default=None, description="Період вибірки: month | half_year | year. БЕЗ нього прод відповідає 400."),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/statistic/progress?period=half_year** ✅🟢 (`getProgress(params)`)

    - **Query**: `period` — обов'язковий (без нього 400);
    - відповідь: `{data:[{chart_type, chart_models[], average_point, prev_average_point}],
      total_average_point, prev_total_average_point}`;
    - `chart_models[*] = {date: "YYYY-MM-01", points, previous_points|null, has_rasp}`
      — точки графіка за місяцями; кілька блоків з різними chart_type (3, 5 …).
    """
    _require_period(period)
    models = lambda pts: [  # noqa: E731
        {"date": d, "points": p, "previous_points": prev, "has_rasp": False}
        for d, p, prev in pts
    ]
    return await handle(request, sample={
        "data": [
            {
                "chart_type": 3,
                "chart_models": models([
                    ("2026-01-01", 11, None), ("2026-02-01", 12, 11), ("2026-03-01", 12, 12),
                    ("2026-04-01", 11, 12), ("2026-05-01", 12, 11), ("2026-06-01", None, 12),
                ]),
                "average_point": 11.7,
                "prev_average_point": 9,
            },
            {
                "chart_type": 5,
                "chart_models": models([
                    ("2026-01-01", 10, None), ("2026-02-01", 11, 10), ("2026-03-01", 11, 11),
                    ("2026-04-01", 12, 11), ("2026-05-01", 11, 12), ("2026-06-01", None, 11),
                ]),
                "average_point": 11.0,
                "prev_average_point": 8,
            },
        ],
        "total_average_point": 11.85,
        "prev_total_average_point": 11,
    })


def _avg_spec(idx: int) -> dict[str, Any]:
    """Елемент average-by-specs — ЯК УЖИВУЮ: багато чисел приходять РЯДКАМИ."""
    base = 988 + idx * 111
    return {
        "id_spec": str(base),
        "name_spec": ["Розробка додатків на Python", "Основи програмування", "Веб-розробка"][idx % 3],
        "image": None,
        "avg": 11.3,
        "opened_homework_count": "0",
        "expired_homework_count": str(idx % 5),
        "inspection_homework_count": "0",
        "attendance": str(60 + idx * 7),
        "all_attendance": str(60 + idx * 7),
        "exam": {"date_start": "2026-05-20", "id_spec": str(base), "mark": "12"} if idx == 0 else None,
        "lesson_amount": "12",
        "all_lesson_amount": "12",
        "avg_classwork": "11.3",
        "avg_homework": "11.0",
        "avg_controlwork": 0,
        "avg_thematicwork": "12.0",
        "avg_exams": 0,
        "teachers": ["Викладач Демо", "Мельник Ольга"][: 1 + idx % 2],
        "lesson_period_start": "2026-02-07",
        "lesson_period_end": "2026-05-30",
    }


@router.get("/statistic/average-by-specs", summary="Середні за специфікаціями", tags=["Dashboard & Stats"])
async def average_by_specs(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/statistic/average-by-specs** ✅🟢 (`getSubjectsProgress`)

    Масив специфікацій з успішністю. ВАЖЛИВО: більшість числових полів приходять
    РЯДКАМИ (`id_spec:"988"`, `attendance:"67"`, `mark:"12"`) — парсер фронта чекає саме це.
    """
    return await handle(request, sample=[_avg_spec(i) for i in range(3)])


@router.get("/statistic/get-spec/{spec_id}", summary="Специфікація за ID", tags=["Dashboard & Stats"])
async def get_spec(spec_id: int, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/statistic/get-spec/{id}** ✅🟢

    Усі поля — РЯДКИ. Жива форма: `{id_spec:"1", name_spec:"Програмування
    мовою C", short_name_spec:"C", id_form:"4", id_dir:"13", status:"1"}`.
    Виклик фронта: `getSpec(t)` — `${endpoint}/get-spec/${t}`.
    """
    return await handle(request, sample={
        "id_spec": str(spec_id),
        "name_spec": "Програмування мовою C",
        "short_name_spec": "C",
        "id_form": "4",
        "id_dir": "13",
        "status": "1",
    })


@router.get("/progress/activity", summary="Активність/історія нарахувань (new_format=1)", tags=["Dashboard & Stats"])
async def progress_activity(
    request: Request,
    new_format: int = Query(default=1, description="Фронт завжди шле `new_format=1`; відповідь читає ЗАГОЛОВКИ пагінації."),
    ctx: AuthCtx = Depends(auth_ctx),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/progress/activity?new_format=1** ✅🟢

    `getBillingHistory` викликають з `observe:'response'` — клієнт розбирає заголовки.

    Відповідь — плоский масив подій нарахувань: `{id, created_at(ISO Z),
    lesson_name|null, name:"rule_name_*", icon(URL), award_value, award_alias,
    mark|null, mark_type|null, awards:[{award_alias, award_value}]}`.
    """
    return await handle(request, sample=[
        {
            "id": 4300101,
            "created_at": "2026-06-04T14:40:22.000000Z",
            "lesson_name": None,
            "name": "rule_name_refund_in_shop",
            "icon": _FS,
            "award_value": 84,
            "award_alias": "cristals",
            "mark": None,
            "mark_type": None,
            "awards": [
                {"award_alias": "cristals", "award_value": 84},
                {"award_alias": "coins", "award_value": 196},
            ],
        },
        {
            "id": 4300102,
            "created_at": "2026-06-11T09:12:45.000000Z",
            "lesson_name": "Робота з масивами",
            "name": "rule_name_homework_mark",
            "icon": _FS,
            "award_value": 15,
            "award_alias": "coins",
            "mark": 12,
            "mark_type": "homework",
            "awards": [{"award_alias": "coins", "award_value": 15}],
        },
    ])


def _leader(name: str, pos: int, amount: int, *, new: bool = False, pos_mandatory: bool = True) -> dict[str, Any]:
    el: dict[str, Any] = {
        "id_stud": str(14000 + pos * 7),
        "fio_stud": name,
        "photo": _FS,
        "group_id": "100001",
        "group_start": None if new else "2025-09-14",
        "stud_start": "2026-08-21" if new else "2025-09-07",
        "is_new": new,
        "amount": amount,
    }
    if pos_mandatory:
        el["position"] = pos
    return el


@router.get("/progress/leader-table", summary="Таблиця лідерів (група + потік)", tags=["Dashboard & Stats"])
async def leader_table(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/progress/leader-table** ✅🟢

    Вкладеність: `{group|stream} → {month|all_time} → {new_students, top, other}`;
    елемент: `{id_stud(рядок!), fio_stud, photo, group_id(рядок), group_start,
    stud_start, is_new, amount, position}`. У новачків (`new_students`) поля
    `position` немає, а `group_start` буває null. Плюс прапорець `sliding_rating`.
    """
    return await handle(request, sample={
        "group": {
            "month": {
                "new_students": [],
                "top": [
                    _leader("Ткаченко Марія Олександрівна", 1, 174),
                    _leader("Бондаренко Артем Ігорович", 2, 158),
                    _leader("Коваленко Олександр Сергійович", 3, 141),
                ],
                "other": [_leader("Шевченко Данило Юрійович", 11, 110)],
            },
            "all_time": {
                "new_students": [],
                "top": [
                    _leader("Ткаченко Марія Олександрівна", 1, 2471),
                    _leader("Бондаренко Артем Ігорович", 2, 2205),
                    _leader("Коваленко Олександр Сергійович", 3, 1980),
                ],
                "other": [_leader("Шевченко Данило Юрійович", 10, 1679)],
            },
        },
        "stream": {
            "month": {
                "new_students": [_leader("Гончар Софія Вікторівна", 0, 151, new=True, pos_mandatory=False)],
                "top": [
                    _leader("Руденко Микита Павлович", 1, 224),
                    _leader("Литвин Аліна Дмитрівна", 2, 210),
                    _leader("Кравець Богдан Олегович", 3, 190),
                ],
                "other": [_leader("Савченко Єгор Антонович", 60, 67)],
            },
            "all_time": {
                "new_students": [_leader("Гончар Софія Вікторівна", 0, 2043, new=True, pos_mandatory=False)],
                "top": [
                    _leader("Руденко Микита Павлович", 1, 3399),
                    _leader("Литвин Аліна Дмитрівна", 2, 3105),
                    _leader("Кравець Богдан Олегович", 3, 2870),
                ],
                "other": [_leader("Савченко Єгор Антонович", 54, 1588)],
            },
        },
        "sliding_rating": False,
    })


@router.get("/progress/leader-points", summary="Позиція студента в рейтингу", tags=["Dashboard & Stats"])
async def leader_points(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/progress/leader-points** ✅🟢 (`getLeaderPoints(params)`)

    Жива форма: `{group:{totalCount, studentPosition, weekDiff, monthDiff},
    stream:{…ті самі поля}}`.
    """
    return await handle(request, sample={
        "group": {"totalCount": 14, "studentPosition": 12, "weekDiff": 0, "monthDiff": 0},
        "stream": {"totalCount": 86, "studentPosition": 58, "weekDiff": 0, "monthDiff": 0},
    })


class AnalyzePerfIn(BaseModel):
    spec: int = Field(description="id_spec предмета (з /statistic/average-by-specs або /statistic/get-spec).")


@router.post("/progress/analyze-performance", summary="Аналіз успішності (POST {spec})", tags=["Dashboard & Stats"])
async def analyze_performance(body: AnalyzePerfIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/progress/analyze-performance** ✅ — тіло знято з фронта.

    Діалог фронта (app-analyze-performance-dialog): `init(){ let t={spec:this.data.idSpec};
    …getAnalyzePerformance(t) }` → body рівно `{spec:<id_spec>}`. Відповідь фронт проганяє
    через парсер блоків — UI малює список секцій index/title; точна структура ⚠️.
    """
    return await handle(request, sample=[
        {"title": "Сильні теми", "index": 1, "text": "Цикли й умови засвоєно на 90%"},
        {"title": "Стоит повторить", "index": 2, "text": "Указатели и память — 54%"},
    ])


@router.get("/gaming/is-star", summary="Зірка тижня/місяця", tags=["Dashboard & Stats"])
async def is_star(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/gaming/is-star** ✅🟢 (`getMonthWeekStar()`)

    Жива форма: `{week:{result, total_coins, total_cristals}, month:{…}}`.
    """
    return await handle(request, sample={
        "week": {"result": False, "total_coins": 0, "total_cristals": 0},
        "month": {"result": False, "total_coins": 0, "total_cristals": 0},
    })


# ── Contacts + Signal ────────────────────────────────────────────────────────


@router.get("/contacts", summary="Контакти філії (адреса, телефони, соцмережі)", tags=["Contacts"])
async def contacts(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/contacts** ✅🟢 (`getContacts(params)`)

    Жива форма — ОБ'ЄКТ (не масив!): адреси з телефонами (`adress[].adress_name /
    learning_tel / tel_room / tel_tel_book`), навчальна частина (`teach_main[].teachMain_name,
    href_teach`), плоскі списки `learning_tel / tel_room / tel_book`, сайт/пошта
    (`site_shag / mail_shag`), соцмережі (`facebook / youtube / vk / instagram / twitter`,
    відсутні = null), мапи (`google_maps`, `google_plus`), `teach_contacts[]`.
    Телефони — рядки цифр БЕЗ "+" (наприклад "380990000001").
    """
    return await handle(request, sample={
        "adress": [{
            "adress_name": "вул. Навчальна, 1",
            "learning_tel": ["380990000001"],
            "tel_room": ["380990000002"],
            "tel_book": ["380990000003"],
        }],
        "learning_tel": ["380990000001", "380990000002"],
        "teach_main": [{"teachMain_name": "Навчальна частина", "href_teach": ["edu_demo@itstep.org"]}],
        "href_teach": ["edu_demo@itstep.org"],
        "tel_room": ["380990000002", "380990000004"],
        "tel_book": ["380990000003"],
        "tel_economists": None,
        "site_shag": ["demo.itstep.org"],
        "mail_shag": ["office_demo@itstep.org"],
        "vk": None,
        "facebook": ["https://www.facebook.com/itstep.demo"],
        "instagram": None,
        "youtube": ["https://www.youtube.com/@itstep-demo"],
        "twitter": None,
        "google_maps": [],
        "google_plus": [],
        # Живий шейп елемента (знято 2026-09, examples/live/contacts.json):
        # лише id_teach:int і fio_teach:str — телефонів/пошти у викладачів
        # НЕМАЄ (вони живуть у teach_main[].href_teach і learning_tel тощо)
        "teach_contacts": [
            {"id_teach": 200001, "fio_teach": "Викладач Демо"},
            {"id_teach": 1122334649, "fio_teach": "Другий Викладач"},
        ],
    })


@router.post("/contacts/send-ceo", summary="Написати директору", tags=["Contacts"])
async def send_ceo(body: Loose, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/contacts/send-ceo** ✅⚠️ — тіло (тема/текст) не спіймано."""
    return await handle(request, sample={"status": "sent"})


@router.post("/contacts/send-teach", summary="Написати викладачу", tags=["Contacts"])
async def send_teach(body: Loose, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/contacts/send-teach** ✅⚠️ — тіло не спіймано."""
    return await handle(request, sample={"status": "sent"})


@router.get("/contacts/get-reference-status", summary="Статус запиту довідки (голий boolean)", tags=["Contacts"])
async def reference_status(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/contacts/get-reference-status** ✅🟢

    Жива відповідь — ГОЛИЙ `true` / `false` (не об'єкт!): чи запитував студент довідку.
    """
    return await handle(request, sample=True)


@router.get(
    "/contacts/get-reference-data",
    summary="Завантажити довідку (responseType=blob, ?type=1)",
    responses={200: {"description": "Файл (blob) — на проді PDF ⚠️."}},
    tags=["Contacts"],
)
async def reference_data(
    request: Request,
    type_: int = Query(default=1, alias="type", description="Тип довідки; фронт завжди шле type=1."),
    ctx: AuthCtx = Depends(auth_ctx),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/contacts/get-reference-data?type=1** ✅⚠️

    Завантаження довідки: фронт запитує з `responseType:'blob'`.
    Mock повертає текстову заглушку замість бінарного файлу.
    """
    from fastapi import Response as FastResponse

    payload = await handle(request, sample=None)
    if isinstance(payload, FastResponse):
        return payload
    return FastResponse(
        content="PDF-MOCK: довідка з місця навчання (type=%d)" % type_,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="reference.pdf"'},
    )


@router.get("/signal/problems-list", summary="Список типів проблем (для сигналу)", tags=["Contacts"])
async def problems_list(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/signal/problems-list** ✅🟢

    Жива форма: масив `{id, title}` (саме `title`, НЕ `name`).
    """
    return await handle(request, sample=[
        {"id": 1, "title": "Скарги"},
        {"id": 2, "title": "Помилка оплати"},
        {"id": 3, "title": "Технічні проблеми"},
        {"id": 4, "title": "Інше"},
    ])


@router.post("/signal", summary="Надіслати сигнал про проблему", tags=["Contacts"])
async def send_signal(body: Loose, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/signal** ✅⚠️ — тіло не спіймано."""
    return await handle(request, sample={"status": "received"})


# ── Payment ──────────────────────────────────────────────────────────────────


@router.get("/payment", summary="Реквізити оплати (повний об'єкт)", tags=["Payments+"])
async def payment_requisites(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/payment** ✅🟢 (`getPaymentRequisites(params)`)

    Жива форма: `{instruction_link, mobile_instruction_link, online_link,
    full_name, city_id, legacy_payment{message_type, amount, date_start,
    pay_date_start}, one_c_code, account_amount, has_invoice_access,
    has_add_invoice_access, student_cost, contract_offer, online_link_has}`.
    Посилання/суми null, коли онлайн-оплата недоступна.
    """
    return await handle(request, sample={
        "instruction_link": None,
        "mobile_instruction_link": None,
        "online_link": None,
        "full_name": "Коваленко Олександр Сергійович",
        "city_id": 4,
        "legacy_payment": {"message_type": 1, "amount": 0, "date_start": None, "pay_date_start": None},
        "one_c_code": "000000001",
        "account_amount": None,
        "has_invoice_access": True,
        "has_add_invoice_access": False,
        "student_cost": None,
        "contract_offer": None,
        "online_link_has": True,
    })


@router.get("/payment/history", summary="Історія платежів (голий масив)", tags=["Payments+"])
async def payment_history(request: Request, page: int = 1, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/payment/history** ✅🟢 (`getPaymentHistory(params)`)

    Жива форма — ГОЛИЙ МАСИВ записів `{date, amount, description, type, currency}`;
    жодного конверта пагінації в тілі немає.
    """
    return await handle(request, sample=[
        {"date": "2025-12-30", "amount": 10026, "description": "Оплата за навчання", "type": 1, "currency": "UAH"},
        {"date": "2026-02-27", "amount": 10026, "description": "Оплата за навчання", "type": 1, "currency": "UAH"},
        {"date": "2026-04-28", "amount": 5000, "description": "Передплата", "type": 1, "currency": "UAH"},
    ])


@router.get("/payment/schedule", summary="Графік платежів (порожній масив, якщо немає)", tags=["Payments+"])
async def payment_schedule(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/payment/schedule** ✅🟢 (`getPaymentSchedule`)

    Якщо графіка немає — голий `[]`.
    """
    return await handle(request, sample=[
        {"date": "2026-09-01", "amount": 3200},
        {"date": "2026-10-01", "amount": 3200},
    ])


@router.post("/payment/link", summary="Посилання на оплату", tags=["Payments+"])
async def payment_link(body: Loose, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/payment/link** ✅⚠️ — body+params не спіймано."""
    return await handle(request, sample={"link": "https://pay.example.com/checkout/demo"})  # noqa: RUF027


@router.get("/payment/get-providers", summary="Платіжні провайдери", tags=["Payments+"])
async def payment_providers(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/payment/get-providers** ✅⚠️

    Провайдери онлайн-оплати (на споріднених ендпоінтах наживо видно IPayShop).
    """
    return await handle(request, sample=[{"name": "IPayShop"}, {"name": "Portmone"}])


@router.get("/payment/get-next-payment", summary="Найближчий платіж (повний об'єкт)", tags=["Payments+"])
async def next_payment(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/payment/get-next-payment** ✅🟢

    Жива форма: `{one_c_code, debtor_status, critical_debtor_status, amount,
    date_start, pay_date_start, date_critical, cw_amount, crm_form_id}`.
    У студента без заборгованості amount=0, усі дати null.
    """
    return await handle(request, sample={
        "one_c_code": "000000001",
        "debtor_status": 0,
        "critical_debtor_status": 0,
        "amount": 3200,
        "date_start": None,
        "pay_date_start": None,
        "date_critical": None,
        "cw_amount": 0,
        "crm_form_id": 1,
    })


@router.get("/payment/get-offer-contract", summary="Оферта договору (клієнт чекає поле success)", tags=["Payments+"])
async def offer_contract(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/payment/get-offer-contract** ✅ (параметрів НЕМАЄ)

    Фронт: `getContractOffer()` — ГОЛИЙ GET без query; клієнт перевіряє
    `'success' in response` і розгортає `response.success`, інакше прокидає помилку.
    Запит лише з `Authorization` сервер відхиляє **400** — імовірно,
    потрібен повний набір заголовків або оферта не випущена для акаунта
    (уточнити перехопленням трафіку).
    """
    return await handle(request, sample={"success": {"url": "https://files.example.com/offer.pdf"}})  # noqa: RUF027


# ── Club ─────────────────────────────────────────────────────────────────────


def _club(idx: int) -> dict[str, Any]:
    cid = 900 + idx
    return {
        "id": cid,
        "name": ["Розробка ігор на Unity", "Створення сайтів", "3D-моделювання та друк"][idx % 3],
        "type": "club",
        "schema": "offline_menu_select",
        "show_menu": 0,
        "branch_id": 4,
        "status": "enabled",
        "image": _FS,
        "images": None,
        "sub_type": "technologies",
        "club_category": "academy",
        "cost": 300,
        "debt": 0,
        "order_edit_until": "08:00:00",
        "address": f"{200 + idx} аудиторія",
        "description": "Демонстраційний опис гуртка: заняття раз на тиждень, "
                       "проєктна робота та захист підсумкового проєкту.",
        "created_at": "2026-03-03T12:23:56.000000Z",
        "updated_at": "2026-03-03T12:25:01.000000Z",
        "deleted_at": None,
        "abonements": [],
        "next_schedule": {"date": "2026-08-27", "time_from": "16:30:00", "time_to": "17:30:00"},
        "employees": [{
            "id": 900 + idx,
            "fio": "Мельник Ольга",
            "photo": None,
            "description": None,
            "external_id": 10000000 + idx,
            "project_id": 50,
            "branch_id": 4,
            "created_at": "2026-03-03T12:23:56.000000Z",
            "updated_at": "2026-03-03T12:23:56.000000Z",
            "deleted_at": None,
        }],
        "schedules": [{
            "id": 1100 + idx,
            "entity_id": cid,
            "day_of_week": "thursday",
            "time_from": "16:30:00",
            "time_to": "17:30:00",
        }],
    }


@router.get("/club/get-clubs", summary="Каталог клубів (голий масив об'єктів)", tags=["Club"])
async def clubs(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/club/get-clubs** ✅🟢

    Жива форма — ГОЛИЙ МАСИВ клубів (НЕ `{data:[…]}`). Елемент: `{id, name,
    type:"club", schema, show_menu, branch_id, status:"enabled", image, images,
    sub_type, club_category, cost, debt, order_edit_until, address, description,
    created_at, updated_at, deleted_at, abonements[], next_schedule{date, time_from,
    time_to}, employees[{id, fio, photo, …}], schedules[{id, entity_id, day_of_week,
    time_from, time_to}]}`.
    """
    return await handle(request, sample=[_club(i) for i in range(3)])


@router.get("/club/transactions", summary="Історія платежів по клубах (порожній масив, якщо немає)", tags=["Club"])
async def club_transactions(request: Request, page: int = 1, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/club/transactions** ✅🟢 (`getPaymentHistory`)

    Без операцій — голий `[]` (конверта немає).
    """
    return await handle(request, sample=[])


@router.get("/club/get-balance", summary="Баланс клубів (масив)", tags=["Club"])
async def club_balance(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/club/get-balance** ✅🟢

    Жива форма за порожнього балансу — голий МАСИВ `[]` (не об'єкт `{balance}`).
    """
    return await handle(request, sample=[])


@router.get("/club/link", summary="Платіжне посилання клубу", tags=["Club"])
async def club_link(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/club/link** ✅⚠️."""
    return await handle(request, sample={"link": "https://pay.example.com/club/demo"})  # noqa: RUF027


@router.get("/club/get-providers", summary="Провайдери клубу (клієнт бере .data)", tags=["Club"])
async def club_providers(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/club/get-providers** ✅⚠️ — фронт розгортає `.data`."""
    return await handle(request, sample={"data": [{"name": "IPayShop"}]})


@router.get("/club/abonements", summary="Активні абонементи (порожній масив, якщо немає)", tags=["Club"])
async def club_abonements(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/club/abonements** ✅🟢 (`getActiveClubs()`)

    Без абонементів — голий `[]`.
    """
    return await handle(request, sample=[])


class BuyAbonementIn(BaseModel):
    abonement_id: int = Field(description="ID пакета абонемента.")
    entity_id: int = Field(description="ID клубу (club.id з /club/get-clubs).")


@router.post("/club/buy-abonement", summary="Купити абонемент (body {abonement_id, entity_id})", tags=["Club"])
async def buy_abonement(body: BuyAbonementIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/club/buy-abonement** ✅ — тіло знято з фронта.

    Фронт (`onPay`): `{abonement_id: package.id, entity_id: club.id}`.
    Успіх → снек `payment_successful`; помилка — поле `{error:{message}}`
    (фолбек `something_went_wrong`). Формат успішної відповіді сервера ⚠️.
    """
    return await handle(request, sample={"status": "ok"})


@router.get("/club/download-schedules", summary="Завантажити розписи клубів (файл)", tags=["Club"])
async def club_schedules(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/club/download-schedules** ✅🟢

    Це НЕ файл: сервер відповідає JSON `{"result":"<посилання файлового сервісу>"}`,
    фронт відкриває посилання напряму (завантаження xlsx на боці файлового CDN).
    """
    return await handle(request, sample={"result": "https://fs3.itstep.org/api/v1/files/DEMOFILE"})


# ── Nutrition (+ QR) ─────────────────────────────────────────────────────────


class CancelOrderIn(BaseModel):
    date: str = Field(description='Дата скасовуваного замовлення, "YYYY-MM-DD".')


class BlockedTextIn(BaseModel):
    relative_text: Optional[str] = Field(
        default=None, description="Текст обмеження (напр., «без свинини»). При prohibited_all=true фронт його дисейблить."
    )
    prohibited_all: bool = Field(description="true — заборонити все харчування.", examples=[False])


@router.get("/students/get-qr-code", summary="QR-код їдальні — ГОЛИЙ РЯДОК data:image/png;base64,…", tags=["Nutrition"])
async def qr_code(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/students/get-qr-code** ✅🟢 (`getQrCode(params)`)

    Жива відповідь — НЕ об'єкт, а голий рядок `data:image/png;base64,…`
    (його фронт одразу підставляє в `<img src>`). Mock віддає коротку демо-заглушку.
    """
    return await handle(request, sample="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


@router.get("/nutrition/get-balance", summary="Баланс харчування (масив)", tags=["Nutrition"])
async def nutrition_balance(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/get-balance** ✅🟢

    Жива форма за відсутності харчування — голий МАСИВ `[]`.
    """
    return await handle(request, sample=[])


@router.post(
    "/students/evaluate-lesson",
    summary="Оцінити заняття та викладача (зірки 1-5)",
    tags=["Dashboard & Stats"],
    responses={401: {"model": ApiError}},
)
async def evaluate_lesson(request: Request, body: EvaluateLessonIn, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/students/evaluate-lesson** ✅ (бандл Chm3fOqc, endpoint '/students')

    Body: `{mark_lesson: 1..5, mark_teach: 1..5, comment: str, id: <evaluation_lesson_id>}`.

    - **Звідки id** — НЕ з `schedule/*`: уроки на оцінку приходять сокет-подією
      `socket_notification_handler` (notify-сокет) з payload
      `{handler:'evaluation_notification', id:<id повідомлення>, data:{…}}`;
      у body береться саме **`data.evaluation_lesson_id`**
      (поруч `data.teach_name`, `data.teach_photo`, `data.theme` — їх малює діалог);
    - діалог веде чергу (`rateClassArr`): кілька оцінок підряд батчаться в одне вікно,
      між хендлерами cooldown 800 мс; доступ гейтиться пермішеном
      `handlers_evaluation_notification` | `handlers_*`;
    - «Приховати» (skip) → emit `notification_hide_until {user_id:<id_user_storage>, id,
      hide_until: Date.now()+3 600 000}` — за годину оцінку показують знову;
    - за будь-якої оцінки <=3 фронт вимагає `comment` завдовжки >=6 символів;
    - оцінити можна лише в ДЕНЬ заняття;
    - помилки (енам): 84221 NOT_FOUND, 84222 ALREADY_USED, 84223 CLOSED_TODAY,
      84224 INCORRECT_MARK, 84225 MARK_SAVE_ERROR.
    """
    return await handle(request, sample={
        "status": "ok",
        "id": body.id,
        "mark_lesson": body.mark_lesson,
        "mark_teach": body.mark_teach,
    })


@router.get("/nutrition/transactions", summary="Історія операцій харчування (масив)", tags=["Nutrition"])
async def nutrition_transactions(request: Request, page: int = 1, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/transactions** ✅🟢

    Без операцій — голий `[]`. Наповнена форма елемента ⚠️.
    """
    return await handle(request, sample=[
        {"id": 1, "amount": -45.00, "date": "2026-08-20", "status": "paid"},
    ])


@router.get("/nutrition/get-order-menu", summary="Меню замовлень за дату (масив)", tags=["Nutrition"])
async def order_menu(request: Request, date: str = Query(description="YYYY-MM-DD"), ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/get-order-menu?date=** ✅🟢

    Фронт запитує діапазон (попередній/поточний/наступний місяць), фільтруючи
    `status!=='cancelled'`. Без замовлень — голий `[]`.
    """
    return await handle(request, sample=[
        {"id": 5, "date": date, "dish": "Борщ", "status": "ordered"},
    ])


@router.get("/nutrition/menu-for-date", summary="Меню на дату (масив)", tags=["Nutrition"])
async def menu_for_date(request: Request, date: str = Query(description="YYYY-MM-DD"), ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/menu-for-date?date=** ✅🟢

    Жива форма без меню — голий `[]`.
    """
    return await handle(request, sample=[
        {"code": "BORSCH", "title": "Борщ український", "price": 45},
    ])


@router.get("/nutrition/weekends-list", summary="Вихідні їдальні", tags=["Nutrition"])
async def weekends_list(request: Request, date: str = Query(description="YYYY-MM-DD (точка відліку)"), ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/weekends-list?date=** ✅🟢

    Фронт робить ТРИ запити одним махом: date = те саме число минулого, поточного й
    наступного місяця (getDateRange), відповіді flat()-ить в один список. Порожньо → `[]`.
    """
    return await handle(request, sample=[])


@router.get("/nutrition/linked-restaurant", summary="Прив'язана їдальня", tags=["Nutrition"])
async def linked_restaurant(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/linked-restaurant** ✅🟢

    Якщо їдальня НЕ прив'язана — сервер дає **500**,
    а не 200 з null. Мок повертає м'яку форму задля Try-it-out.
    """
    return await handle(request, sample={"restaurant": None})


@router.get("/nutrition/dish-categories", summary="Категорії страв (клієнт бере code)", tags=["Nutrition"])
async def dish_categories(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/dish-categories** ✅🟢

    Елемент `{name, code}`; клієнт мапить лише `.code`. Живі коди:
    first, second, garnish, bread, baking, drinks, salads, dessert, required.
    """
    return await handle(request, sample=[
        {"name": "First courses", "code": "first"},
        {"name": "Main dishes", "code": "second"},
        {"name": "Side dishes", "code": "garnish"},
        {"name": "Bread", "code": "bread"},
        {"name": "Baking", "code": "baking"},
        {"name": "Drinks", "code": "drinks"},
        {"name": "Salads", "code": "salads"},
        {"name": "Dessert", "code": "dessert"},
        {"name": "Extras", "code": "required"},
    ])


@router.get("/nutrition/link", summary="Платіжне посилання харчування", tags=["Nutrition"])
async def nutrition_link(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/link** ✅⚠️."""
    return await handle(request, sample={"link": "https://pay.example.com/nutrition/demo"})  # noqa: RUF027


@router.get("/nutrition/get-providers", summary="Провайдери харчування", tags=["Nutrition"])
async def nutrition_providers(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/nutrition/get-providers** ✅⚠️."""
    return await handle(request, sample={"data": [{"name": "Visa"}]})


@router.get("/payments/success", summary="Статус успішного платежу", tags=["Nutrition"])
async def payments_success(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/payments/success** ✅⚠️ (`getPaymentStatus`) — шлях БЕЗ /nutrition."""
    return await handle(request, sample={"success": True})


@router.post("/nutrition/make-order", summary="Зробити замовлення їжі", tags=["Nutrition"])
async def make_order(body: Loose, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/nutrition/make-order** ✅⚠️

    Тіло будує фронт із форми меню (дата + обрані страви за категоріями) —
    точний склад не спіймано ⚠️. Помилки приходять масивом `error[0]`; рядок
    `Your balance is too low` відкриває діалог поповнення балансу.
    """
    return await handle(request, sample={"status": "ordered"})


@router.post("/nutrition/cancellation-order", summary="Скасувати замовлення їжі", tags=["Nutrition"])
async def cancellation_order(body: CancelOrderIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/nutrition/cancellation-order** ✅ — тіло знято з фронта.

    Діалог підтвердження: `{date:"YYYY-MM-DD"}`;
    успіх → снек `order_successfully_canceled`.
    """
    return await handle(request, sample={"status": "cancelled"})


@router.post("/nutrition/set-blocked-text", summary="Текст блокування харчування", tags=["Nutrition"])
async def set_blocked_text(body: BlockedTextIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/nutrition/set-blocked-text** ✅ — тіло знято з фронта.

    Діалог обмежень шле `formGroup.getRawValue()` =
    `{relative_text, prohibited_all}`; при `prohibited_all=true` текст дисейблиться.
    Успіх → снек `snackbar_restrictions_saved`.
    """
    return await handle(request, sample={"status": "ok"})


# ── Library + Reviews ────────────────────────────────────────────────────────


@router.get("/library/list", summary="Бібліотека матеріалів (групування: спец → пакет → картки)", tags=["Library"])
async def library_list(request: Request, page: int = 1, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/library/list** ✅🟢 (`getMaterials(e)`)

    Жива форма: `{view: 1, data:[…]}`, де елемент `data[*]` — група за специфікацією:
    `{name_spec, image_spec|null, data:[{additional:[картки]}]}`.
    Картка матеріалу: `{url(файловий сервіс), description, material_id, theme,
    week_theme(багаторядковий список уроків тижня), current_week, public_week,
    material_type, id_spec, name_spec, is_new_material, date, sort_date(epoch)}`.
    """
    card = {
        "url": _FS,
        "description": "Презентація до уроку (демо)",
        "material_id": 1450000,
        "theme": "Презентація 6",
        "week_theme": "Урок 5. Побудова сцени\\nУрок 6. Геймплей",
        "current_week": 3,
        "public_week": 3,
        "material_type": 6,
        "id_spec": 2334,
        "name_spec": "Основи програмування",
        "is_new_material": True,
        "date": "2026-05-30",
        "sort_date": 1780088400,
    }
    return await handle(request, sample={
        "view": 1,
        "data": [
            {"name_spec": "Основи програмування", "image_spec": None, "data": [{"additional": [card]}]},
            {"name_spec": "Веб-розробка", "image_spec": None, "data": [{"additional": [card | {"material_id": 1450001, "name_spec": "Веб-розробка"}]}]},
        ],
    })


@router.get("/settings/history-specs", summary="Специфікації за історію навчання", tags=["Library"])
async def history_specs(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/settings/history-specs** ✅🟢 (`getSubjects()`)

    Масив `{id, name, short_name}` — короткий код використовується у відгуках (`reviews.spec`).
    """
    return await handle(request, sample=[
        {"id": 988, "name": "Розробка додатків на Python", "short_name": "PYT"},
        {"id": 2334, "name": "Основи програмування", "short_name": "BAS"},
        {"id": 2401, "name": "3D-моделювання та 3D-друк", "short_name": "3DMP"},
    ])


@router.get("/reviews/list", summary="Відгуки про місце навчання (_meta + дані)", tags=["Library"])
async def reviews_list(request: Request, page: int = 1, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/reviews/list** ✅🟢

    endpoint='/reviews' → реальний шлях `/reviews/list`.

    Жива форма: `{_meta:{currentPage, totalPages, totalCount}, data:[…]}`.
    Елемент: `{date:"YYYY-MM-DD HH:MM:SS", message, spec(короткий код з
    history-specs), full_spec, teacher, view:"0"|"1"(рядок!), mark:"excellent"|null,
    teacher_photo(URL файлового сервісу)|null, subject_image|null}`.
    Лічильники якості (excellent/good/bad) фронт збирає сам по `data[*].mark`.
    """
    return await handle(
        request,
        sample={
            "_meta": {"currentPage": page, "totalPages": 1, "totalCount": 3},
            "data": [
                {
                    "date": "2026-03-30 20:05:10",
                    "message": "Студент відповідально підходить до виконання завдань, "
                               "шукає нестандартні підходи. Молодець!",
                    "spec": "BAS",
                    "full_spec": "Основи програмування",
                    "teacher": "Викладач Демо",
                    "view": "0",
                    "mark": "excellent",
                    "teacher_photo": _FS,
                    "subject_image": None,
                },
                {
                    "date": "2025-12-26 13:53:52",
                    "message": "Дуже хороший і кмітливий студент! Завжди активний на уроках.",
                    "spec": "3DMP",
                    "full_spec": "3D-моделювання та 3D-друк",
                    "teacher": "Мельник Ольга",
                    "view": "1",
                    "mark": None,
                    "teacher_photo": None,
                    "subject_image": None,
                },
            ],
        },
    )
