"""§7 Адмін-розділ (роут /admin) + Shop з §14 «Інше» (сервіс у старих бандлах).

Правила стилю (як у routers/auth.py):
- «гілкові» шляхи повторюють прод: /v1/mystat/{branch_alias}/admin/* і /shop/*;
- кожен ендпоінт: докладний markdown-опис (маркер 🟢/✅/⚠️/❌, реальний URL, заголовки,
  тіло з типами, відповідь, особливості), responses= з моделлю помилки ApiError;
- тіло обробника — завжди через handle()/forward() з ..proxy (mock|proxy режими);
- пагінація — query page/per_page + заголовки X-Pagination-* через параметр response: Response."""
from collections.abc import Iterator
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx, make_fake_jwt
from ..models.common import ApiError
from ..proxy import MODE, forward, handle

router = APIRouter(prefix="/v1/mystat/{branch_alias}")


# ── Вхідні моделі ────────────────────────────────────────────────────────────


class EmptyBody(BaseModel):
    """Порожнє JSON-тіло `{}` — так викликають фронтові POST без параметрів."""

    model_config = ConfigDict(json_schema_extra={"examples": [{}]})


class CreateOrderIn(BaseModel):
    """Тіло `POST /shop/create-order` ✅ (бандл DB7g6Drg2, transformPayload)."""

    products: list[dict[str, int]] = Field(
        description="[{product_id, quantity}] — саме `product_id`, не `id`.",
        examples=[[{"product_id": 12, "quantity": 1}]],
    )
    merchant: str = Field(
        default="IPayShop",
        description='selectedPaymentMethod()==="bonus" ? "Gaming" : "IPayShop".',
        examples=["IPayShop", "Gaming"],
    )


def _set_pagination_headers(
    response: Response, page: int, per_page: int, total: int
) -> None:
    """Прод віддає номери сторінок заголовками (див. §2 Пагінація та models/common.PaginationMeta)."""
    last_page = max(1, -(-total // max(per_page, 1)))
    # поточна сторінка затискається в [1, last_page] — як у homework.py:
    # «?page=7» при 1 сторінці віддає current=7 і порожнє тіло, що
    # ламає цикл пагінації на клієнті (сторінка 7 з 1)
    response.headers["X-Pagination-Current-Page"] = str(min(max(page, 1), last_page))
    response.headers["X-Pagination-Page-count"] = str(last_page)
    response.headers["X-Pagination-Per-Page"] = str(per_page)
    response.headers["X-Pagination-Total-Count"] = str(total)


# ── Admin (§7) ────────────────────────────────────────────────────────────────


@router.get(
    "/admin/list-students",
    summary="Список студентів (для входу «як студент»)",
    tags=["Admin"],
)
async def list_students(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/admin/list-students** ✅

    Список студентів філії для адмінського розділу.

    - **Доступ**: визначається по `rolePerm.*.*.includes("admin.mystat.view")` — роль приходить
      у `POST /auth/me`; без цього права справжнє API не віддає дані.
    - **Відповідь**: `{ "<branch_alias>": [ { "id_stud": 123, "fio": "Іванов І." } ] }` — ключі — аліаси філій.
    - **Важливо**: `id_stud` = **logbook_id** студента (= JWT.sub), НЕ `id_user_storage`!

    > Mock: одна гілка `pl` з одним студентом; proxy — форвард у живе API."""
    return await handle(
        request,
        sample={"pl": [{"id_stud": 100001, "fio": "Коваленко Олександр"}]},
    )


@router.post(
    "/admin/login-student/{student_id}",
    summary="Увійти як студент → text/plain URL «?t=<JWT>»",
    response_class=PlainTextResponse,
    responses={
        200: {
            "content": {"text/plain": {"example": "https://mystat.itstep.org/?t=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...."}},
            "description": "Рядок URL, з якого клієнт витягує параметр t як access_token студента.",
        },
        401: {"model": ApiError},
        403: {"model": ApiError, "description": "Немає права admin.mystat.view."},
    },
)
async def login_student(
    student_id: int, request: Request, body: EmptyBody | None = None, ctx: AuthCtx = Depends(auth_ctx)
) -> Any:
    """**POST /v1/mystat/{branch_alias}/admin/login-student/{student_id}** ✅

    Вхід адміністратора під обраним студентом (`student_id` = **logbook_id**, той самий,
    що `id_stud` з list-students).

    Механіка на клієнті:
    - перед викликом фронт ставить `localStorage.branch_alias` = **аліас філії студента**
      (студент може бути в іншій гілці, ніж адмін!);
    - відповідь — `text/plain`: рядок URL виду `https://.../?t=<JWT>`;
    - клієнт витягує query-параметр `t` — це **access_token студента** — і зберігає його
      у `localStorage.access_token`;
    - адмінський токен при цьому залишається в `localStorage.admin_token`;
    - виставляється прапорець `localStorage.admin_login="1"` — за ним фронт розуміє, що сесія
      «під маскою», і вміє повернутися до адміна (відновивши `access_token` з `admin_token`);
    - доступ до самого ендпоінта визначається правом `rolePerm.*.*.includes("admin.mystat.view")`.

    > Mock: повертає `"https://mystat.itstep.org/?t=" + make_fake_jwt(sub=id=student_id)` —
    > фейковий JWT студента з потрібним logbook_id; proxy — форвард у живе API."""
    if MODE == "proxy":
        return await forward(request)
    # Контракт доступу: право admin.mystat.view у rolePerm (див. докстринг).
    # rolePerm ОБОВ'ЯЗКОВИЙ: без нього (дефолтний мок-студент) — 403, а не «дозволено
    # для сумісності». Токен із rolePerm у моку можна зібрати через make_fake_jwt(rolePerm=…).
    role_perm = ctx.payload.get("rolePerm")

    def _perm_strings(node: Any) -> Iterator[str]:
        # rolePerm може бути будь-якої вкладеності: {proj:{role:[perm,…]}} / списки
        if isinstance(node, str):
            yield node
        elif isinstance(node, (list, tuple)):
            for item in node:
                yield from _perm_strings(item)
        elif isinstance(node, dict):
            for value in node.values():
                yield from _perm_strings(value)

    if role_perm is None or not any(p == "admin.mystat.view" for p in _perm_strings(role_perm)):
        raise HTTPException(
            status_code=403,
            detail=[{"field": "summary", "message": "Нет права admin.mystat.view"}],
        )
    token = make_fake_jwt(sub=student_id, id=student_id)
    return PlainTextResponse(f"https://mystat.itstep.org/?t={token}", media_type="text/plain")


# ── Shop («Інше», §14; сервіс у старих бандлах) ─────────────────────────────


def _demo_product(idx: int) -> dict[str, Any]:
    """Товар — форма елемента каталогу."""
    pid = 46000 + idx
    now = "2026-04-22T09:14:23.000000Z"
    return {
        "id": pid,
        "uuid": f"00000000-0000-4000-8000-{pid:012d}",
        "project_id": 50,
        "branch_id": 4,
        "category_id": 743,
        "status": 1,
        "quantity": 10 - idx % 10,
        "dynamic_price": "off",
        "premium_subscription": "off",
        "published_at": "2026-04-22 12:14:23",
        "sku": str(200 + idx),
        "image": ["https://fs3.itstep.org/api/v1/files/DEMOFILE"],
        "type": 0,
        "external_id": None,
        "created_by": 63000 + idx,
        "created_by_fio": "Ірина Мельник",
        "updated_by": 63000 + idx,
        "updated_by_fio": "Ірина Мельник",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "properties": [
            {"name": "Color", "value": "Чорний", "code": "color"},
            {"name": "Material", "value": "Бавовна", "code": "material"},
        ],
        "prices": [
            {"id": 93154 + idx, "product_id": pid, "price": "231.00", "min_price": "116.00", "currency": "COI", "type": "default", "until_to": None, "created_at": now, "updated_at": now},
            {"id": 93151 + idx, "product_id": pid, "price": "99.00", "min_price": "50.00", "currency": "DIA", "type": "default", "until_to": None, "created_at": now, "updated_at": now},
        ],
    }


@router.get("/shop/products", summary="Каталог магазину (голий масив товарів)", tags=["Shop"])
async def products(
    request: Request,
    response: Response,
    page: int = 1,
    per_page: int = 15,
    ctx: AuthCtx = Depends(auth_ctx),
) -> Any:
    """**GET /v1/mystat/{branch_alias}/shop/products** ✅🟢

    Каталог мерчу IT Step. Форма — ГОЛИЙ МАСИВ товарів
    (`{current_page,data,…}` конверта НЕМАЄ); номери сторінок — заголовками `X-Pagination-*`.

    Елемент: `{id, uuid, project_id, branch_id, category_id, status, quantity,
    dynamic_price:"off", premium_subscription:"off", published_at, sku, image[URL],
    type, external_id, created_by(_fio), updated_by(_fio), created_at, updated_at,
    deleted_at, properties[{name,value,code}], prices[{price, min_price,
    currency(DIA|COI|BEV), type(default|discount), until_to}]}`."""
    total = 12
    start = (max(page, 1) - 1) * per_page
    result = [_demo_product(i) for i in range(start, min(start + per_page, total))]
    _set_pagination_headers(response, page=max(page, 1), per_page=per_page, total=total)
    return result


@router.get(
    # `:int` обов'язковий! Інакше маршрут з'їв би /products/get-quantity і /products/get-others
    "/shop/products/{product_id:int}",
    summary="Картка товару",
    tags=["Shop"],
)
async def product(product_id: int, request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/shop/products/{product_id}** ✅🟢

    Один товар — форма елемента каталогу (див. `/shop/products`)."""
    return await handle(request, sample=_demo_product(product_id % 12))


@router.get(
    "/shop/products/get-quantity",
    summary="Залишок товару на складі (getQuantity)",
    tags=["Shop"],
)
async def product_quantity(request: Request, product_id: int, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/shop/products/get-quantity?{params}** ✅

    Точні імена query ⚠️ (імовірний `product_id`)."""
    return await handle(request, sample={"product_id": product_id, "quantity": 7})


@router.get(
    "/shop/products/get-others",
    summary="Схожі / інші товари (getOtherProducts)",
    tags=["Shop"],
)
async def other_products(
    request: Request, product_id: int, ctx: AuthCtx = Depends(auth_ctx)
) -> Any:
    """**GET /v1/mystat/{branch_alias}/shop/products/get-others?{params}** ✅

    Шлях — **`/shop/products/get-others`** (функція фронту `getOtherProducts`).

    - **Відповідь**: масив товарів тієї ж форми, що каталог; для товару
      без «схожих» сервер віддає голий `[]`."""
    return await handle(
        request,
        sample=[_demo_product(3), _demo_product(4)],
    )


@router.get("/shop/orders", summary="Замовлення користувача (статуси 1|3 нові, 2|5 скасовані, 4 закрите)", tags=["Shop"])
async def orders(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/shop/orders** ✅

    Замовлення. Форма — ГОЛИЙ МАСИВ замовлень; елемент:
    `{id, uuid, project_id, branch_id, user_id(logbook_id), fio,
    status, notes, delivery_notes, external_id, receipt, created_by(_fio),
    updated_by(_fio), created_at, updated_at, deleted_at, onec_code,
    products[{sku, image[], id, order_id, product_id, quantity, created_at,
    updated_at, order_product_price[{price, currency(DIA|COI|BEV)}], title, text,
    edu_forms[]}], can_discard}`.

    **Статуси замовлення**: `1|3` — нове; `2|5` — скасоване (isDiscarded); `4` — закрите.
    Скасування можливе при `can_discard=true` і статусі ∉ {2,5,4} → `PUT /shop/discard-order`."""
    return await handle(
        request,
        sample=[
            {
                "id": 480001,
                "uuid": "0c1f8b3e-6d4a-4a5f-9d3c-8f2b7a1e55aa",
                "project_id": 50,
                "branch_id": 4,
                "user_id": 100001,
                "fio": "Коваленко Олександр Сергійович",
                "status": 1,
                "notes": None,
                "delivery_notes": None,
                "external_id": None,
                "receipt": None,
                "created_by": 63000,
                "created_by_fio": "Ірина Мельник",
                "updated_by": 63000,
                "updated_by_fio": "Ірина Мельник",
                "created_at": "2026-08-10T12:00:00.000000Z",
                "updated_at": "2026-08-10T12:05:00.000000Z",
                "deleted_at": None,
                "onec_code": "000000001",
                "products": [
                    {
                        "sku": "219",
                        "image": ["https://fs3.itstep.org/api/v1/files/DEMOFILE"],
                        "id": 900001,
                        "order_id": 480001,
                        "product_id": 46001,
                        "quantity": 1,
                        "created_at": "2026-08-10T12:00:00.000000Z",
                        "updated_at": "2026-08-10T12:00:00.000000Z",
                        "order_product_price": [
                            {"id": 1800001, "order_product_id": 900001, "price": 196, "currency": "COI", "created_at": "2026-08-10T12:00:00.000000Z", "updated_at": "2026-08-10T12:00:00.000000Z"},
                            {"id": 1800002, "order_product_id": 900001, "price": 84, "currency": "DIA", "created_at": "2026-08-10T12:00:00.000000Z", "updated_at": "2026-08-10T12:00:00.000000Z"},
                        ],
                        "title": "Окуляри",
                        "text": "Іміджеві окуляри (демо)",
                        "edu_forms": [],
                    }
                ],
                "can_discard": True,
            },
            {
                "id": 480002,
                "uuid": "7b2d9c4f-1e5b-4c6a-b8d9-2a3f4e5d6c7b",
                "project_id": 50,
                "branch_id": 4,
                "user_id": 100001,
                "fio": "Коваленко Олександр Сергійович",
                "status": 4,
                "notes": None,
                "delivery_notes": None,
                "external_id": None,
                "receipt": None,
                "created_by": 63000,
                "created_by_fio": "Ірина Мельник",
                "updated_by": 63000,
                "updated_by_fio": "Ірина Мельник",
                "created_at": "2026-06-02T09:40:00.000000Z",
                "updated_at": "2026-06-15T18:20:00.000000Z",
                "deleted_at": None,
                "onec_code": "000000001",
                "products": [],
                "can_discard": False,
            },
        ],
    )


@router.post("/shop/create-order", summary="Створити замовлення (createOrder)", tags=["Shop"])
async def create_order(
    request: Request,
    ctx: AuthCtx = Depends(auth_ctx),
    body: Optional[CreateOrderIn] = None,
) -> Any:
    """**POST /v1/mystat/{branch_alias}/shop/create-order** ✅

    Тіло підтверджено кодом фронту (transformPayload):
    `{products:[{product_id, quantity}], merchant: "Gaming"(оплата бонусами)
    | "IPayShop"(online)}`; при онлайн-оплаті фронт відкриває `urlLink`
    з відповіді (`window.open(t.urlLink,'_blank')`)."""
    payload = body.model_dump() if body else {}
    return await handle(
        request,
        sample={
            "status": "ok",
            "id": 503,
            "uuid": "9c3e0d5g-2f6c-4d7b-a9e0-3b4c5d6e7f8a",
            "status_code": 1,
            **({"urlLink": "https://pay.example.com/checkout/demo"} if (body and body.merchant == "IPayShop") else {}),
        },
    )


@router.get("/shop/get-providers", summary="Провайдери магазину (масив БЕЗ .data)", tags=["Shop"])
async def shop_providers(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{branch_alias}/shop/get-providers** ✅⚠️

    Фронт (`getProviders`) кладе відповідь ЦІЛКОМ у `providers` (`i || []`) —
    на відміну від club/nutrition НЕ розгортає `.data`.
    Поля елементів ⚠️ (родичі живцем віддають name)."""
    return await handle(request, sample=[{"name": "IPayShop"}, {"name": "Portmone"}])


@router.put("/shop/discard-order", summary="Скасувати замовлення (discardOrder)", tags=["Shop"])
async def discard_order(request: Request, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**PUT /v1/mystat/{branch_alias}/shop/discard-order** ✅

    `discardOrder(uuid)` — тіло ⚠️ містить `uuid` замовлення; після скасування статус ∈ {2,5}."""
    return await handle(request, sample={"status": "ok", "discarded": True})
