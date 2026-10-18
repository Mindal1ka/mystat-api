# MyStat (mystat.itstep.org) — повний опис API

> Документ складено реверсом JS-бандлів фронтенду (`main.js`, `chunk-*.js`, версія release `db7a081de8be3397e189690ccca5a0d08c36f1ec`).
> **Оновлення 2026-10-18:** живий фронтенд перезібраний (release `b480fd27846bb1b3edb6a4c65c0fa8bf791ce6bf`, `assets/version.json` усе ще `1.0.3`). Зміни зібрані у [§15](#15-зміни-збірки-2026-10-порівняно-з-2026-08); решта документа описує збірку 2026-08, яка в частині ендпоінтів лишається чинною. Імена чанків у тексті (`BVhovRZH` тощо) — зі збірки 2026-08, у новій збірці всі хеші інші.
> Фронтенд — Angular (standalone), HTTP — Angular HttpClient, реалтайм — socket.io.
> Позначки: ✅ = підтверджено кодом бандлів, ⚠️ = відновлено за непрямими ознаками (імена полів тіла запиту потрібно уточнити перехопленням трафіку).
> Додатково: 🟢 = підтверджено живим запитом реального акаунта (гілка `pl`, сирі відповіді в `examples/*.json`), ❌ = живий запит повернув 404 (фіча вимкнена у філії).

**Зміст:** [1. Базові адреси](#1-базові-адреси) · [2. Аутентифікація та заголовки](#2-аутентифікація-та-заголовки) (+структура JWT) · [3. Auth-ендпоінти](#3-auth-ендпоінти-без-гілки) · [4. Похідні значення акаунта](#4-акаунт--похідні-значення) · [5. Конфіг філії та загальні дані](#5-конфіг-філії-та-загальні-дані-з-гілкою) · [6. Навчальні сервіси](#6-навчальні-сервіси-з-гілкою) · [7. Адмін](#7-адмін-розділ-роут-admin) · [8. Файловий сервіс](#8-файловий-сервіс-) · [9. Сокети](#9-сокети-socketio) · [10. Інше](#10-інше) · [11. Карта розділів UI↔API](#11-карта-розділів-ui--api-роути-фронту) · [12. Приклади curl](#12-приклади-запитів-curl) · [13. Зведена таблиця](#13-зведена-таблиця-ендпоінтів) · [14. Розділи з лінивих чанків](#14-розділи-з-лінивих-чанків-) · [15. Зміни збірки 2026-10](#15-зміни-збірки-2026-10-порівняно-з-2026-08)

---

## 1. Базові адреси

| Призначення | URL |
|---|---|
| REST API (base) | `https://mapi.itstep.org/v1` |
| Модуль API | `/mystat` → підсумковий base: `https://mapi.itstep.org/v1/mystat` |
| Гілка (branch) | `https://mapi.itstep.org/v1/mystat/{branch_alias}` — префікс додається до всіх «гілкових» ендпоінтів |
| Конфіг застосунку | `GET https://mapi.itstep.org/v1/config/1` (шаблон: `/config/{appId}`, appId=1) |
| Переклади | `GET https://mapi.itstep.org/v1/mystat/translate?lang_id={code}` |
| Notify-сокет (сповіщення) | `https://notify-socket-logbook.itstep.org` (socket.io) |
| Log-сокет (трекінг активності) | `https://log-socket-mystat.itstep.org` (socket.io) |
| Chat-сокет | `https://chat-socket-logbook.itstep.org` (socket.io) |
| Файловий сервер | динамічний, видається в `user/file-token` → зараз `https://fsx3.itstep.org/api/v1/files` 🟢 (аватарки — на `fsx1`, статика фронту — на `fs1`) |
| Sentry tunnel | `https://mapi.itstep.org/sentry` |

### Середовище (з `chunk-w36jqjFL.js`) ✅
```js
{
  production: true,
  configuration: "production",
  release: "db7a081de8be3397e189690ccca5a0d08c36f1ec",
  apiUrl: "https://mapi.itstep.org/v1",
  notifySocketUrl: "https://notify-socket-logbook.itstep.org",
  logSocketUrl: "https://log-socket-mystat.itstep.org",
  chatSocketUrl: "https://chat-socket-logbook.itstep.org",
  cryptoKey: "<REDACTED: статичний ключ із публічного environment-чанка>",
  apiModule: "mystat",
  appId: 1,
  appName: "MyStat",
  isMultiBranches: true          // → всі сервіси ходять з префіксом /{branch_alias}
}
```

---

## 2. Аутентифікація та заголовки

### Схема ✅
- Токен доступу — **JWT у вигляді plain text** (запити логіну/рефрешу робляться з `{responseType: "text"}`).
- Зберігається в `localStorage` під ключем **`access_token`**.
- Заголовок авторизації: `Authorization: Bearer <access_token>` (конфіг: `authScheme: "Bearer "`, `headerName: "Authorization"`).
- Адмінський токен зберігається окремо: `admin_token`, прапорець `admin_login = "1"`.
- JWT несе весь профіль (повний набір claims — див. «Структура JWT» нижче): фронт бере з payload `branch_alias`, `lang`, `id_user_storage`.

### Заголовки запитів ✅
| Заголовок | Значення | Коли |
|---|---|---|
| `Authorization` | `Bearer {access_token}` | всі авторизовані запити до mapi та до файлового сервера |
| `X-Language` | код мови з акаунта (`lang`), напр. `ru`/`ua` | завжди (якщо відомий) |
| `X-UserId` | `id_user_storage` 🟢 (= `account.user_profiles[*][*].user_id`); це НЕ `logbook_id` (JWT.sub)! | завжди після логіну |
| `X-XSRF-TOKEN` | з cookie `XSRF-TOKEN` | стандартний механізм Angular (може не застосовуватись крос-доменно) |
| `ngrok-skip-browser-warning: 69420` | extra header socket.io-з'єднань | сокети |

### Логіка збирання URL (інтерцептор) ✅
1. Якщо URL починається з `http://` / `https://` або `/assets/` — префікси не додаються.
2. Інакше URL доповнюється base: `https://mapi.itstep.org/v1/mystat` + url.
3. «Гілкові» сервіси самі додають `/{branch_alias}` через `getEndpoint()` (бо `isMultiBranches=true`).

Підсумкові форми:
- Без гілки: `/v1/mystat/auth/login`, `/v1/mystat/user-storage/password/send-auth-code`
- З гілкою: `/v1/mystat/{alias}/students/get-products`

### Refresh-логіка (інтерцептор 401/403) ✅
- `401` на `/auth/login` — просто пробросити помилку.
- `401` на `/auth/refresh` — локальний логаут.
- Інші `401` — один раз `POST /auth/refresh` (текст нового токена), повтор запиту з новим токеном; паралельні запити чекають результат (shared subject).
- `403` — проброс; якщо масив помилок виду `[{field:"summary", message}]` — показується toast.

### Ключі localStorage ✅
`access_token`, `admin_token`, `admin_login`, `X-Language`, `X-UserId`, `child_id`, `branch_alias`, `cart`, `per_page`, `file_token` (JSON), `tta`, `login-event`, ключі онбордингу.

### Помилки ✅
Формат помилок — масив об'єктів: `[{ "field": "login" | "password" | "summary", "message": "..." }]`.

### Пагінація ✅
Параметри `page` / `per_page` серіалізуються за форматом бекенду (`paginationFormat`):
- `laravel`: `pagination[page]`, `pagination[per_page]`
- `yii`: `page`, `per_page`
- `flask`: `limit`, `offset`

Значення `per_page` за замовчуванням береться з localStorage `per_page`. Кеш GET-даних — 1800 с.

### Структура JWT-токенів ✅🟢
Обидва токени підписані **HS256**. Payload живого `access_token` (термін дії — рівно 30 днів):
```jsonc
{
  "iss": "https://auth.itstep.org/api/auth/login",
  "iat": 1787517521, "nbf": 1787517521,
  "exp": 1790109521,               // iat + 2 592 000 с = 30 днів
  "jti": "<випадковий id>",
  "sub": 100001,                    // = "id" — logbook_id студента
  "id": 100001,
  "id_user_storage": 5000001,      // → заголовок X-UserId
  "email": "...", "username": "...", "name": "Ім'я Прізвище",
  "branch_id": 4, "project_id": 50, "lang": "uk",
  "profile": "student",            // student | relative | ...
  "module": "mystat", "branch_alias": "pl"
}
```

⚠️ У системі **два різні числові ID** — не плутати:
| ID | Що це | Де зустрічається |
|---|---|---|
| `logbook_id` | запис студента в журналі | JWT `sub`/`id`; `balances[].user_id`; адмінський `list-students` → `id_stud` |
| `id_user_storage` | акаунт у user-storage | заголовок `X-UserId`; `user_profiles[*][*].user_id`; ⚠️ ймовірно `user_id` у payload notify-сокета |

`file_token` (див. §8) — окремий JWT рівно на 48 годин:
```jsonc
{ "jti": "...", "projectId": 5, "extId": 44557,
  "userId": "100001",               // рядком, це logbook_id!
  "subData": null, "access": ["file.create"] }
```

---

## 3. Auth-ендпоінти (без гілки)

Конфіг auth ✅:
```js
{
  endpointLogin:         "/auth/login",
  endpointLogout:        "/auth/logout",
  endpointAccount:       "/auth/me",
  endpointRefresh:       "/auth/refresh",
  endpointRecovery:      "/auth/password/link",
  endpointCheckToken:    "/auth/password/check",
  endpointResetPassword: "/auth/password/reset",
  endpointCreatePassword:"/user-storage/password/store", // викликається як apiUrl + "/mystat" + шлях
  routeLogin: "/auth",
  routeAdminLogin: "/admin"
}
```

### POST `/auth/login` ✅
- Body: JSON з полями форми входу (у формі поля `login` і `password`; точний набір полей — у лінивому чанку AuthModule, ⚠️ ймовірно `{login, password}`).
- Відповідь: **text/plain** — рядок JWT.
- Після логіну: токен зберігається → викликається `POST /auth/me` → встановлюються `X-Language`, `X-UserId`, `branch_alias`, `child_id`.

### POST `/auth/logout` ✅
- Body: `{}`. Локально чиститься storage (крім `X-Language`).

### POST `/auth/me` ✅ (підтверджено живим запитом)
Відповідь (student, гілка `pl`; особисті дані знеособлені):
```jsonc
{
  "id": 100001,                        // = JWT.sub/logbook_id
  "id_user_storage": 5000001,         // = JWT.id_user_storage = X-UserId
  "email": "...",
  "username": "...",
  "name": "...",
  "branch_id": 4,
  "project_id": 50,
  "lang": "uk",
  "profile": "student",
  "module": "mystat",
  "branch_alias": "pl",
  "user_profiles": {
    "<project_id>": {
      "<branch_id>": [ {
        "user_id": 5000001, "login": "...", "type": "student", "status": "active",
        "project_id": 50, "branch_id": 4, "division_id": 0,
        "photo": "https://fsx1.itstep.org/api/v1/files/<hash>",
        "id": 3500001, "branch_alias": "pl", "logbook_id": 100001,
        "onec_id": "...", "externals":"", "contacts":"", "properties":"",
        "position_id": null, "updated_by": 1, "created_by": 1
      } ]
    }
  },
  "user_storage": { "firstname","lastname","patronymic","birthdate":"2009-05-14","gender":"","branch_id","id",... },
  // для relative додатково: childs[{id, profiles[{logbook_id, branch_alias,...}]}], rolePerm{...}
}
```

### POST `/auth/refresh` ✅
- Body: `{}`. Відповідь: text/plain — новий JWT.

### POST `/auth/password/link` ✅
- Запит посилання відновлення. Body ⚠️ `{email}`.
- Відповідь: text/plain.

### GET `/auth/password/check?token={token}` ✅
- Перевірка токена з листа.

### POST `/auth/password/reset` ✅
- Скидання пароля. Body ⚠️ `{token, password, passwordRepeat}` (на формі скидання є password/passwordRepeat).

### POST `/mystat/user-storage/password/store` ✅
- Створення пароля (запрошення/перший вхід). Викликається як `apiUrl + "/mystat"` + `/user-storage/password/store`.
- Body ⚠️ `{password, ...}`.

### Швидкий вхід за кодом (SMS) ✅
- `POST /relatives/get-phones-to-auth-by-stud` — отримати телефони студента для входу. Body ⚠️ (ідентифікатор студента). Відповідь — список телефонів.
- `POST /user-storage/password/send-auth-code` — вислати код. Body ⚠️ `{phone}`.
- `POST /auth/login-by-auth-code` — вхід за кодом. Body ⚠️ `{phone/code}`. Відповідь: text/plain JWT.

### Підтвердження телефону при реєстрації ✅ (сервіс endpoint=`/sms`, з гілкою)
- `POST /{alias}/sms/send-code` — body: `null`.
- `POST /{alias}/sms/verified-phone` — перевірка кода. Body ⚠️ `{phone, code}`.

### Підтвердження e-mail ✅
- `POST /{alias}/mailing/confirm` — body `{key}` (ключ із посилання; alias філії передається в query-параметрі посилання).
- Відповідь: `{message, type}` або помилка → `email_is_not_confirmed`.

---

## 4. Акаунт — похідні значення

Повна структура відповіді — в §3 (`POST /auth/me`, 🟢 живий приклад). Правила, за якими фронт її читає ✅:
- `branchAlias = child?.branch_alias ?? account?.branch_alias`;
- для `relative`: береться `childs[0]` (або обраний `child_id`), з нього `profiles[0].logbook_id` → заголовки/storage;
- адмін-доступ: наявність `admin.mystat.view` у будь-якій гілці `rolePerm`;
- `X-Language` = `lang`, `X-UserId` = `id_user_storage` 🟢 (= `user_profiles[*][*].user_id`);
- у `balances[].user_id` фігурує інший ID — `logbook_id` (див. §2 «Структура JWT»).

---

## 5. Конфіг філії та загальні дані (з гілкою)

### GET `/{alias}/config` ✅🟢
Відповідь — великий об'єкт: інфо про проєкт + навігація + платежі + група студента + прапорці філії.
Реальна структура (гілка `pl`, довгі значення скорочені):
```jsonc
{
  // проєкт (ті самі поля, що й у /v1/config/1)
  "id": 50, "uuid": "a98b7f58-...", "name": "Lbapi", "alias": "lbapi",
  "currency_code": "EUR", "language_code": "uk",
  "logo": "data:image/png;base64,...",
  "has_admin": 1, "has_frontend": 1, "is_multilang_branches": 0,
  "currencies": [ { "code": "USD", "name": "Dollars", "symbol": "$" } /* ~20 валют */ ],

  // навігація
  "menuItems": ["main", "progress", "schedule", ...],   // які пункти меню показувати
  "menuItemsDetails": {
    "main": ["payment","attendance","awards","average_mark","marks","homeworks","reviews","leaderboard"],
    // аналогічні блоки для: header, profile, progress, schedule, materials,
    // review, contacts, news, homework, shop, awards, clubs, payment
  },

  // платежі
  "paymentConfig": { "need_payment_schedule": true },

  // група студента (масив)
  "group": [
    {
      "id_tgroups": 1001, "id_streams": 398, "id_dir": 103,
      "curator_id": null, "name_tgroups": "П-101", "arc_tgroups": 0,
      "is_merged": 0, "azure": null,
      "is_special_schedule": 0, "special_days_per_week": null,
      "special_lessons_per_day": null, "lessons_type": 0, "link_to_group": null
    }
  ],

  // форми навчання
  "studyForm":     [ { "id_form": 5, "form_name": "МКА (вихідні)", "form_status": 0 } ],
  "baseStudyForm": { ... },

  // прапорці філії
  "country": "...", "is_school": false, "is_college": false,
  "is_children_form": ..., "is_globus": false, "is_third_party": ...,
  "show_languages": [...],

  // онбординг-підказки (див. /stud-passed-instructions)
  "instructions": [ { "type": "welcome" | "achievements" } ]
}
```

### GET `/{alias}/count/page-counters` ✅🟢
Лічильники-бейджі пунктів меню; фронт читає через `getCounterNumber(counter_type)`:
```jsonc
[
  { "counter_type": "homework",  "counter": 0 },
  { "counter_type": "review",    "counter": 0 },
  { "counter_type": "news",      "counter": 0 },
  { "counter_type": "materials", "counter": 0 },
  { "counter_type": "chats",     "counter": 0 }
]
```

### GET `/{alias}/gaming/get-balances` ✅🟢
Масив балансів гейміфікації — один запис на валюту (`alias` ∈ `cristals` | `coins` | `achivements`):
```jsonc
[
  {
    "id": 1101313, "user_id": 100001, "award_id": 50,
    "value": 170,                       // скільки одиниць нараховано
    "rating": 446,                      // рейтинг
    "project_id": 50, "branch_id": 4,
    "created_at": "2024-09-10T09:30:30.000000Z",
    "updated_at": "2026-06-04T14:40:22.000000Z",
    "alias": "cristals"
  }
  // далі записи з alias "coins" і "achivements"
]
```
Фронт збирає з них об'єкт `amount` (за alias).

### GET `/{alias}/students/get-promo` ✅🟢 — реферальний промокод (nullable):
```jsonc
{
  "promocode": "DEMO1",
  "promo_url": "https://branch.example.org/uk/promocode?token=<base64({\"p\":promocode,\"o\":phone})>",
  "is_school": false, "is_college": false, "is_globus": false,
  "amount": 500                                  // бонус за реферала
}
```
### GET `/{alias}/students/get-products` ✅🟢 — спец. пропозиції; якщо нема що показати → `[]`.
### GET `/{alias}/profile/check-moderating-data` ✅🟢
```jsonc
{
  "photo": null,
  "email": { "verified_status": "0", "email_address": "...@student.itstep.org" },
  "phone": { "phone_number": "+380...",        "verified_status": "0" }
}
```
### GET `/{alias}/profile/get-personal-data` ✅🟢
```jsonc
{
  "photo": "https://fsx1.itstep.org/api/v1/files/<hash>",   // або null
  "photo_alternative": null,
  "fio": "Прізвище Ім'я По батькові",
  "birthdate": "2009-05-14",
  "emails": [ { "value": "особистий@gmail.com" }, { "value": "логін@student.itstep.org" } ],
  "phones": [ { "value": "+380..." } ]
}
```
### POST `/{alias}/profile/change-personal-data?{params}` ✅
Body ⚠️: `{birthdate, phone, email, file(фото)...}`; query-параметри передаються окремо (напр. id дитини для батька).

### GET `/{alias}/counters-header` ✅❌
Полегшений лічильник для хедера (виняток із глобального лоадера — викликається часто).
❌ На живому API для гілки `pl` повернув 404 — ендпоінт увімкнений не в усіх філіях; фронт переживає його відсутність без помилок.

---

## 6. Навчальні сервіси (з гілкою)

### Students (endpoint `/students`)
| Метод | Шлях | Опис |
|---|---|---|
| POST | `/{alias}/students/evaluate-lesson` | оцінка уроку. Body ⚠️ `{lesson_id, rate/star, teacher_star?, comment?}` |
| GET | `/{alias}/students/get-products` | продукти/апсели. 🟢 порожньо → `[]` |
| POST | `/{alias}/notification/create` | рапорт про відсутність (форма: тип `late/absence`, дата, коментар). Body ⚠️ |
| POST | `/mystat/user-storage/relative` (absolute, без гілки) | додати родича. Body ⚠️ `{firstname, lastname, ..., created_by: id_user_storage, contacts:[{channel:"mail", value}]}` |

### Contract (endpoint `/contract`)
| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/contract/conditions` | умови договору. ❌ 404 на живому API (гілка `pl`) — фіча вимкнена у філії |
| POST | `/{alias}/contract/suspend` | призупинення навчання. Body ✅ `{comment}` (min 10 символів) |

### Cyberfit (endpoint `/cyberfit`)
| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/cyberfit/get-stats?{params}` | статистика Cyberfit. 🟢 200, порожньо якщо не підключений |

### Utility (endpoint `/utility`)
| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/utility/statistic/achievements?{params}` | досягнення. ❌ 404 на живому API (гілка `pl`) |
| POST | `/{alias}/utility/social-review/screen-review?{params}` | надсилання відгуку з екрана ✅ body: `{filename:<link з file-token>, clientFilename:<оригінальне ім'я>, link_id:<link_id слота>}`, файли заздалегідь вантажаться в files з каталогом `reviewDirId`; один запит на кожен файл |
| GET | `/{alias}/utility/social-review/get-review-list?{params}` | список відгуків. ❌ 404 на живому API (гілка `pl`) |
| GET | `/{alias}/utility/social-review/get-study-place-list?{params}` | список місць навчання для відгуку. ❌ 404 на живому API (гілка `pl`) |

### Онбординг (endpoint `/stud-passed-instructions`)
| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/stud-passed-instructions` | пройдені інструкції. 🟢 поки нічого не відмічено → `[]` |
| POST | `/{alias}/stud-passed-instructions` | відмітити пройденою. Body ✅ `{type: "welcome" \| "achievements" \| ...}` |

### Переклади
| Метод | Шлях | Опис |
|---|---|---|
| GET | `/v1/mystat/translate?lang_id={code}` | словник перекладів. ❌ **404 на живому API** — ендпоінт прибрано з прода |
| GET | `https://mystat.itstep.org/assets/i18n/{code}.json` | 🟢 актуальне джерело перекладів — статика ~62 КБ (`uk` підтверджений); фронт робить `translate.setTranslation(lang, відповідь)`. Для своєї версії просто беріть цей файл |

---

## 7. Адмін-розділ (роут `/admin`) ✅

| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/admin/list-students` | список студентів. Відповідь: `{ "<branch_alias>": [ { "id_stud": 123, "fio": "Іванов І." } ] }` |
| POST | `/{alias}/admin/login-student/{id_stud}` | увійти як студент. Відповідь: **text** — URL виду `https://.../?t=<JWT>`; клієнт витягує параметр `t` як access_token студента |

Логіка: адмін обирає студента → `localStorage.branch_alias = <alias студента>` → login-student → токен зберігається в `access_token`, адмінський залишається в `admin_token`, ставиться прапорець `admin_login="1"`.

Доступ в адмінку визначається за `rolePerm.*.*.includes("admin.mystat.view")`.

---

## 8. Файловий сервіс ✅🟢

### GET `/{alias}/user/file-token`
Відповідь (зберігається як localStorage `file_token`; живий приклад):
```jsonc
{
  "url": "https://fsx3.itstep.org/api/v1/files",   // база файлового сервера — ДИНАМІЧНА
  "domain": "https://fsx3.itstep.org",
  "token": "<JWT ≈ на 2 доби: claims {projectId:5, extId, userId, access:['file.create']}>",
  "directories": {
    "homeworkDirId":  "<hash>",   // домашні роботи
    "portfolioDirId": "<hash>",   // портфоліо
    "reviewDirId":    "<hash>",   // рев'ю
    "examDirId":      "<hash>",   // екзамени
    "photoStudDirId": "<hash>",   // фото студента
    "chatDirId":      "<hash>"    // вкладення чату
  }
}
```
⚠️ Хост не фіксований: зараз видається `fsx3`, аватарки студентів віддаються з `fsx1`, статика фронту лежить на `fs1`. У своєму клієнті завжди беріть `url` з цієї відповіді, не хардкодьте.

Усі запити до `url` підписуються: `Authorization: Bearer <token>` + `X-Language`.

| Метод | Шлях | Опис |
|---|---|---|
| POST | `{url}` | завантаження. multipart/form-data: `directory=<ім'я каталогу>`, `files[]=<File,...>` (кілька). Прогрес через upload events. Відповідь — JSON (шляхи файлів) |
| GET | `{url}/info/{filename}` | мета файлу |
| DELETE | `{url}/{path}` | видалити файл |
| POST | `{url}/replace-file` | замінити. multipart: `file`, `token=<шлях старого файлу>`, `keepOriginalName=true/false`, `makeBackup=false/true` |

Статичні ассети фронту лежать на `fs1`: `https://fs1.itstep.org/api/v1/files/DEMOFILE` (прапорці телефонів); користувацькі файли — на динамічному хості з `file-token` (`fsx3`), аватарки — на `fsx1`.

---

## 9. Сокети (socket.io)

Три окремі socket.io-сервери (движок engine.io). Базова обгортка — `SocketModule`
у main.js ✅:
```js
io(url, {
  path: "/socket.io",                    // движок engine.io
  query: { alias: "<branch_alias>" },    // гілка
  auth: { token: "<access_token з localStorage>" },  // JWT
  extraHeaders: { "ngrok-skip-browser-warning": "69420" }
})
```
**Reconnect** ✅: після кожного `connect` обгортка підписується на зміну гілки
(фільтри) та оновлення `access_token` у storage → `reconnect()` = перечитати
`query`+`auth`, `disconnect().connect()`. Тобто при зміні гілки або
оновленні токена всі сокети перепідключаються з новими даними.

### Notify-сокет `wss://notify-socket-logbook.itstep.org` (чанки 8lGH9t5Y, Chm3fOqc)

**Кімнати** ✅: при кожному `connect` (через 1 с) клієнт робить:
```js
emit("join_room", {
  rooms: ["global",
          "<profile>_personal_<id_user_storage>",       // особиста
          "<profile>_group_<id_tgroups>",               // за правами
          "<profile>_stream_<id_streams>",
          "<profile>_dir_<id_dir>"],
  user_id, unread: true
})
```
де `<profile>` — `account.profile` (напр. `student`). Після `disconnect` прапорець
скидається — кімната перепідключається знову.

Клієнт → сервер (emit) ✅:
| Подія | Payload |
|---|---|
| `join_room` | `{rooms[], user_id, unread: true}` — при кожному connect |
| `notification_filter` | `{user_id, unread: bool}` — переключення фільтра «непрочитані» |
| `notification_next_page` | `{user_id, count: <скільки вже завантажено>, unread}` |
| `notification_status_change` | `{id, user_id}` — відмітити ОДНЕ прочитаним (клік по нотифікації) ✅ |
| `notification_status_all_read` | `{user_id}` — «прочитати все» |
| `notification_remove_handler` | `{id, user_id}` — прибрати handler-сповіщення (глобальне — див. room) |
| `notification_remove_room_handler` | `{id, roomId}` — прибрати handler у room-сповіщення (`isGlobal`) |
| `notification_remove_message_handler` | `{id, user_id, removeHandler: true}` — після закриття модалки-handler'а ✅ |
| `notification_hide_until` | `{user_id, id, hide_until: <timestamp ms>}` — «сховати до…» |

Сервер → клієнт (on) ✅:
| Подія | Payload |
|---|---|
| `socket_notification_list` | `{notifications[], pagination}` — первинний список ✅ |
| `socket_notification` | нова нотифікація (поле `data` — JSON-рядок, клієнт парсить) |
| `socket_notification_counter` | `{type: "total_counter", unread: n}` |
| `socket_notification_more` | `{notifications[], pagination:{total}}` — наступна сторінка |
| `notification_filtered` | `{notifications[], pagination}` після фільтра |
| `notification_status_updated` | `{id, read, handlerButtons?}` — статус однієї нотифікації змінився (галочки синхронізуються між вкладками) ✅ |
| `marked_all_read` | підтвердження «прочитати все» |
| `socket_notification_handler` | **подія-хендлер** (модальні сценарії): `{id, handler, data:{…}, hide_until?<ms>}` (+ `isGlobal`/`roomId` у room-хендлерів) |

#### Реєстр хендлерів `socket_notification_handler` ✅ (чанк Chm3fOqc)
- Якщо `hide_until > Date.now()` — клієнт **мовчки пропускає** показ; доступ гейтається пермішенами
  `handlers_<handler>` \| `handlers_*`.
- Черга з cooldown **800 мс**; підряд ідучі `evaluation_notification` батчаться в **один** діалог.
- Значення hide_until: оцінка заняття — **1 година** (`3600*1e3`, чанк uoRIxOfz), фото — **24 год** (`24*3600*1e3`).

| handler | Дія клієнта |
|---|---|
| `evaluation_notification` | діалог «Оцініть заняття»; `data:{evaluation_lesson_id, teach_name, teach_photo, theme}`; submit → `POST /students/evaluate-lesson {mark_lesson, mark_teach, comment, id: data.evaluation_lesson_id}`; «Сховати» → emit `notification_hide_until {user_id:<id_user_storage>, id, hide_until: Date.now()+3600e3}` (**1 година**, потім пере-показ) |
| `happy_birthday_student_handler` | модалка вітання; закриття → emit `notification_remove_handler {id, user_id}` |
| `new_survey` | опитувальник (`surveyService.initSurvey(payload)`) |
| `update_student_photo_handler` | діалог завантаження фото (`data`); відхилити → `notification_hide_until …+24*3600e3` (**24 год**); прийняти → `notification_remove_handler` |
| `new_news_handler` | довантажує новину за `data.news_id` і показує модалку; закриття → `notification_remove_handler {id, user_id}` |
| `homework_rejected_notification` | «ДЗ на доопрацювання» ⚠️ тіло data не зафіксовано |
| `payment_required_notification` | «потрібна оплата» ⚠️ тіло data не зафіксовано |
| `nutrition_order_notification` | замовлення харчування ⚠️ тіло data не зафіксовано |

Шлях від події до надсилання оцінки — див. §14, розділ «Students — оцінка заняття».

### Log-сокет `wss://log-socket-mystat.itstep.org` (чанк Chm3fOqc) — трекінг активності

Клієнт накопичує час активності за ключами (глобальний `g_tta` + ключі сторінок) у
localStorage `tta`, **зашифрованому** cryptoKey'єм з env-конфігу ✅:
- дельта активності **> 2 хв** (`1e3*60*2`) не зараховується (anti-AFK: таймер просто скидається);
- коли накопичено **≥ 10 с** (`1e3*10`) — надсилання та скидання лічильників.

| Подія | Payload |
|---|---|
| `user.log` | `{user: {accessToken}, u_tta: <СИРИЙ зашифрований рядок з localStorage 'tta'>, app_id: 1, app_version}` ✅ |
| `operation.log` | `{user: {accessToken}, data: {...}, app_id, app_version, branchAlias}` ✅ (ім'я події з крапкою) |

### Chat-сокет `wss://chat-socket-logbook.itstep.org` ✅ (чанк BVhovRZH — сервіс, w5Z3py2Q — UI)

**Ідентифікація** ✅ (сервіс в основному бандлі, не в лінивому чанку чату):
```js
on("connect") → emit("identify", {profile: "student"|…, userId: <user_storage id>})
             → чекаємо on("identified")
             → emit("join_room", {rooms: [<id бесіди>, String(branch_id)]})
```
(`identify`/`join_room` Є в поточному бандлі — у ранній ревізії доки були
зняті помилково. У лінивому чанку UI чату їх нема — там тільки надсилання/прийом повідомлень.)

Клієнт → сервер (emit):
| Подія | Payload |
|---|---|
| `message_out_send` | `{roomId: <conversation_id>, message:{message, attachments[посилання файлів], created_at ISO, size_kb,…}}` — вкладення спочатку заливаються файловим сервісом (CHAT_DIR_ID), потім у message йдуть посилання |

Сервер → клієнт (on):
| Подія | Payload |
|---|---|
| `socket.incoming.message` | `{conversation_id, id, type_send, message, status, created_at, user_id, user_fio, user_photo, attachments[]}` — фронт розкладає в `messages[<дата>]` обраної бесіди |
| `conversation_updated` | оновлення статусу бесіди |
| `conversation_messages_counter` | оновлення лічильників непрочитаних |

---

## 10. Інше

| Метод | URL | Опис |
|---|---|---|
| GET | `https://mapi.itstep.org/v1/config/1` | конфіг застосунку 🟢: проєкт (id=50 «Lbapi»), `currencies[]`, `appVersions[{version,critical,link}]`, `branches[]`, `languages[]`, `menuItems[]` ✅ |
| GET | `https://mystat.itstep.org/assets/version.json?t=<ts>` | 🟢 `{"version":"1.0.3"}` — фронт порівнює і пропонує перезавантаження при новій версії ✅ |
| POST | `https://mapi.itstep.org/sentry` | тунель Sentry (envelope) ✅ |
| GET | `https://api.ipify.org?format=json`-подібні / country api | список країн для телефонних масок (конфігурований `countryApiConfig.api`) ⚠️ |

YouTube/Vimeo/Loom-посилання уроків розпізнаються за шаблонами, включно з `/api/v1/youtube/` (прев'ю через власний проксі) ⚠️.

---

## 11. Карта розділів UI ↔ API (роути фронту) ✅

Роути верхнього рівня: `/auth` (AuthModule), `/small-screen`, `/admin`, `/email-confirmation/:token`, `/` (MainModule).

Розділи MainModule (ліниві): `main` (Dashboard), `homework` (+ `done`, `examination`), `progress`, `schedule`, `materials`, `review`, `awards`, `missions`, `home-achievements(-stud)`, `shop` (+ `my-orders`, детальна товару), `nutrition`, `clubs`, `payment`, `news`, `cyberfit`, `contacts`, `chat`.

⚠️ Ендпоінти цих сторінок живуть у лінивих чанках, яких нема в наборі файлів:
домашка, успішність, розклад, матеріали, магазин/замовлення/платежі, харчування, клуби, чат, новини.
Відомі за посиланнями чанки: `main-3W3C2Q6I.js`, `chunk-D_xF_Z72.js`, `chunk-Bq7AGarI2.js` (Auth), `chunk-D2sR7hks.js` (Dashboard), `chunk-DVtZKYdc.js` (HomeworkList), `chunk-BtZmIgXz2.js` (Progress), `chunk-CX-QE1u-2.js`, `chunk-BxR4-6Qd2.js`, `chunk-CLVN5htK2.js`, `chunk-qrntOfEt.js`, `chunk-RIK711GE.js`, `chunk-B8kvLnQE2.js` та ін.

Як добратися (якщо знадобиться):
1. Відкрити mystat.itstep.org, DevTools → Network → XHR/Fetch та WS — там видні реальні запити всіх розділів.
2. DevTools → Sources → скачати бракуючі `chunk-*.js` і прогнати ті самі регулярки.

---

## 12. Приклади запитів (curl)

```bash
BASE=https://mapi.itstep.org/v1/mystat
ALIAS=ua   # branch_alias

# Логін (відповідь - текстовий JWT)
curl -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
  -d '{"login":"...","password":"..."}'

# Акаунт
curl -X POST "$BASE/auth/me" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}'

# Конфіг філії
curl "$BASE/$ALIAS/config" -H "Authorization: Bearer $TOKEN" -H "X-Language: ru"

# Лічильники меню
curl "$BASE/$ALIAS/count/page-counters" -H "Authorization: Bearer $TOKEN"

# Баланс гейміфікації
curl "$BASE/$ALIAS/gaming/get-balances" -H "Authorization: Bearer $TOKEN"

# Токен файлового сервера
curl "$BASE/$ALIAS/user/file-token" -H "Authorization: Bearer $TOKEN"

# Завантаження файлу
curl -X POST "$FS_URL" -H "Authorization: Bearer $FILE_TOKEN" \
  -F "directory=avatars" -F "files[]=@photo.jpg"

# Призупинення договору
curl -X POST "$BASE/$ALIAS/contract/suspend" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"comment":"..."}'
```

---

## 13. Зведена таблиця ендпоінтів

| # | Метод | Шлях | Гілка | Auth | Відповідь |
|---|---|---|---|---|---|
| 1 | POST | `/auth/login` | – | – | text JWT |
| 2 | POST | `/auth/logout` | – | Bearer | – |
| 3 | POST | `/auth/me` | – | Bearer | Account JSON 🟢 |
| 4 | POST | `/auth/refresh` | – | Bearer | text JWT |
| 5 | POST | `/auth/password/link` | – | – | text |
| 6 | GET | `/auth/password/check?token=` | – | – | JSON |
| 7 | POST | `/auth/password/reset` | – | – | JSON |
| 8 | POST | `/mystat/user-storage/password/store` | – | – | JSON |
| 9 | POST | `/relatives/get-phones-to-auth-by-stud` | – | – | phones[] |
| 10 | POST | `/user-storage/password/send-auth-code` | – | – | JSON |
| 11 | POST | `/auth/login-by-auth-code` | – | – | text JWT |
| 12 | POST | `/{alias}/sms/send-code` | ✔ | – | JSON |
| 13 | POST | `/{alias}/sms/verified-phone` | ✔ | – | JSON |
| 14 | POST | `/{alias}/mailing/send-confirmation` | ✔ | – | підтвердження e-mail, body `{email}` ✅(бандл ZhxNLKrC) |
| 14b | POST | `/{alias}/mailing/confirm` | ✔ | – | підтвердження за ключем із листа, body `{key}` ✅(бандл u6KDr9Bf; фронт підмінює відповідь на `{message:"email_has_been_confirmed",type:"success"}` / помилка `email_is_not_confirmed`) |
| 15 | GET | `/{alias}/config` | ✔ | Bearer | Branch config 🟢 |
| 16 | GET | `/{alias}/count/page-counters` | ✔ | Bearer | counters 🟢 |
| 17 | GET | `/{alias}/counters-header` | ✔ | Bearer | counters ❌ 404 (pl) |
| 18 | GET | `/{alias}/gaming/get-balances` | ✔ | Bearer | balances 🟢 |
| 19 | GET | `/{alias}/students/get-promo` | ✔ | Bearer | promo 🟢 |
| 20 | GET | `/{alias}/students/get-products` | ✔ | Bearer | products[] 🟢 |
| 21 | POST | `/{alias}/students/evaluate-lesson` | ✔ | Bearer | JSON |
| 22 | POST | `/{alias}/notification/create` | ✔ | Bearer | JSON |
| 23 | POST | `/mystat/user-storage/relative` | – | Bearer | JSON |
| 24 | GET | `/{alias}/profile/check-moderating-data` | ✔ | Bearer | status 🟢 |
| 25 | GET | `/{alias}/profile/get-personal-data` | ✔ | Bearer | profile data 🟢 |
| 26 | POST | `/{alias}/profile/change-personal-data` | ✔ | Bearer | JSON |
| 27 | GET | `/{alias}/contract/conditions` | ✔ | Bearer | conditions ❌ 404 (pl) |
| 28 | POST | `/{alias}/contract/suspend` | ✔ | Bearer | JSON |
| 29 | GET | `/{alias}/cyberfit/get-stats` | ✔ | Bearer | stats 🟢 (порожньо) |
| 30 | GET | `/{alias}/utility/statistic/achievements` | ✔ | Bearer | achievements ❌ 404 (pl) |
| 31 | POST | `/{alias}/utility/social-review/screen-review` | ✔ | Bearer | JSON |
| 32 | GET | `/{alias}/utility/social-review/get-review-list` | ✔ | Bearer | reviews ❌ 404 (pl) |
| 33 | GET | `/{alias}/utility/social-review/get-study-place-list` | ✔ | Bearer | places ❌ 404 (pl) |
| 34 | GET | `/{alias}/stud-passed-instructions` | ✔ | Bearer | instructions 🟢 (порожньо) |
| 35 | POST | `/{alias}/stud-passed-instructions` | ✔ | Bearer | JSON |
| 36 | GET | `/{alias}/user/file-token` | ✔ | Bearer | {url,token,directories} 🟢 |
| 37 | GET | `/{alias}/admin/list-students` | ✔ | Admin | {alias:[{id_stud,fio}]} |
| 38 | POST | `/{alias}/admin/login-student/{id_stud}` | ✔ | Admin | text URL (?t=JWT) |
| 39 | GET | `/translate?lang_id=` | – | опц. | ❌ 404; переклади тепер статикою: `assets/i18n/{code}.json` |
| 40 | GET | `https://mapi.itstep.org/v1/config/1` | – | – | app config 🟢 |
| 41 | POST | `/{alias}/sender/conversation/message-edit` | ✔ | Bearer | body `{id,text}` ✅ (збірка 2026-10) |
| 42 | POST | `/{alias}/sender/conversation/message-delete` | ✔ | Bearer | body `{id}` ✅ (збірка 2026-10) |
| 43 | POST | `/{alias}/relatives/get-active-children` | ✔ | Bearer | body `{ids}` → `{active_ids,groups}` ✅ (збірка 2026-10) |
| 44 | POST | `/{alias}/activity/events` | ✔ | Bearer | body `{events:[{section,seconds,continued?}]}` ✅ (збірка 2026-10) |

### Жива перевірка 🟢 (токен студента, гілка `pl`)
- **OK (200):** №3 me, №15 config, №16 page-counters, №18 balances, №19 promo, №20 products, №24 check-moderating, №25 personal-data, №29 cyberfit, №34 instructions, №36 file-token, №40 app-config. Сирі відповіді — в папці `examples/`.
- **404:** №17 counters-header, №27 contract/conditions, №30 achievements, №32/33 social-review — фічі вимкнені на філії `pl` (на інших гілках можуть працювати); №39 `/translate` — ендпоінт прибрано з прода повністю, переклади тепер статикою `assets/i18n/{lang}.json`.
- Не перевірялися (write-операції / потрібен адмін): №1–2, 4–14, 21–23, 26, 28, 31, 35, 37–39.
- **Масова проба 2026-08-24 (tools/probe_verify.py, 50 шляхів): токен ЖИВИЙ** — 41/50 → 200,
  нуль 401. Ранковий висновок «токен відкликано» був ПОМИЛКОЮ інструмента, не сервера:
  (1) у `probe_verify.ps1` потрапляв порожній/старий `$env:MYSTAT_TOKEN` (змінні оточення
  не живуть між окремими викликами шелла); (2) однострочник PowerShell з токеном інлайном
  ламався об екранування cmd — запит ішов узагалі без `Authorization` → хибний 401.
  Правило: перевірка токена і декод JWT — тільки python-скриптом, що читає `token.txt`
  (`python tools\probe_verify.py` — він же сам підбирає профіль заголовків).
- Заголовки: для API обов'язковий тільки `Authorization: Bearer <jwt>` — перевірено,
  «bearer only» → 200. Браузер додатково шле `X-L-Session` (id сесії, видно в DevTools),
  `Origin`, `Referer`, браузерний `User-Agent` — усе це НЕобов'язково.
- Показові 404 **до** авторизації: `/pl/missions/get-list` і `/pl/missions` (маршрута нема
  на беці філії) та голий `/pl/survey-user-attempts` без `{id}` (маршрут вимагає id у шляху).
  Правило: 401 = шлях існує, токен поганий; 404 = шляху нема взагалі; а 400/500 на кривих
  параметрах теж доводять, що маршрут Є (`gaming/achieve-info/1`,
  `shop/products/get-quantity?product_id=1`, `quiz/opened-interview` → 500;
  `payment/get-offer-contract`, `sender/conversation/messages` → 400 — обидва пізніше відновлені з коду фронту, див. «Реверс-уточнення»).

---

## 14. Розділи з лінивих чанків ✅

> Усі **98 чанків** фронтенду (збірка 2026-08; у збірці 2026-10 їх 98 + `main-*.js` + `polyfills-*.js`) доскачані з `https://mystat.itstep.org/` і розібрані регулярками (2026-08-24).
> Пагінація тут — Laravel-стиль; номери сторінок приходять заголовками відповіді `X-Pagination-Current-Page` / `X-Pagination-Page-count`.

### Homework (endpoint `/homework`, чанки `DngPB5Fy`, `DVtZKYdc`) ✅ розкрито глибше 2026-08-24

> ⚠️ ВИПРАВЛЕНО: раніше тут були вигадані статуси «done/undone». Насправді статус —
> **числовий енам** з коду бандла:

```js
HomeworkStatus = { Done:1, Examination:2, UntilExecution:3, Retake:5 }   // значення 4 не існує
```
Таби клієнта: «До виконання» → `status=3` · «На перевірці/екзамен» → `status=2` · «Виконано» → `status=1`.
У роботи є і вкладений статус розв'язку: `homework_stud.status` — **окремий енам**
(наживо видені `1` — здано, `mark` виставлена, і `6` — не здано: `mark=null`,
`creation_time="-0001-11-30"`, порожній `stud_answer`); відмітка показується тільки якщо
`homework_stud.mark` і статус ≠ Examination. Наживо підтверджені також поля елемента:
`fio_teach`, `name_spec`, `overdue_time`, `file_path`, `comment`, `auto_mark`, `is_retake`,
`unlock_expire`, `communication_history[]`
(`{type_name:"homework_student_comment", comment, date, file, client_filename}`).

**Жива форма відповіді** (2026-08-24, `examples/live/hw-*.json`): `status=1|2|3` → об'єкт
`{"data":[…], "_meta":{currentPage, totalPages, totalCount}}` (пагінація і в `_meta`, і
заголовками `X-Pagination-*`); а от **`status=5` приходить МАСИВОМ секцій**:
`[{"status":3, "data":[…], "_meta":{…}}]` — обгортка-масив, а не об'єкт!

| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/homework/list?{filters}` ✅ | список. Фільтри (точна карта типів параметрів з бандла): `type[]` (`1`=homeworkAndTests, `2`=practicalWord, `3`=essay, `-1`=tests), `spec_id[]`, `sort`, **`status`** (`1\|2\|3\|5`), `overdue` (`1`=прострочені, `0`=не прострочені), `for_last_year`, `limit`, `homework_id`. Пагінація — заголовки `X-Pagination-*` |
| GET | `/{alias}/homework/materials?{filters}` ✅ | матеріали до домашки, той самий фільтр `type[]` (1/2/3/-1) |
| GET | `/{alias}/homework/types` ✅ | типи робіт |
| GET | `/{alias}/homework/{id}` ✅ **новий** | картка роботи (`getHomeworkInfo(b)` → `GET /homework/${b}`) |
| GET | `/{alias}/settings/group-specs?{params}` | специфікації групи (для фільтрів) |
| POST | `/{alias}/homework/create?{params}` | здати роботу; ліміт файлу **25 МБ** (`25*1024*1024`) |
| DELETE | `/{alias}/homework/delete/{id}?{params}` | видалити розв'язок |
| GET | `/{alias}/materials/id/{id}` | матеріал за числовим ID |

Поля елемента списку (шаблон `DVtZKYdc`): `id`, `ospr` (`0`=independent_work,
`1`=practice_work), `is_autotest` (значення `2` → тип підпису «essay»),
`creation_time`, `status`, `homework_stud{status, creation_time, mark}`,
коментар викладача (`teachersComment.comment`).

### Schedule (база `${apiUrl}/mystat/{alias}/schedule` — 🟢 шляхи гілкові, як у всіх)

| Метод | Шлях | Опис |
|---|---|---|
| GET | `…/mystat/{alias}/schedule/get-existing-schedule` 🟢 | календар: `{schedule:[{date,is_holiday}], daysUntilStartOfHoliday, exams}` (`examples/schedule-existing.json`) |
| GET | `…/mystat/{alias}/schedule/get-month?type=week\|month&date_filter=YYYY-MM-DD` 🟢 | розклад; `date_filter` = **понеділок** тижня (1-ше число для місяця); відповідь `{data:[lesson…], start_day, end_date, first_visit_day, last_visit_day}` (`examples/schedule-week.json`) |
| GET | `…/mystat/{alias}/video/link?id_schedule={id_schedule}` ✅🟢 | посилання на трансляцію уроку `{link}`; шлях БЕЗ `/schedule` (літерал бандла DnXa_4eV); неіснуючий `id_schedule` → **422**, варіант `/schedule/video/link…` → 404 |

Поля елемента `data[]`: `is_video_available, schedule_id, date, lesson, started_at,
finished_at, teacher_name, subject_name, room_name, mark, mark_type, homeworks[],
was, was_type, lesson_theme, id_spec, lesson_type, exam[], link_to_lesson,
cn/tl/cl/dz/lb, mark_comments[], lesson_comment, task_attendance_comment{…},
task_attendance_comment_created_by{id_teach, fio_teach, photo_pas, …}, week_day,
task_id, attendance, avg, video_link, tgroup_lessons_type`.

### Тести / прогрес (чанк `8lGH9t5Y`, endpoint `/survey`) ✅ уточнено 2026-08-24
| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/survey/{survey_uuid}/{lang}` ✅уточнено 2026-08-24 | параметри — **UUID опитування та МОВА** (`survey.get(uuid, lang)`, не type/id!); фронт шукає у відповіді `binds[]` → збіжний `survey_lang` → `survey_binds[]{launch_uuid,date_time_to,…}`; питання — `quiz_data[]{question{id,image_url}, answers_list[{id,answer_text}]}` |
| POST | `/{alias}/survey-logs` | лог проходження |
| GET | `/{alias}/survey-user-attempts/{id}` ✅ | спроби: **`{id}` обов'язковий у шляху** (голий шлях без id → 404 ще до авторизації, перевірено наживо) |
| POST | `/{alias}/survey-user-attempts/{id}` body `{attempts:[…]}` ✅ | зберегти спроби |
| DELETE | `/{alias}/survey-user-attempts/{id}` ✅ | видалити спроби |
| POST | `/{alias}/answers/quiz/{qid}` · `/answers/exercise/{qid}` · `/answers/multi/{qid}` | тіло = `getSaveModel()`: `{task_type, question_id, answer:{answer_id:[<id>…]}}` (чекбокси дають масив id у answer_id); типи питання: `1`=oneRightAnswer, `2`=allCorrectOrNone, `3`=multipleAnswers, `4`=ownAnswer, `5`=oneOrOwnAnswer |
| GET | `/{alias}/materials/uuid/{uuid}/{sub}` | матеріал за UUID |
| POST | `/{alias}/progress-item-answers/quizzes/{id}?expand=answers` · `/exercises/{id}?expand=multiProgressItem` | збереження відповідей прогресу |
| GET | `/{alias}/progress-items/get-entity-task-progress-item?entity_name=material&entity_id={id}&task_type=multi&task_id={id}&expand=multiProgressItems` ✅ **новий** | прогрес-айтем сутності |
| GET | `/{alias}/progress-items/{id}?expand={list}` ✅ **новий** | елемент прогресу; expand з бандла: `student,file,comment,answer.file,answer.task_file,answer.points.file,answer.question,answer.questions,answer.questions.task.quiz,answer.questions.answers.task,answer.questions.points,answer.questions.file,answer.questions.task_file` |
| PUT | `/{alias}/progress-items/reject/{id}` body `{id_spec}` | відхилити елемент прогресу |

**Тіла/форми, зняті з фронту і живих проб (2026-08-24):**
- `finishQuiz(id, t)` → `POST /quiz/finish/{id}`, шлеться весь `t` = `{data:{id, answers:{<question_id>:[<answer_id>…], …}}}`; відповідь фронт кладе в `testFinished={finished:true,data:відповідь}` ⚠️; `delay-interview` → `{id}`; `run/{id}` → body `{id:t}`, при помилці тост за `error.code`.
- `POST /custom-awards/give-award` → `{award_id:<t.id>}` (якщо value>balance — фронт спочатку діалог поповнення); успіх → снек `reward_sent`.
- `POST /shop/create-order` → `{products:[{product_id, quantity}], merchant:"Gaming"(оплата бонусами)|"IPayShop"(online)}`; у відповіді `urlLink` для онлайн-оплати (фронт робить `window.open`). `discard-order` — саме **PUT**.
- `POST /club/buy-abonement` → `{abonement_id, entity_id:<club.id>}`; успіх → снек `payment_successful`.
- `GET /club/download-schedules` → це НЕ файл: `{"result":"<посилання файлового сервісу>"}` 🟢.
- `POST /nutrition/cancellation-order` → `{date:"YYYY-MM-DD"}`; `POST /nutrition/set-blocked-text` → `{relative_text, prohibited_all}` (діалог обмежень).
- `GET /nutrition/dish-categories` → `[{name, code}]`; живі коди: `first, second, garnish, bread, baking, drinks, salads, dessert, required` 🟢. `linked-restaurant` без прив'язаної їдальні → **500** 🟢. `weekends-list` фронт смикає 3 рази (той самий день минулого/поточного/наступного місяця) і flat().
- `POST /progress/analyze-performance` → `{spec:<id_spec>}` (кнопка «Докладніше» в картці предмета); відповідь — список секцій index/title ⚠️.
- `GET /statistic/get-spec/{id}` → всі поля РЯДКА: `{id_spec,name_spec,short_name_spec,id_form,id_dir,status}` 🟢.

**Квізи — окремий сервіс** (чанк `KerK84QV`, база гілкова, НЕ всередині `/survey`):
`GET /quiz/{id}` · `POST /quiz/run/{id}` body `{id}` · `POST /quiz/finish/{id}` ·
`POST /quiz/delay-interview` body `{id}` · `GET /quiz/get-time-between-retries/{id}` ·
`GET /quiz/get-time-between-retries?{params}` · `GET /quiz/opened-interview?{params}`.
Усі 7 маршрутів реалізовані в моку (2026-08-24, smoke ✔). Коди помилок родини
(enum бандла, фронт мапить `error.code` → тост): `7001` two_quizzes_at_the_same_time_error ·
`7002` closed_quiz_error · `7003` group_closed_quiz_error · `7004` too_frequent_attempts_error ·
`7005` attempts_are_exhausted_error · `7006` question_not_found_error · `7007` quiz_not_found_error ·
`7008` interview_passed · `7009` two_interviews_at_the_same_time_error · `7010` interview_closed_error ·
`7011` can_not_retake_quiz_lack_of_funds · `7012` interview_inner_exception · `7013` interview_inner_exception_log.

**Прикол з achieve-info:** фронт кличе його «голим» відносним шляхом
`this.httpClient.get(`/kiev/gaming/achieve-info/${t}`)` — минаючи getEndpoint, із захардкодженим
`kiev`. Живі проби 2026-08-24: kiev-варіанти на mapi → 404; на mystat.itstep.org (обидва:
`/v1/kiev/…` і `/v1/mystat/kiev/…`) → HTML-заглушка SPA (не API). Гілковий
`…/mystat/pl/gaming/achieve-info/1` → **500** на неіснуючому id — маршрут живий,
але потрібен реальний id досягнень (джерело `GET /utility/statistic/achievements`,
яке зараз саме віддає 404). Для свого клона використовуйте гілковий шлях.

### Новини (чанк `CxyTFJYr`, endpoint `/news`)
`GET /{alias}/news` · `GET /{alias}/news/{id}` · `POST /{alias}/news/set-mark` · `POST /{alias}/news/set-view-time`

### Місії (чанк `Bxt9wog3`, endpoint `/missions`) ✅ уточнено 2026-08-24
| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/missions/get-list` | список місій (клієнт сам ділить на Super/Base за `mission.category`). ⚠️ Жива проба `mapi/v1/mystat/pl/missions/get-list` → **404** — модуль вимкнено на філії `pl` |
| POST | `/{alias}/missions/send-to-review/{mission_id}` | надіслати місію на перевірку |

Мапінг елемента з бандла: `id, mission{id,name,category,description,deadline,cristals},
coins, imageUrl, status, date_pending, date_rejected`; картинки `assets/images/missions/{img}`.
Енам `MissionStatus`: `OnReview`, `Rejected` (інші значення в бандлі не мелькають ⚠️).

### Нагороди батька / поповнення (чанк `sc20t5_5`, endpoint `/custom-awards`)
| Метод | Шлях | Опис |
|---|---|---|
| GET | `/{alias}/custom-awards/relative/balance?{params}` | баланси дитини |
| GET | `/{alias}/custom-awards/relative/logs?{params}` | історія нарахувань |
| GET/POST | `/{alias}/custom-awards/awards` | список (`{id,name,icon,value}` — поля форми діалогу) / створити; body = `awardForm.getRawValue()` `{name(≤20), icon, value}` ✅ |
| POST | `/{alias}/custom-awards/give-award` ✅ **новий** | вручити готову нагороду дитині; body `{award_id}` ✅(бандл sc20t5_5); реалізований у моку 2026-08-24 |
| PUT/DELETE | `/{alias}/custom-awards/award/{id}` | змінити (PUT = ПОВНА форма `{name,icon,value}`, не патч) / видалити (успіх → снек `success` + `awardsUpdated`) ✅ |
| GET | `/{alias}/custom-awards/icons?{params}` | іконки нагород |
| GET | `/{alias}/custom-awards/topup-options?{params}` | варіанти поповнення |
| GET | `/{alias}/custom-awards/pay-link?{params}` | посилання на оплату |
| GET | `/{alias}/custom-awards/get-providers?{params}` | платіжні провайдери |

#### Аватар студента: предмети за бобрів ✅ (чанки `0A-Vv-q9` + `B_ScMRTO`, endpoint `/custom-awards`)
Сервіс `homeAchievementsStudService`; UI — сторінка досягнень студента (`app-home-achievements-stud`,
блоки `app-avatar-block` / `app-top-awards-block`, i18n `collect_them_to_customize_avatar`):
предмети купуються за бобрів і надягаються на аватар.
- **Флоу кліку по предмету**: не куплений → `POST /items/buy {items:[id]}` → одразу
  `POST /items/equip {item_id}`; вже куплений або `prices: []` → одразу equip.
- 🟢 **ФІЧА ЖИВА НА ПРОДЕ (проба 2026-08-24)**: `GET /items` відповідає ОБ'ЄКТОМ
  `{<код категорії>:[предмети,…]}`; категорії `body`(30) · `mouth`(10) · `eyes`(10) ·
  `background`(16) — разом 66 предметів. Query `?category=` сервер ІГНОРУЄ.
- Форма предмета (жива): `{id, img:<files-url>, prices:[{value:<int>, currency:"BEV"}],
  purchased, equipped, default, params:[]}`; безкоштовні — `prices: []` + `default:true`;
  ціна кнопки = `prices[0].value` (ЧИСЛО).
- `balance` живий: `{"beavers":<int>}` (парсер фронту терпить і вкладені форми).
- `logs`: у живого акаунта `[]`; фронт сортує елементи за полем `date` DESC —
  інші поля елемента ⚠️ (зняти при ненульовій історії).
- `top-achievements`: у живого акаунта `[]`; мапінг фронта: id=`rule_id??id`,
  title=`title||name||label`, count=`value??count??total`, icon=`icon||img`.

| Метод | URL | Опис |
|---|---|---|
| GET | `/{alias}/custom-awards/balance` | баланс бобрів студента ✅🟢 `{"beavers":<int>}` |
| GET | `/{alias}/custom-awards/logs?page=1&per_page=20` | історія нарахувань; елемент зобов'язаний мати `date` |
| GET | `/{alias}/custom-awards/top-achievements?{params}` | топ досягнень (блок «Топ нагород») |
| GET | `/{alias}/custom-awards/items` | каталог предметів аватара — ОБ'ЄКТ за категоріями |
| POST | `/{alias}/custom-awards/items/buy` | купити ВСЕ обране разом: body `{items:[<id>,…]}` |
| POST | `/{alias}/custom-awards/items/equip` | надіти: body `{item_id:<id>}` |

### Чат (чанк `BVhovRZH`, endpoint `/chat`) ✅ уточнено 2026-08-24
`GET /{alias}/chat/room-list?{params}` · `GET /{alias}/sender/conversation/messages?{params}` ·
`GET /{alias}/sender/conversation?{params}` · `POST /{alias}/sender/conversation/decrement-unreaded`

> ⚠️ ВИПРАВЛЕНО: раніше писали `/{sender}/…` (student|relative) як path-параметр.
> У бандлі `senderEndpoint='/sender/conversation'` — **літерал**, без підстановки.
> Список бесід клієнт фільтрує за ключем стану (`Opened`).

Події chat-сокета: emit `message_out_send {roomId, message:{…}}`; on `socket.incoming.message`, `conversation_messages_counter`, `conversation_updated` (`identify`/`join_room` є в основному бандлі — див. §9). Нове у збірці 2026-10: `POST /{alias}/sender/conversation/message-edit {id,text}` і `message-delete {id}` (див. §15).

### Інше
- **Dashboard** (`D2sR7hks`): історія списань (пагінація за заголовками), групування нагород за датами, `balances.rating` для монет.
- **Shop** (чанк `ByDv-LLj2`, endpoint `/shop`) ✅ розкрито 2026-08-24:
  `GET /shop/orders` · `GET /shop/products?page&per_page` (observe:response → пагінація в заголовках) ·
  `GET /shop/products/{id}` · `POST /shop/create-order` · `PUT /shop/discard-order` ·
  `GET /shop/get-providers?{params}` (фронт кладе відповідь ЦІЛИМ у `providers`, тобто масив БЕЗ `.data` —
  на відміну від club/nutrition; реалізований у моку 2026-08-24) · `GET /shop/products/get-quantity?{params}` ·
  `GET /shop/products/get-others?{params}` (функція фронту `getOtherProducts`).
  Статуси замовлення (класи UI): `1|3` — нове, `2|5` — скасоване, `4` — закрите;
  скасування можливе при `can_discard` і статусі ∉ {2,5,4}. Елемент: `{id, uuid, status,
  created_at, updated_at, can_discard, products:[{title,image,quantity,
  order_product_price{DIA,COI,BEV,currency}}]}`; ціна шукається за парою `currency+type`
  (`default`/`discount`). Провайдер з ім'ям `IPayShop` обробляється особливо.
- **Оцінки**: якість у відгуках/мета — рядковий енам `excellent/good/bad`
  (`excellentMarkCount/goodMarkCount/badMarkCount` в `_meta`), read/unread = `'1'/'0'`.

### Сервіси, знайдені глибоким розкриттям 2026-08-24 ✅ (раніше були відсутні в доці)

> Механіка гілок: базовий клас будує шлях як `(multiBranch ? '/'+alias : '') + (path || this.endpoint)`,
> інтерцептор додає префікс `https://mapi.itstep.org/v1/mystat`. Тому «endpoint=/dashboard»
> у класі ще не значить, що він реально дописується до шляхів — див. рядки нижче (взяті з викликів).

> ### 🟢 Живе підтвердження 2026-08-24 (tools/probe_verify.py → examples/live/*.json): 41/50 → 200, нуль 401
> - Dashboard: `count/homework` → `[{counter_type, counter}]` (6 шт., останній 114 = усього Done);
>   `statistic/attendance` і `statistic/progress` **без `period` дають 400** — параметр обов'язковий
>   (`?period=month|year`); `statistic/marks` без періоду → 200 (повний груз ~94 КБ),
>   з `period=month` → `[]`. `leader-points` → `{group:{totalCount, studentPosition, weekDiff,
>   monthDiff}, stream:{…}}`; `leader-table` → `{group:{month:{new_students, top, other},
>   all_time:{…}}, stream:{…}, sliding_rating}`; `progress/activity?new_format=1&per_page=20&page=1` →
>   `[{id, created_at, name:"rule_name_refund_in_shop", icon, award_value, award_alias:"cristals",
>   awards:[{award_alias, award_value}]}]`; `gaming/is-star` → `{week:{result, total_coins,
>   total_cristals}, month:{…}}`.
> - Contacts/Signal: `contacts` (повна структура адрес/телефонів/соцмереж),
>   `get-reference-status` → голий `true`; `signal/problems-list` → `[{id, title}]`.
> - Payment: реквізити `{instruction_link, online_link, full_name, city_id, legacy_payment,
>   one_c_code, has_invoice_access, online_link_has, …}`; `history` → `[{date, amount,
>   description, type, currency:"UAH"}]`; `get-next-payment` → `{one_c_code, debtor_status,
>   critical_debtor_status, amount, date_critical, cw_amount, crm_form_id}`; `schedule` → `[]`;
>   `get-offer-contract` → 400 (параметри не підібрані ⚠️).
> - Club: `get-clubs` → `[{id, type:"club", schema:"offline_menu_select", status:"enabled",
>   sub_type, club_category:"academy", cost, debt, order_edit_until, …}]`;
>   `get-balance`/`transactions`/`abonements` → `[]` (клуб не активований).
> - Nutrition: `students/get-qr-code` → 200, тіло — рядок (QR-картинка);
>   баланс/транзакції/меню → `[]` (їдальня не використовувалась).
> - Library: `library/list` → `{view, data:[{name_spec, data:[{additional:[{url, description,
>   material_id, theme, week_theme, current_week, public_week, material_type, is_new_material,
>   date, sort_date}]}]}]}`; `settings/history-specs` → `[{id, name, short_name}]`.
> - Reviews: `reviews/list` → `{_meta:{currentPage, totalPages, totalCount}, data:[{date,
>   message, spec, full_spec, teacher, view, mark:"excellent", teacher_photo, subject_image}]}`.
> - Інше ✅ 200: `custom-awards/awards|icons|topup-options`, `custom-awards/relative/balance`
>   (→ `{beavers:{value, temp_value, all}}`), `shop/get-providers`, `shop/orders` (реальне замовлення:
>   `{id, uuid, status:5, fio, created_by, created_by_fio, …}` — статус 5 = скасоване ✓),
>   `shop/products` (`quantity`, `dynamic_price:"off"`, `premium_subscription:"off"`, `sku`, `image:[]`),
>   `shop/products/get-others`; `news` І `news/list` — живі обидва; `homework/types`,
>   `settings/group-specs`, `cyberfit/get-stats` (→ `[]`).
> - `GET /students/get-promo` 🟢 (шлях підказаний юзером 2026-08-24): `{promocode:"DEMO1",
>   promo_url:"https://branch.example.org/uk/promocode?token=<base64>", is_school:false,
>   is_college:false, is_globus:false, amount:500}` — реферальний промокод; у base64 токені
>   посилання лежить `{p:<промокод>, o:<one_c_code>}`. `students/page-counters` → 404
>   (page-counters — не API mapi, фронтовий лічильник).

**Dashboard** (чанк `dw0-gB7X2`): `GET /count/homework?{params}` ·
`GET /statistic/attendance?{params}` · `GET /statistic/marks?{params}` ·
`GET /progress/leader-points?{params}` · `GET /gaming/is-star`.

**Statistic / Progress** (чанк `BFcdGx4G`, endpoint `/statistic`): `GET /statistic/progress?{params}` ·
`GET /statistic/attendance?{params}` · `GET /statistic/marks?{params}` ·
`GET /statistic/average-by-specs?{params}` · `GET /statistic/get-spec/{id}` ·
`GET /progress/activity?new_format=1` (клієнт читає заголовки відповіді!) ·
`GET /progress/leader-table?{params}` · `POST /progress/analyze-performance`.
Періоди: енам `month | half_year | year`.

**Contacts / Signal** (чанк `Dh196EpA`, endpoint `/contacts`): `GET /contacts?{params}` ·
`POST /contacts/send-ceo` · `POST /contacts/send-teach` ·
`GET /contacts/get-reference-status?{params}` ·
`GET /contacts/get-reference-data?type=1&{params}` — **завантаження довідки, responseType blob** ·
`GET /signal/problems-list?{params}` · `POST /signal`.

> Живий шейп `GET /contacts` (знято 2026-09, `examples/live/contacts.json`):
> `teach_contacts[]` = `{"id_teach": int, "fio_teach": str}` — ТІЛЬКИ id і ПІБ,
> телефонів/пошти у викладачів НЕМАЄ (вони в `teach_main[].href_teach`,
> `learning_tel`, `tel_room`, `tel_book`). Якщо у філії викладачів нема —
> масив порожній (стара каптура). Мок: `extras.py` (реальні імена полів,
> демо-значення).

**Payment** (чанк `Cn0o3akg`, endpoint `/payment`): `GET /payment?{params}` (реквізити) ·
`GET /payment/history?{params}` · `GET /payment/schedule?{params}` ·
`POST /payment/link` body+params · `GET /payment/get-providers?{params}` ·
`GET /payment/get-next-payment?{params}` · `GET /payment/get-offer-contract`
(клієнт чекає поле `success`).

**Club** (чанк `CLVN5htK2`, endpoint `/club`): `GET /club/get-clubs?{params}` ·
`GET /club/transactions?{params}` · `GET /club/get-balance?{params}` ·
`GET /club/link?{params}` · `GET /club/get-providers?{params}` (клієнт бере `.data`) ·
`GET /club/abonements` · `POST /club/buy-abonement` · `GET /club/download-schedules`.

**Nutrition** (чанк `CetopaL8`, endpoint `/nutrition`): `GET /students/get-qr-code?{params}`
(QR для їдальні) · `GET /nutrition/get-balance?{params}` ·
`GET /nutrition/transactions?{params}` · `GET /nutrition/get-order-menu?date=` ·
`GET /nutrition/link?{params}` · `GET /nutrition/get-providers?{params}` ·
`GET /payments/success?{params}` · `GET /nutrition/weekends-list?date=` ·
`GET /nutrition/menu-for-date?date=` · `GET /nutrition/linked-restaurant` ·
`POST /nutrition/make-order` · `POST /nutrition/cancellation-order` ·
`GET /nutrition/dish-categories?{params}` · `POST /nutrition/set-blocked-text`.
Статус позиції замовлення — рядок, є значення `'cancelled'` (клієнт його відфільтровує).
Діапазон дат меню: попередній/поточний/наступний місяць.

**Library** (чанк `Q0VuxuCI`): `GET /library/list?{params}` · `GET /settings/history-specs`.

**Students — оцінка заняття** (чанк `Chm3fOqc`, endpoint `/students`) ✅ бандл:
`POST /students/evaluate-lesson` — body `{mark_lesson: 1..5, mark_teach: 1..5,
comment: "<рядок>", id: <evaluation_lesson_id>}`.
- **Звідки id уроку**: НЕ з `schedule/*`! Уроки на оцінку приходять **сокет-подією**
  `socket_notification_handler` (notify-сокет) з конвертом `{id, handler:'evaluation_notification',
  data:{evaluation_lesson_id, teach_name, teach_photo, theme}, hide_until?}`; у body береться
  саме **`data.evaluation_lesson_id`** — це НЕ `id` самого сповіщення. Діалог — черга
  (`rateClassArr`; підряд ідучі оцінки батчаться в одне вікно, між хендлерами cooldown 800 мс,
  доступ за пермішеном `handlers_evaluation_notification` / `handlers_*`). «Сховати» → emit
  `notification_hide_until {user_id:<id_user_storage>, id, hide_until: Date.now()+3600e3}`;
  через 1 годину (і при перевідкритті вікна — поки `expires_in >= Date.now()`) оцінка показується повторно.
- Валідація фронту: при `mark_lesson<=3` АБО `mark_teach<=3` поле `comment` обов'язкове
  (≥6 символів), інакше тост `write_comment`.
- Коди помилок (енам): 84221 NOT_FOUND · 84222 ALREADY_USED · 84223 CLOSED_TODAY
  (оцінити можна тільки в день заняття) · 84224 INCORRECT_MARK · 84225 MARK_SAVE_ERROR.

**Реверс-уточнення вечора 2026-08-24** (витягнуто з коду фронтенду, ✅):
- `GET /video/link` (шлях БЕЗ `/schedule` — літерал бандла) — параметр **`id_schedule`**
  (`getVideoLink({id_schedule})`, `lesson.id_schedule`); відповідь `{link}`. Живий чек
  2026-08-24: `/video/link?id_schedule=1` → 422 (маршрут живий, запису нема),
  `/schedule/video/link?id_schedule=1` → 404. Прежні проби з `lesson_id`/`task_id` були повз.
- `POST /notification/create` («Я не прийду») — повний payload форми absence:
  `{category:"late"|"absence"|"online_presence", date_start, date_end, student_id,
  text, additional_answer, additional_text}`; фронт читає `error[0].message`
  (напр. «у вибраний день немає занять»).
- `GET /sender/conversation/messages` — параметри **`{id, branch_id, last_message_id?}`**,
  де id = число conversation.id АБО рядок conversation_id (`"group_<id_tgroups>"`);
  відповідь — `{messages:{<ключ>:[повідомлення…]}}` (дикт груп). Прежній 400 був через
  невірні імена (`room_id`, `page`).
- `POST /sender/conversation/decrement-unreaded` — тіло **`{id}`**, викликається тільки
  коли id числовий.
- `GET /payment/get-offer-contract` — викликається БЕЗ параметрів (`getContractOffer()`);
  клієнт чекає `'success' in response`. Живий 400 при bearer-only — питання заголовків/
  наявності оферти в акаунта.


**Reviews** (чанк `CjKPb4zE2`, endpoint `/reviews`): `GET /reviews/list?{params}` —
жива форма `_meta`: `{currentPage, totalPages, totalCount}`; лічильники якості
(excellent/good/bad) фронт збирає сам за `data[*].mark`.

**Mailing** (чанк `ZhxNLKrC`, endpoint `/mailing`): `POST /mailing/send-confirmation` body `{email}`
(локальний стор `verification.emailExpiry`).

---

## Додаток: приховані механізми фронту (реверз 2026-08-24)

### 🔐 AES-ключ продакшена в бандлі + шифрований трекінг активності
- environment (`chunk-w36jqjFL.js`): `cryptoKey: '<REDACTED: статичний ключ із публічного environment-чанка>'`
  (+ release `db7a081d…`, apiUrl, 3 сокет-хости, appId=1, appName `MyStat`, isMultiBranches=true).
- CryptoService (`chunk-Chm3fOqc.js`, CryptoJS): `AES.encrypt/decrypt(value, cryptoKey.trim())`.
- Трекінг часу (`g_tta`): клієнт **сам** рахує час у застосунку; дельти довші за 2 хвилини
  відкидаються, при накопиченні ≥10 с `g_tta` іде на log-сокет як `u_tta`
  (див. §9). Зберігається в `localStorage.tta` = **AES(JSON `{g_tta:<ms>, …})` тим самим ключем** —
  значення можна розшифрувати і підробити: час «активності» рахується на клієнті,
  на сервер приходить готовим.

### 🖼 Інші цікаві механізми
- Вбудований **HEIF/HEIC-декодер** (Emscripten/WASM, той самий чанк) — прев'ю фото iPhone без конвертації.
- `localStorage.login-event / logout-event` — синхронізація входу/виходу між вкладками (storage events).
- Пасхалок / cheat-кодів / konami-комбо не знайдено; єдиний справжній «секрет» — cryptoKey вище.

---

## 15. Зміни збірки 2026-10 порівняно з 2026-08

**Метод порівняння (2026-10-18):** `GET /assets/version.json` усе ще віддає `1.0.3`, тому версію
для виявлення змін використовувати НЕ можна — порівнюйте `release` (git-sha) із environment-чанка.
Було `db7a081d…` (збірка 2026-08), стало `b480fd27…`. Свіжі публічні бандли скачано в окрему теку й
порівняно з попередніми за *рядковими літералами* (імена змінних у мініфікованому коді інші).
Логін і токени не використовувались.

### Структура збірки
- Точка входу змінилась: тепер `index.html` (SSR/prerender, `data-beasties-container`) підключає
  `main-<hash>.js`, `polyfills-<hash>.js`, `styles-<hash>.css`; раніше було `main.js` з фіксованим іменем.
  Алгоритм збору чанків (how.md §2) працює без змін, але стартувати треба з `index.html`.
- Імена **94 із 99** попередніх файлів змінилися (5 дрібних/спільних чанків побайтово ідентичні); у новій збірці 98 `chunk-*.js` + `main-*.js` + `polyfills-*.js`. Співставляти чанки зі старих секцій за іменем не можна — шукайте за рядками.
- environment: змінився лише `release`; `apiUrl`, три сокет-хости, `apiModule`, `appId=1`,
  `isMultiBranches=true` — без змін. Ключ `cryptoKey` у публічному бандлі лишився тим самим.

### Нові ендпоінти ✅ (усі «гілкові»: `${apiUrl}/mystat/{alias}/…`)
| Метод | Шлях | Тіло → відповідь |
|---|---|---|
| POST | `/{alias}/sender/conversation/message-edit` | `{id, text}`; у UI чату з'явився режим редагування (банер `chat_editing_message`, позначка `chat_message_edited`). Успішна відповідь клієнтом не читається ⚠️, при помилці клієнт підставляє `{status:false}` |
| POST | `/{alias}/sender/conversation/message-delete` | `{id}`; перед викликом діалог підтвердження `chat_delete_message_confirm` |
| POST | `/{alias}/relatives/get-active-children` | `{ids:[logbook_id…]}` → `{active_ids:[…], groups:{"<logbook_id>":"<група>"}}`. Тільки для акаунта-батька (`profile==="relative"`); `active_ids` визначає, на яку дитину авто-перемкнути профіль, `groups` — підпис групи в меню профілю. Помилка ігнорується |
| POST | `/{alias}/activity/events` | `{events:[{section, seconds, continued?}]}` — телеметрія активного часу по розділах UI (нижче) |

> Шлях `/relatives/get-phones-to-auth-by-stud` (без гілки, §3) не змінився — не плутати з новим
> `/{alias}/relatives/get-active-children`.

### Телеметрія `activity/events` ✅
- Розділи (`section`): `main` (також `survey`), `homework` (також `test`), `progress`, `schedule`, `materials`, `review`,
  `awards`, `home_achievements`, `home_achievements_stud`, `shop`, `nutrition`, `clubs`, `payment`, `news`,
  `cyberfit`, `contacts`, `chat`; невідомий перший сегмент URL → `other`; `auth`, `admin`, `small-screen`,
  `email-confirmation` не рахуються.
- Лічильник реагує на `pointerdown/keydown/wheel/scroll/mousemove/touchstart` (тротлінг 1 с); проміжки
  понад 2 хв між подіями не враховуються; сегмент ріжеться кожні 1800 с (`continued:true` для наступних частин).
- Відправка: пачка ≤100 подій, черга ≤500, скидання кожні 5 хв, при приховуванні вкладки та `pagehide`
  (`fetch` з `keepalive`). Заголовки: `Authorization`, `X-UserId` (= `id_user_storage`).
  Відповіді 4xx (крім 401) → подію відкидають; 5xx/мережа → повтор; глобальний інтерцептор не показує тост на 500 для цього шляху.
- Не надсилається, якщо в `localStorage` є ключ `logbook_impersonation` (див. нижче).
- Це окремий HTTP-канал; старий `u_tta`/`user.log` на log-сокет (§9, додаток) залишився.

### Вхід «як студент» (impersonation) — зміна фронту
Якщо URL містить `?t=<JWT>`, фронт чистить storage, зберігає токен, ставить
`localStorage.logbook_impersonation = "1"` і прибирає `t` з адреси. Новий ключ localStorage:
`logbook_impersonation`. Адмін-логін при помилці кидає `impersonation_login_incomplete` та відновлює адмін-сесію.

### Чат (REST + UI)
- Ліміти вкладень: до 5 файлів; **200 МБ на файл** (було 50 МБ) і **200 МБ сумарно** за повідомлення
  (нова помилка `chat_max_attachment_total_size_error`); з'явився діалог попереднього перегляду вкладень (зображення/відео/PDF).
- Сокет-події чату не змінились: `identify`, `join_room`, `message_out_send`, `socket.incoming.message`,
  `conversation_messages_counter`, `conversation_updated`.

### Не змінилось
- Усі 74 виклики `getEndpoint(...)`, 23 присвоєння `endpoint=`, набір подій сокетів (108), заголовків `X-*` (5) і ключів localStorage (5 за регуляркою) — ідентичні, окрім переліченого вище.
- Ендпоінт призупинення договору (`/suspend`) лишився; змінився лише UI (нові компоненти `suspension-link`, `suspend-form`).
- Прибрано сторонні скрипти: Google Analytics (`gtag`) та чат-віджет Helpcrunch — на API не впливає.
- Дрібні UI-зміни: нова іконка «немає платежів», нові ключі перекладів (`hasPayments` у таблиці платежів, `parent-option`, перемикання дитини в меню профілю `profile_menu_switch_child`).

### Не перевірялося
Живі відповіді нових ендпоінтів не знімались (потрібен токен, а за умовами аналізу облікові дані не використовувались).
Форми відповідей `message-edit/delete` та `activity/events` у коді не читаються — у моку це заглушки ⚠️.
