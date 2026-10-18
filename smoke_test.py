"""Smoke-тест: піднімає застосунок у TestClient і прогоняє ключові сценарії.

Запуск із теки fastapi/:  python smoke_test.py
"""
import sys

from fastapi.testclient import TestClient

from app.deps import make_fake_jwt
from app.main import app

client = TestClient(app)

failures: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    mark = "OK " if cond else "FAIL"
    print(f"[{mark}] {name} {extra}")
    if not cond:
        failures.append(name)


# ── 1. Інфраструктура Swagger ────────────────────────────────────────────────
r = client.get("/")
check("GET /", r.status_code == 200)

r = client.get("/openapi.json")
check("GET /openapi.json", r.status_code == 200)
spec = r.json()
ops = sum(
    len([m for m in methods if m not in ("HEAD", "OPTIONS")])
    for methods in (p.keys() for p in spec["paths"].values())
)
check("operations >= 60", ops >= 60, f"(отримано {ops})")
check(
    "securitySchemes.bearerAuth",
    any("bearer" in k.lower() for k in spec["components"].get("securitySchemes", {})),
    f"( schemes={list(spec['components'].get('securitySchemes', {}))} )",
)
tags = {t["name"] for t in spec["tags"]}
need_tags = {"Auth", "Branch", "Study", "Homework", "Schedule", "Surveys & Progress",
             "News", "Missions", "Awards & Payments", "Chat", "Shop", "Admin", "Files",
             "Public", "Docs & Info", "Dashboard & Stats", "Contacts", "Payments+",
             "Club", "Nutrition", "Library"}
check("усі теги на місці", need_tags <= tags, f"(немає: {need_tags - tags})")

r = client.get("/docs")
check("GET /docs (Swagger UI)", r.status_code == 200 and "swagger" in r.text.lower())
r = client.get("/redoc")
check("GET /redoc", r.status_code == 200)

# ── 1b. Довідка по сокетах (§9 MYSTAT_API.md) ────────────────────────────────
r = client.get("/v1/info/sockets")
socks = r.json() if r.status_code == 200 else {}
notify = socks.get("notify-socket-logbook.itstep.org", {})
chat = socks.get("chat-socket-logbook.itstep.org", {})
check(
    "GET /info/sockets: handler-реєстр + chat з identify/join_room",
    "socket_notification_handler" in notify.get("server_emits", {})
    and "evaluation_notification" in notify.get("handler_notifications", {}).get("handlers", {})
    and "identify" in chat.get("client_emits", {}),
)

# ── 2. Логін → токен → авторизовані запити ────────────────────────────────
r = client.post("/v1/mystat/auth/login", json={"login": "student", "password": "secret123"})
check("POST /auth/login (text/plain JWT)", r.status_code == 200 and r.text.count(".") == 2,
      f"(ct={r.headers.get('content-type')})")
token = r.text.strip()
H = {"Authorization": f"Bearer {token}"}

r = client.post("/v1/mystat/auth/me", headers=H)
check("POST /auth/me (fixture)", r.status_code == 200 and r.json().get("id_user_storage") == 5000001)

r = client.post("/v1/mystat/auth/me")
check("401 без токена (масив помилок)", r.status_code == 401 and isinstance(r.json()["detail"], list))

# Branch
r = client.get("/v1/mystat/pl/config", headers=H)
check("GET /{alias}/config 🟢", r.status_code == 200 and r.json().get("paymentConfig") == {"need_payment_schedule": True})
r = client.get("/v1/mystat/pl/count/page-counters", headers=H)
check("GET page-counters 🟢", r.status_code == 200 and any(c["counter_type"] == "homework" for c in r.json()))
r = client.get("/v1/mystat/pl/gaming/get-balances", headers=H)
bal = r.json()
check("GET gaming/get-balances 🟢", r.status_code == 200 and any(b["alias"] == "cristals" for b in bal))
check("balances.user_id == logbook_id", bal[0]["user_id"] == 100001)
r = client.get("/v1/mystat/pl/students/get-promo", headers=H)
check("GET get-promo 🟢", r.status_code == 200 and r.json().get("promocode"))
r = client.get("/v1/mystat/pl/profile/get-personal-data", headers=H)
check("GET personal-data 🟢", r.status_code == 200 and "fio" in r.json())

# ❌ вимкнені фічі
for path in ("/counters-header", "/contract/conditions", "/utility/statistic/achievements"):
    r = client.get(f"/v1/mystat/pl{path}", headers=H)
    check(f"❌ 404 {path}", r.status_code == 404)

# Homework / Schedule
r = client.get("/v1/mystat/pl/homework/list?status=3&limit=10", headers=H)
body = r.json()
check("GET homework/list?status=3 (енам статусов)", r.status_code == 200 and "data" in body
      and all(item["status"] in (1, 2, 3, 5) for item in body["data"]))
check("X-Pagination-Page-count заголовок", "x-pagination-page-count" in {k.lower() for k in r.headers.keys()})
check("homework_stud вкладений статус", bool(body["data"]) and "homework_stud" in body["data"][0])
r = client.get("/v1/mystat/pl/homework/100001", headers=H)
check("GET homework/{id} ✅ нове", r.status_code == 200 and r.json().get("id") == 100001)
r = client.get("/v1/mystat/pl/homework/materials?type[]=1", headers=H)
check("GET homework/materials?type[]", r.status_code == 200)
r = client.get("/v1/mystat/pl/schedule/get-month?type=week&date_filter=2026-05-25", headers=H)
check("GET mystat/{alias}/schedule/get-month 🟢(исправлено)", r.status_code == 200
      and r.json().get("start_day") == "2026-05-25" and r.json().get("end_date") == "2026-05-31")
r = client.get("/v1/mystat/pl/schedule/get-existing-schedule", headers=H)
check("GET schedule/get-existing-schedule 🟢", r.status_code == 200 and "daysUntilStartOfHoliday" in r.json())

# Survey / News / Missions / Files
r = client.post("/v1/mystat/pl/survey-user-attempts/123",
                json={"attempts": [{"question_id": 12, "answer": "b"}]}, headers=H)
check("POST survey-user-attempts/{id} (id в пути!)", r.status_code == 200)
r = client.get("/v1/mystat/pl/news", headers=H)
check("GET /news", r.status_code == 200)
r = client.get("/v1/mystat/pl/missions/get-list", headers=H)
check("GET /missions/get-list (исправлено)", r.status_code == 200)
r = client.get("/v1/mystat/pl/user/file-token", headers=H)
ft = r.json()
check("GET user/file-token 🟢", r.status_code == 200 and ft.get("url", "").startswith("https://fs"))

# Нові сервіси (розкриття 2026-08-24)
for path in ("/count/homework", "/statistic/marks", "/progress/leader-points", "/gaming/is-star",
             "/contacts", "/signal/problems-list", "/payment/get-next-payment",
             "/club/get-clubs", "/nutrition/get-balance", "/students/get-qr-code",
             "/library/list", "/settings/history-specs", "/reviews/list"):
    r = client.get(f"/v1/mystat/pl{path}", headers=H)
    check(f"новий GET {path}", r.status_code == 200)

# Admin / Chat / Public
r = client.get("/v1/mystat/pl/admin/list-students", headers=H)
check("GET admin/list-students", r.status_code == 200 and "pl" in r.json())
r = client.post("/v1/mystat/pl/admin/login-student/100001", headers=H)
check("admin/login-student без rolePerm → 403", r.status_code == 403)
H_ADMIN = {"Authorization": "Bearer " + make_fake_jwt(rolePerm={"5": {"admin": ["admin.mystat.view"]}})}
r = client.post("/v1/mystat/pl/admin/login-student/100001", headers=H_ADMIN)
check("POST admin/login-student (?t=JWT)", r.status_code == 200 and "?t=" in r.text)
r = client.get("/v1/mystat/pl/chat/room-list", headers=H)
check("GET /chat/room-list (исправлено)", r.status_code == 200)
r = client.get("/v1/mystat/pl/sender/conversation/messages?id=42&branch_id=4", headers=H)
check("GET /sender/conversation/messages (?id=&branch_id=)", r.status_code == 200 and "messages" in r.json())
r = client.get("/v1/config/1")
check("GET /v1/config/1 🟢", r.status_code == 200 and r.json().get("id") == 50)
r = client.get("/v1/mystat/translate?lang_id=2", headers=H)
check("❌ 404 translate (статика i18n)", r.status_code == 404)

# Info
r = client.get("/v1/info/sockets")
check("GET /v1/info/sockets", r.status_code == 200 and "notify-socket-logbook.itstep.org" in r.json())

# Аватар студента: предмети за бобрів (custom-awards/items) ✅ реверс 2026-08-24
r = client.get("/v1/mystat/pl/custom-awards/balance", headers=H)
check("GET custom-awards/balance {beavers:int}", r.status_code == 200 and isinstance(r.json().get("beavers"), int))
r = client.get("/v1/mystat/pl/custom-awards/items", headers=H)
items = r.json() if r.status_code == 200 else {}
cats = list(items.keys()) if isinstance(items, dict) else []
it0 = items[cats[0]][0] if cats and items[cats[0]] else {}
check(
    "GET custom-awards/items: об'єкт категорій + жива форма item",
    len(cats) >= 4
    and {"id", "img", "prices", "purchased", "equipped", "default", "params"} <= set(it0)
    and (it0["prices"] == [] or (isinstance(it0["prices"][0].get("value"), int) and it0["prices"][0].get("currency") == "BEV")),
)
r = client.get("/v1/mystat/pl/custom-awards/top-achievements", headers=H)
check("GET custom-awards/top-achievements", r.status_code == 200 and isinstance(r.json(), list))
r = client.post("/v1/mystat/pl/custom-awards/items/buy", json={"items": [703]}, headers=H)
check("POST custom-awards/items/buy {items:[ids]}", r.status_code == 200)
r = client.post("/v1/mystat/pl/custom-awards/items/equip", json={"item_id": 703}, headers=H)
check("POST custom-awards/items/equip {item_id}", r.status_code == 200 and r.json().get("item_id") == 703)

# Уточнення реверсу й живих проб 2026-08-24 (раунд «довести до ідеалу»)
r = client.post("/v1/mystat/pl/progress/analyze-performance", json={"spec": 1}, headers=H)
check("POST progress/analyze-performance {spec}", r.status_code == 200 and isinstance(r.json(), list))
r = client.post("/v1/mystat/pl/club/buy-abonement", json={"abonement_id": 5, "entity_id": 11}, headers=H)
check("POST club/buy-abonement {abonement_id,entity_id}", r.status_code == 200)
r = client.get("/v1/mystat/pl/club/download-schedules", headers=H)
check("GET club/download-schedules → {result:url}", r.status_code == 200 and str(r.json().get("result", "")).startswith("http"))
r = client.get("/v1/mystat/pl/nutrition/dish-categories", headers=H)
check("GET nutrition/dish-categories живі коди", r.status_code == 200 and {d.get("code") for d in r.json()} >= {"first", "second", "required"})
r = client.post("/v1/mystat/pl/nutrition/cancellation-order", json={"date": "2026-08-24"}, headers=H)
check("POST nutrition/cancellation-order {date}", r.status_code == 200)
r = client.post("/v1/mystat/pl/nutrition/set-blocked-text", json={"relative_text": None, "prohibited_all": False}, headers=H)
check("POST nutrition/set-blocked-text {relative_text,prohibited_all}", r.status_code == 200)
r = client.get("/v1/mystat/pl/statistic/get-spec/7", headers=H)
j = r.json() if r.status_code == 200 else {}
check("GET statistic/get-spec/{id}: усі поля рядка", r.status_code == 200 and isinstance(j.get("id_spec"), str) and "name_spec" in j)
r = client.get("/v1/mystat/pl/video/link?id_schedule=555", headers=H)
check("GET /video/link?id_schedule= (путь БЕЗ /schedule)", r.status_code == 200 and "link" in r.json())
r = client.get("/v1/mystat/pl/survey/0c9f-demo-uuid/uk", headers=H)
check("GET survey/{uuid}/{lang}: ответ с binds[]", r.status_code == 200 and isinstance(r.json().get("binds"), list))
r = client.get("/v1/mystat/pl/progress-items/get-entity-task-progress-item?entity_id=9&task_id=3", headers=H)
check("GET progress-items/get-entity-task-progress-item", r.status_code == 200)
r = client.get("/v1/mystat/pl/progress-items/123?expand=student,file", headers=H)
check("GET progress-items/{id}?expand", r.status_code == 200)

# Нові фронтові маршрути 2026-08-24 (quiz-родина, shop, give-award, mailing)
r = client.get("/v1/mystat/pl/quiz/opened-interview", headers=H)
check("GET quiz/opened-interview", r.status_code == 200 and "launch_uuid" in r.json())
r = client.get("/v1/mystat/pl/quiz/get-time-between-retries", headers=H)
check("GET quiz/get-time-between-retries (период)", r.status_code == 200)
r = client.get("/v1/mystat/pl/quiz/get-time-between-retries/5", headers=H)
check("GET quiz/get-time-between-retries/{id}", r.status_code == 200)
r = client.get("/v1/mystat/pl/quiz/42", headers=H)
check("GET quiz/{id}: питання answers_list[]", r.status_code == 200 and isinstance(r.json().get("questions"), list))
r = client.post("/v1/mystat/pl/quiz/run/42", json={"id": 42}, headers=H)
check("POST quiz/run/{id} {id}", r.status_code == 200 and r.json().get("status") == "started")
r = client.post("/v1/mystat/pl/quiz/delay-interview", json={"id": 55101}, headers=H)
check("POST quiz/delay-interview {id}", r.status_code == 200 and r.json().get("status") == "delayed")
r = client.post(
    "/v1/mystat/pl/quiz/finish/42",
    json={"data": {"id": 42, "answers": {"101": [1, 2]}}},
    headers=H,
)
j = r.json() if r.status_code == 200 else {}
check("POST quiz/finish/{id} {data:{id,answers}}", r.status_code == 200 and "score" in j)
r = client.get("/v1/mystat/pl/shop/get-providers", headers=H)
check("GET shop/get-providers: массив БЕЗ .data", r.status_code == 200 and isinstance(r.json(), list))
r = client.post("/v1/mystat/pl/custom-awards/give-award", json={"award_id": 3}, headers=H)
check("POST custom-awards/give-award {award_id}", r.status_code == 200 and r.json().get("award_id") == 3)
r = client.post(
    "/v1/mystat/pl/custom-awards/awards",
    json={"name": "Пицца", "icon": "pizza.svg", "value": 50},
    headers=H,
)
check("POST custom-awards/awards {name,icon,value}", r.status_code == 200 and r.json().get("name") == "Пицца")
r = client.put("/v1/mystat/pl/custom-awards/award/3", json={"name": "Пицца XL", "icon": "pizza.svg", "value": 75}, headers=H)
check("PUT custom-awards/award/{id} полная форма", r.status_code == 200 and r.json().get("value") == 75)
r = client.delete("/v1/mystat/pl/custom-awards/award/3", headers=H)
check("DELETE custom-awards/award/{id}", r.status_code == 200)
r = client.post("/v1/mystat/pl/mailing/confirm", json={"key": "demo-token"}, headers=H)
check("POST mailing/confirm {key}", r.status_code == 200)

# Нове у збірці 2026-10: чат (edit/delete), relatives/get-active-children, activity/events
r = client.post("/v1/mystat/pl/sender/conversation/message-edit", json={"id": 1, "text": "x"}, headers=H)
check("POST sender/conversation/message-edit ✅ нове", r.status_code == 200)
r = client.post("/v1/mystat/pl/sender/conversation/message-delete", json={"id": 1}, headers=H)
check("POST sender/conversation/message-delete ✅ нове", r.status_code == 200)
r = client.post("/v1/mystat/pl/relatives/get-active-children", json={"ids": [100001, 100002]}, headers=H)
check("POST relatives/get-active-children ✅ нове", r.status_code == 200 and "active_ids" in r.json() and "groups" in r.json())
r = client.post("/v1/mystat/pl/activity/events", json={"events": [{"section": "main", "seconds": 30}]}, headers=H)
check("POST activity/events ✅ нове", r.status_code == 200)
r = client.post("/v1/mystat/pl/activity/events", json={"events": [{"section": "main", "seconds": 0}]}, headers=H)
check("POST activity/events: seconds>=1 (422)", r.status_code == 422)
r = client.post("/v1/mystat/pl/activity/events", json={"events": []})
check("POST activity/events без токена -> 401", r.status_code == 401)

r = client.get("/v1/info/endpoints")
n = r.json().get("count", 0)
check("GET /v1/info/endpoints", r.status_code == 200 and n >= 60, f"({n} операцій)")

print("\n" + ("=" * 50))
if failures:
    print(f"ПРОВАЛЕНО {len(failures)}: {failures}")
    sys.exit(1)
print(f"УСІ ПЕРЕВІРКИ ПРОЙДЕНО ✔ ({n} операцій в OpenAPI)")
