"""§14 Ледачі чанки — нагороди батька (чанк `sc20t5_5`) та чат (чанк `BVhovRZH`).

Правила стилю (як у routers/auth.py):
- «філійні» шляхи повторюють прод: /v1/mystat/{branch_alias}/custom-awards/* і /{sender}/*;
- кожен ендпоінт: детальний markdown-опис (маркер 🟢/✅/⚠️/❌, реальний URL, заголовки,
  тіло з типами, відповідь, особливості), responses= з моделлю помилки ApiError;
- тіло обробника — завжди через handle()/forward() з ..proxy (mock|proxy режими);
- пагінація — query page/per_page + заголовки X-Pagination-* через параметр response: Response.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx
from ..models.common import ApiError
from ..proxy import MODE, forward, handle

router = APIRouter(prefix="/v1/mystat/{branch_alias}")


# ── Вхідні моделі ────────────────────────────────────────────────────────────


class AwardFormIn(BaseModel):
    """Тіло створення/правки нагороди — форма `awardForm` з діалога фронта
    (`getRawValue()`): `{name, icon, value}`. Поля обов'язкові."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(
        max_length=20,
        description="Назва нагороди (валідатор maxLength=20).",
        examples=["Поход в кино"],
    )
    icon: str = Field(
        description="Іконка з GET /custom-awards/icons (фронт кладе її в <img src>).",
        examples=["cinema.svg"],
    )
    value: int = Field(
        ge=1,
        description="Ціна в монетах; дефолт форми = 2. Дитина «купує» за цей баланс.",
        examples=[100],
    )


class DecrementUnreadedIn(BaseModel):
    """Скидання лічильника непрочитаних кімнати. Тіло підтверджене бандлом ✅: `{id}`."""

    model_config = ConfigDict(extra="allow")

    id: int | str = Field(description="ID бесіди (conversation.id або conversation_id виду 'group_3001').", examples=["group_3001"])


class MessageEditIn(BaseModel):
    """Редагування свого повідомлення в чаті. Тіло підтверджене бандлом ✅: `{id, text}`."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(description="ID повідомлення (поле `id` з `socket.incoming.message` / `messages`).", examples=[1001])
    text: str = Field(description="Новий текст повідомлення.", examples=["Виправлений текст"])


class MessageDeleteIn(BaseModel):
    """Видалення свого повідомлення в чаті. Тіло підтверджене бандлом ✅: `{id}`."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(description="ID повідомлення.", examples=[1001])


def _set_pagination_headers(
    response: Response, page: int, per_page: int, total: int
) -> None:
    """Прод віддає номери сторінок заголовками (див. §2 Пагінація та models/common.PaginationMeta)."""
    last_page = max(1, -(-total // max(per_page, 1)))
    response.headers["X-Pagination-Current-Page"] = str(page)
    response.headers["X-Pagination-Page-count"] = str(last_page)
    response.headers["X-Pagination-Per-Page"] = str(per_page)
    response.headers["X-Pagination-Total-Count"] = str(total)


# ── Awards & Payments (нагороди батьків, чанк sc20t5_5) ───────────────────────


@router.get(
    "/custom-awards/relative/balance",
    summary="Баланси дитини для нагород",
    tags=["Awards & Payments"],
)
async def relative_balance(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/relative/balance** ✅🟢

    Баланс «бобрів» (beavers) — внутрішня валюта кастомних нагород.
    Форма — ОБ'ЄКТ `{beavers:{value, temp_value, all}}` (НЕ масив балансів!).

    > Mock: демо-значення; proxy — форвард у живе API.
    """
    return await handle(
        request,
        sample={"beavers": {"value": 0, "temp_value": 0, "all": 0}},
    )


@router.get(
    "/custom-awards/relative/logs",
    summary="Історія нарахувань нагород (пагінація заголовками)",
    tags=["Awards & Payments"],
)
async def relative_logs(
    request: Request,
    response: Response,
    page: int = 1,
    per_page: int = 15,
    ctx: AuthCtx = Depends(auth_ctx),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/relative/logs** ✅

    Історія нарахувань/списань монет за нагородами.

    - **Query**: `page` (з 1), `per_page` — серіалізація залежить від `paginationFormat` філії
      (див. §2): laravel → `pagination[page]`, yii → `page`, flask → `limit/offset`.
      Значення `per_page` за замовчуванням фронт бере з `localStorage.per_page`.
    - **Пагінація**: номерами сторінок у **заголовках відповіді** `X-Pagination-Current-Page`,
      `X-Pagination-Page-count` (+ Per-Page / Total-Count) — через параметр `response: Response`.
    - **Відповідь**: масив записів `{date, items[]}` — групування за датами, як на Dashboard ⚠️.

    > Mock: одна сторінка з двома записами + заголовки X-Pagination-*; proxy — форвард.
    """
    result = await handle(
        request,
        sample=[
            {
                "date": "2026-08-20",
                "items": [
                    {"id": 101, "title": "Поход в кино", "amount": 100, "type": "accrual"},
                    {"id": 102, "title": "Штраф за опоздание", "amount": -20, "type": "writeoff"},
                ],
            }
        ],
    )
    if isinstance(result, Response):
        # proxy-режим: handle() повернув готовий Response — у нього немає len()
        # (раніше це падало TypeError → 500), заголовки прийдуть з upstream
        return result
    _set_pagination_headers(response, page, per_page, total=len(result))
    return result


@router.get("/custom-awards/awards", summary="Список нагород батька", tags=["Awards & Payments"])
async def list_awards(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/awards** ✅

    Створені батьком кастомні нагороди (доступні дитині до «купівлі» за монети).

    - **Відповідь**: масив `{id, name, icon, value}` — рівно ці поля діалог правки
      кладе в форму (`data.name || null`, `data.icon`, `data.value`), а
      `giveAward` порівнює `t.value > balance()`.
    """
    return await handle(
        request,
        sample=[
            {"id": 1, "name": "Поход в кино", "value": 100, "icon": "cinema.svg"},
            {"id": 2, "name": "День без домашних заданий", "value": 250, "icon": "walk.svg"},
        ],
    )


@router.post(
    "/custom-awards/awards",
    summary="Створити нагороду",
    tags=["Awards & Payments"],
    responses={200: {"description": "Створена нагорода."}, 401: {"model": ApiError}},
)
async def create_award(body: AwardFormIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/custom-awards/awards** ✅⚠️

    Створення нагороди: `saveAward()` шле `getRawValue()` форми —
    `{name(≤20), icon, value}`. Успіх → снекбар підтвердження й
    перезавантаження списку (`awardsUpdated`). Форма відповіді ⚠️ (повертаємо створений об'єкт).
    """
    return await handle(request, sample={"id": 3, **body.model_dump()})


@router.put(
    "/custom-awards/award/{award_id}",
    summary="Змінити нагороду",
    tags=["Awards & Payments"],
)
async def update_award(
    award_id: int, body: AwardFormIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)
) -> Any:
    """**PUT /v1/mystat/{branch_alias}/custom-awards/award/{award_id}** ✅⚠️

    Правка нагороди: діалог із `data.id` шле ПОВНУ форму `updateAward(form, id)` —
    `{name, icon, value}` (не патч!). Успіх → снекбар `changes_saved`.
    Форма відповіді ⚠️.
    """
    return await handle(request, sample={"id": award_id, **body.model_dump()})


@router.delete(
    "/custom-awards/award/{award_id}",
    summary="Видалити нагороду",
    tags=["Awards & Payments"],
)
async def delete_award(award_id: int, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**DELETE /v1/mystat/{branch_alias}/custom-awards/award/{award_id}** ✅⚠️

    Видалення: `onDelete(t)` → `deleteAward(t.id)`; успіх → снекбар `success`
    і `awardsUpdated.emit(true)`, помилка → тост `error`.
    Форма відповіді ⚠️.
    """
    return await handle(request, sample={"status": "deleted", "id": award_id})


class GiveAwardIn(BaseModel):
    """Вручити готову нагороду — тіло підтверджене бандлом (`sc20t5_5`)."""

    award_id: int = Field(description="ID нагороди з GET /custom-awards/awards.")


@router.post(
    "/custom-awards/give-award",
    summary="Вручити готову нагороду дитині",
    tags=["Awards & Payments"],
)
async def give_award(body: GiveAwardIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/custom-awards/give-award** ✅⚠️

    Бандл (`sc20t5_5`): `giveAward({award_id: t.id})`. Якщо `value > balance`,
    фронт СПЕРШУ відкриває діалог поповнення (topup-options + providers),
    інакше шле цей POST; успіх → снекбар `reward_sent` і перезавантаження списку
    нагород. Форма відповіді ⚠️.
    """
    return await handle(request, sample={"status": "ok", "award_id": body.award_id})


@router.get("/custom-awards/icons", summary="Іконки нагород", tags=["Awards & Payments"])
async def icons(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/icons** ✅

    Каталог іконок для вибору під час створення нагороди. Query-параметри прод-запиту ⚠️.

    - **Відповідь**: масив `{id, …}` (URL/ключ картинки — точна структура ⚠️).
    """
    return await handle(
        request,
        sample=[{"id": 1, "name": "cinema"}, {"id": 2, "name": "pizza"}, {"id": 3, "name": "walk"}],
    )


@router.get(
    "/custom-awards/topup-options",
    summary="Варіанти поповнення монет",
    tags=["Awards & Payments"],
)
async def topup_options(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/topup-options** ✅

    Пакети поповнення внутрішніх монет (для купівлі нагород дитині). Query-параметри ⚠️.

    - **Відповідь**: масив варіантів `{id, amount, price, currency, …}` ⚠️.
    """
    return await handle(
        request,
        sample=[
            {"id": 1, "amount": 100, "price": 99, "currency": "UAH"},
            {"id": 2, "amount": 500, "price": 449, "currency": "UAH"},
        ],
    )


@router.get(
    "/custom-awards/pay-link",
    summary="Посилання на оплату поповнення",
    tags=["Awards & Payments"],
)
async def pay_link(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/pay-link** ✅

    Посилання на платіжну сторінку поповнення монет (обраний варіант — у query ⚠️).

    - **Відповідь**: `{"link": "<url платіжної системи>"}`.
    """
    return await handle(
        request, sample={"link": "https://pay.example.com/checkout/custom-awards?order=demo"}
    )


@router.get(
    "/custom-awards/get-providers",
    summary="Платіжні провайдери",
    tags=["Awards & Payments"],
)
async def get_providers(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/get-providers** ✅

    Список доступних платіжних провайдерів для поповнення.

    - **Відповідь**: `[{id:int, name:str}, …]`.
    """
    return await handle(
        request,
        sample=[{"id": 1, "name": "Privat24"}, {"id": 2, "name": "LiqPay"}, {"id": 3, "name": "WayForPay"}],
    )


# ── Аватар студента: предмети за бобрів (чанк 0A-Vv-q9 + B_ScMRTO) ✅ ─────────
# Сервіс homeAchievementsStudService, endpoint='/custom-awards'. UI: app-home-achievements-stud,
# app-avatar-block; i18n 'collect_them_to_customize_avatar' — купівля предметів за бобрів
# й екіпіровка на аватар. Клік по предмету: не куплений → buyItems({items:[id]}) → equipItem;
# куплений або prices порожній → одразу equipItem({item_id}).


def _demo_catalog() -> dict:
    """Каталог аватарів: категорії body/mouth/eyes/background (66 предметів),
    елемент: {id, img:<files-url>, prices:[{value:int,currency:"BEV"}], purchased,
    equipped, default, params}. Перший предмет категорії — безкоштовний дефолт."""
    cats = [("body", 6), ("mouth", 4), ("eyes", 4), ("background", 5)]
    out: dict = {}
    nid = 3
    for code, cnt in cats:
        arr = []
        for i in range(cnt):
            free = i == 0
            arr.append({
                "id": nid,
                "img": "https://fs3.itstep.org/api/v1/files/DEMOFILE",
                "prices": [] if free else [{"value": 40 if i % 2 else 60, "currency": "BEV"}],
                "purchased": free,
                "equipped": free,
                "default": free,
                "params": [],
            })
            nid += 3
        out[code] = arr
    return out


@router.get("/custom-awards/balance", summary="Баланс бобрів студента", tags=["Awards & Payments"])
async def ca_balance(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/balance** ✅🟢

    Форма: `{"beavers":<int>}`. Парсер фронта терпить і
    вкладені форми ({beavers:{all|value}}, {balance}), але сервер відповідає просто числом.
    """
    return await handle(request, sample={"beavers": 120})


@router.get("/custom-awards/logs", summary="Історія нарахувань бобрів (?page=&per_page=)", tags=["Awards & Payments"])
async def ca_logs(request: Request, page: int = 1, per_page: int = 20, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/logs?page=1&per_page=20** ✅🟢

    Дефолти сторінки зашиті у фронті (`{page:1, per_page:20}`). Живий акаунт
    відповідає `[]`; фронт сортує елементи за полем `date` (DESC) — решта
    полів елемента ⚠️ (зняти за ненульової історії).
    """
    return await handle(request, sample=[
        {"id": 900 + page, "value": 25, "description": "Награда за активность", "date": "2026-08-20"},
    ])


@router.get("/custom-awards/top-achievements", summary="Топ досягнень (блок «Топ нагород»)", tags=["Awards & Payments"])
async def ca_top(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/top-achievements** ✅🟢

    Порожня історія → `[]`. Мапінг фронта: id=`rule_id??id`,
    title=`title||name||label`, count=`value??count??total`, icon=`icon||img`.
    """
    return await handle(request, sample=[
        {"rule_id": 12, "title": "Собери 50 бобров", "count": 25, "icon": "/assets/icons/beaver/beaver.svg"},
    ])


@router.get("/custom-awards/items", summary="Каталог предметів аватара (ОБ'ЄКТ за категоріями)", tags=["Awards & Payments"])
async def ca_items(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/custom-awards/items** ✅🟢

    Відповідає ОБ'ЄКТОМ `{<код категорії>:[предмети,…]}` — категорії:
    body(30), mouth(10), eyes(10), background(16); разом 66 предметів.
    Query `?category=` сервер ІГНОРУЄ (завжди весь каталог).
    Предмет: `{id, img, prices:[{value:<int>, currency:"BEV"}], purchased,
    equipped, default, params}` (params у живих = `[]`); безкоштовні —
    `prices:[]` + `default:true`. totalPurchasePrice фронта = Σ prices[0].value.
    """
    return await handle(request, sample=_demo_catalog())


class ItemsBuyIn(BaseModel):
    items: list[int] = Field(description="ID предметів до купівлі (масив! фронт шле {items:[id]}).")


@router.post("/custom-awards/items/buy", summary="Купити предмети за бобрів", tags=["Awards & Payments"])
async def ca_buy(request: Request, body: ItemsBuyIn, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/custom-awards/items/buy** ✅⚠️

    Body: `{"items":[<id>, …]}`. Після купівлі фронт одразу викликає
    `POST /custom-awards/items/equip`.
    """
    return await handle(request, sample={"status": "ok", "items": body.items})


class ItemEquipIn(BaseModel):
    item_id: int = Field(description="ID предмета для екіпіровки на аватар.")


@router.post("/custom-awards/items/equip", summary="Екіпірувати предмет на аватар", tags=["Awards & Payments"])
async def ca_equip(request: Request, body: ItemEquipIn, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**POST /v1/mystat/{branch_alias}/custom-awards/items/equip** ✅⚠️

    Body: `{"item_id":<id>}`. Викликається і одразу після купівлі, і при кліку на вже
    куплений предмет.
    """
    return await handle(request, sample={"status": "ok", "item_id": body.item_id})


# ── Chat ─────────────────────────────────────────────────────────────────────
# У коді фронта senderEndpoint='/sender/conversation' — ЛІТЕРАЛ, без підстановки {sender}.


@router.get("/chat/room-list", summary="Список кімнат чату", tags=["Chat"])
async def room_list(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/chat/room-list** ✅🟢

    Кімнати чату. Жива форма елемента: `{conversation_id:"group_<id_tgroups>",
    photo_from, name(ПІБ власника), conversation_name(ім'я групи), type:"group",
    user_id_from, additional:{id_tgroups, participants[список id_user_storage]},
    readonly}`.

    - `participants` — це **id_user_storage** учасників (НЕ logbook_id!);
    - живе оновлення списку — по chat-сокету, REST віддає первинний зріз.
    """
    return await handle(
        request,
        sample=[
            {
                "conversation_id": "group_3001",
                "photo_from": None,
                "name": "Коваленко Олександр",
                "conversation_name": "П-101",
                "type": "group",
                "user_id_from": None,
                "additional": {"id_tgroups": 3001, "participants": [5000001, 5000002, 5000003]},
                "readonly": False,
            }
        ],
    )


@router.get(
    "/sender/conversation/messages",
    summary="Повідомлення бесіди (?id=&branch_id=&last_message_id=)",
    tags=["Chat"],
)
async def messages(
    request: Request,
    id: int | str,
    branch_id: Optional[int] = None,
    last_message_id: Optional[int] = Query(default=None, description="Для підвантаження СТАРИХ повідомлень: id останнього відомого."),
    ctx: AuthCtx = Depends(auth_ctx),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/sender/conversation/messages** ✅ (параметри з коду фронта)

    Історія повідомлень (`getConversationMessages`). Реальні query-параметри:

    - `id` — ID бесіди: число (conversation.id) АБО рядок `conversation_id`
      виду `"group_3001"` (фронт шле `id ?? conversation_id`);
    - `branch_id` — філія;
    - `last_message_id` — при «догрузити ще» (пагінація вгору).

    **Відповідь**: об'єкт з ДИКТОМ `messages`: `{messages:{ "<ключ>": [повідомлення…] }}`,
    ключі — групи (дати); фронт розгортає/сортує їх сам. Нові повідомлення
    приходять подією `socket.incoming.message` chat-сокета.
    """
    return await handle(
        request,
        sample={
            "messages": {
                "2026-08-20": [
                    {"id": 1001, "user_id": 100001, "message": "Привіт!", "created_at": "2026-08-20 10:15:00"},
                    {"id": 1002, "user_id": 100002, "message": "Привіт 👋", "created_at": "2026-08-20 10:16:30"},
                ],
            },
        },
    )


@router.get("/sender/conversation", summary="Бесіди, згруповані за станами (new/opened/closed)", tags=["Chat"])
async def room(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/sender/conversation** ✅🟢

    Фронт зазвичай викликає БЕЗ параметрів. Форма: бесіди згруповані за станами —
    `{new:{count, list}, opened:{count, list}, closed:{count, list}}`;
    клієнт бере групу за ключом стану (`r[Opened]`).
    """
    return await handle(
        request,
        sample={
            "new": {"count": 0, "list": []},
            "opened": {"count": 1, "list": [{"conversation_id": "group_3001", "id": 42, "type": "group"}]},
            "closed": {"count": 0, "list": []},
        },
    )


@router.post(
    "/sender/conversation/decrement-unreaded",
    summary="Скинути лічильник непрочитаних кімнати",
    tags=["Chat"],
)
async def decrement_unreaded(
    body: DecrementUnreadedIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)
) -> Any:
    """**POST /v1/mystat/{branch_alias}/sender/conversation/decrement-unreaded** ✅

    Позначити бесіду прочитаною при відкритті (`setReadMessages`).

    - **Body** ✅ (з коду фронта): `{id: <conversation_id|число>}`;
    - викликається лише коли id числовий (`Number(r.id)` — для group-кімнат
      з рядковим `conversation_id` фронт НЕ викликає).
    """
    return await handle(request, sample={"status": "ok", "id": body.id})


@router.post(
    "/sender/conversation/message-edit",
    summary="Редагувати своє повідомлення в чаті",
    tags=["Chat"],
)
async def message_edit(
    body: MessageEditIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)
) -> Any:
    """**POST /v1/mystat/{branch_alias}/sender/conversation/message-edit** ✅ (нове у збірці 2026-10)

    Виклик `ChatService.editMessage(id, text)`: тіло `{id, text}`. Фронт у UI чату показує
    банер «редагування» (`chat_editing_message`) і позначку `chat_message_edited`.
    Форма успішної відповіді у бандлі не читається ⚠️; при помилці клієнт підставляє
    `{status: false}` (`catchError → of({status:false})`).
    """
    return await handle(request, sample={"status": True})


@router.post(
    "/sender/conversation/message-delete",
    summary="Видалити своє повідомлення в чаті",
    tags=["Chat"],
)
async def message_delete(
    body: MessageDeleteIn, request: Request, ctx: AuthCtx = Depends(auth_ctx)
) -> Any:
    """**POST /v1/mystat/{branch_alias}/sender/conversation/message-delete** ✅ (нове у збірці 2026-10)

    Виклик `ChatService.deleteMessage(id)`: тіло `{id}`. Перед видаленням UI питає
    підтвердження (`chat_delete_message_confirm`). Форма успішної відповіді у бандлі
    не читається ⚠️; при помилці клієнт підставляє `{status: false}`.
    """
    return await handle(request, sample={"status": True})


# Chat-сокет wss://chat-socket-logbook.itstep.org — події лінивого чанка BVhovRZH ⚠️.
#
# Підключення (як в інших сокетів, §9): io(url, {path:"/socket.io",
#   query:{alias:"<branch_alias>"}, auth:{token:"<access_token>"}, extraHeaders:{...}}).
#
# Клієнт → сервер (emit) ⚠️ (payload уточнити):
#   • identify           — реєстрація: {profile, userId=<id_user_storage>} ✅ (чекаємо on('identified'));
#   • join_room          — підписка: {rooms:["chat_<branch_id>_<conversation_id>", "<branch_id>"]} ✅;
#   • message_out_send   — надсилання повідомлення в кімнату.
#
# Сервер → клієнт (on) ⚠️ (payload уточнити):
#   • socket.incoming.message          — нове вхідне повідомлення;
#   • conversation_messages_counter    — перерахунок непрочитаних по кімнатах;
#   • conversation_updated             — зміна кімнати (повідомлення/учасники).
