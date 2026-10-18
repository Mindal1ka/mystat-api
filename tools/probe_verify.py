# -*- coding: utf-8 -*-
"""
Жива верифікація MYSTAT API — python-версія (заміна probe_verify.ps1).

Токен береться з token.txt у корені проєкту (або env MYSTAT_TOKEN). У консоль НЕ друкується.
X-L-Session береться ТІЛЬКИ з env MYSTAT_XL_SESSION (у коді його немає; без нього профілі c/f/auto недоступні).

Головна фішка — АВТОПЕРЕБІР профілів заголовків. Факт 2026-08-24: той самий JWT у браузері
дає 200, а «голий» bearer зі скрипта — 401. Отже сервер вимагає щось іще.
Кандидати (за скріном DevTools): X-L-Session, Origin/Referer, браузерний User-Agent.
Скрипт сам знаходить робочий профіль на легкому шляху і ним проганяє всі проби.

Запуск:  python tools\\probe_verify.py [a|b|c|e|f]   (за замовчуванням auto)
Відповіді 200 -> examples/_raw_live/<slug>.json (у .gitignore; перед публікацією анонімізуйте) (+ <slug>.headers.txt поруч)
"""
import base64, json, os, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://mapi.itstep.org/v1/mystat/pl/"
OUTDIR = os.path.join(ROOT, "examples", "_raw_live")  # СИРІ відповіді з персональними даними: у .gitignore, не комітити!
XL_SESSION = os.environ.get("MYSTAT_XL_SESSION", "").strip()  # з DevTools (Request Headers -> X-L-Session); швидко протухає

BROWSER = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8;uk;q=0.7",
    "Origin": "https://mystat.itstep.org",
    "Referer": "https://mystat.itstep.org/",
    "DNT": "1",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Dest": "empty",
}


def load_token():
    p = os.path.join(ROOT, "token.txt")
    raw = open(p, encoding="utf-8-sig").read() if os.path.exists(p) else os.environ.get("MYSTAT_TOKEN", "")
    lines = [re.sub(r"(?i)^\s*bearer\s+", "", l).strip() for l in raw.splitlines()]
    tok = max(lines, key=len) if lines else ""
    if not tok:
        sys.exit("НЕМА ТОКЕНА: ані token.txt, ані $MYSTAT_TOKEN")
    return tok


def jwt_claims(tok):
    try:
        p = tok.split(".")[1]
        p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p))
    except Exception as e:
        return {"_decode_error": str(e)}


def profiles(tok):
    b = {"Authorization": "Bearer " + tok}
    return {
        "a": {**b, "X-Language": "uk"},                                        # як старий probe_verify.ps1
        "b": dict(b),                                                          # лише bearer
        "c": {**b, "X-Language": "uk", "X-L-Session": XL_SESSION},             # + сесія з DevTools
        "e": {**b, "X-Language": "uk", **BROWSER},                             # + браузерні UA/Origin/Referer
        "f": {**b, "X-Language": "uk", "X-L-Session": XL_SESSION, **BROWSER},  # усе одразу
    }
PROFILE_NAMES = {
    "a": "bearer + X-Language (старий профіль)",
    "b": "лише bearer",
    "c": "bearer + X-Language + X-L-Session",
    "e": "bearer + X-Language + браузерні UA/Origin/Referer",
    "f": "bearer + X-Language + X-L-Session + браузерні",
}


def fetch(url, headers, timeout=20):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception:
        # Текст винятку не повертаємо в тіло: він міг би потрапити у збережені файли
        # (URL/заголовки/токен). Статус -1 = мережева помилка.
        return -1, b"", {}


_JWT_RE = re.compile(rb"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")


def scrub(body):
    """Замінює JWT-подібні рядки у тілі відповіді перед записом на диск."""
    return _JWT_RE.sub(b"<JWT-REDACTED>", body)


# (шлях, slug) — шлях відносно BASE. Контрольні 404-шляхи позначені в slug.
PROBES = [
    ("profile/get-personal-data",                      "profile-personal-data"),
    ("count/homework?page=1",                          "count-homework"),
    ("statistic/attendance?period=month",              "statistic-attendance"),
    ("statistic/marks?period=month",                   "statistic-marks"),
    ("statistic/progress?period=year",                 "statistic-progress"),
    ("statistic/average-by-specs",                     "statistic-average-by-specs"),
    ("progress/activity?new_format=1&per_page=20&page=1", "progress-activity"),
    ("progress/leader-points",                         "leader-points"),
    ("progress/leader-table",                          "leader-table"),
    ("gaming/is-star",                                 "gaming-is-star"),
    ("gaming/achieve-info/1",                          "gaming-achieve-info"),
    ("homework/list?status=3&page=1&limit=10",         "hw-until-exec"),
    ("homework/list?status=1&page=1&limit=10",         "hw-done"),
    ("homework/list?status=2&page=1&limit=10",         "hw-examination"),
    ("homework/list?status=5&page=1&limit=10",         "hw-retake"),
    ("schedule/get-month?type=day&date_filter=2026-08-24", "schedule-day"),
    ("schedule/get-existing-schedule?date_filter=2026-08-01", "schedule-existing"),
    ("missions/get-list",                              "missions"),
    ("missions",                                       "CONTROL404-missions-bare"),
    ("chat/room-list",                                 "chat-rooms"),
    ("sender/conversation",                            "chat-conversations"),
    ("sender/conversation/messages?conversation_id=1", "chat-messages"),
    ("shop/orders",                                    "shop-orders"),
    ("shop/products?page=1&per_page=12",               "shop-products"),
    ("shop/products/get-quantity?product_id=1",        "shop-quantity"),
    ("shop/products/get-others?product_id=1",          "shop-others"),
    ("club/get-clubs",                                 "club-clubs"),
    ("club/get-balance",                               "club-balance"),
    ("club/transactions",                              "club-transactions"),
    ("club/abonements",                                "club-abonements"),
    ("nutrition/get-balance",                          "nutrition-balance"),
    ("nutrition/transactions",                         "nutrition-transactions"),
    ("nutrition/get-order-menu?date=2026-08-01",       "nutrition-order-menu"),
    ("nutrition/menu-for-date?date=2026-08-24",        "nutrition-menu-date"),
    ("students/get-qr-code",                           "nutrition-qr"),
    ("payment",                                        "payment-requisites"),
    ("payment/history",                                "payment-history"),
    ("payment/schedule",                               "payment-schedule"),
    ("payment/get-next-payment",                       "payment-next"),
    ("payment/get-offer-contract",                     "payment-offer"),
    ("contacts",                                       "contacts"),
    ("contacts/get-reference-status",                  "contacts-ref-status"),
    ("signal/problems-list",                           "signal-problems"),
    ("library/list?page=1",                            "library"),
    ("settings/history-specs",                         "history-specs"),
    ("reviews/list?page=1",                            "reviews"),
    ("quiz/opened-interview",                          "quiz-opened"),
    ("awards",                                         "awards"),
    ("custom-awards/relative/balance",                 "custom-awards-balance"),
    ("survey-user-attempts",                           "CONTROL404-survey-attempts-bare"),
]


def main():
    tok = load_token()
    cl = jwt_claims(tok)
    fmt = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if isinstance(t, int) else t
    print("JWT: sub=%s jti=%s alias=%s iat=%s exp=%s" % (
        cl.get("sub"), cl.get("jti"), cl.get("branch_alias"), fmt(cl.get("iat")), fmt(cl.get("exp"))))

    want = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if want in ("auto", "c", "f") and not XL_SESSION:
        sys.exit("НЕМА X-L-SESSION: задайте env MYSTAT_XL_SESSION "
                 "(DevTools -> Request Headers -> X-L-Session) або запустіть профіль a/b/e.")
    profs = profiles(tok)
    test_path = "profile/get-personal-data"

    if want != "auto":
        winner = want
        st, _, _ = fetch(BASE + test_path, profs[winner])
        print("Профіль %s (%s) -> %s на %s" % (winner, PROFILE_NAMES[winner], st, test_path))
        if st != 200:
            sys.exit("Вибраний профіль не дав 200.")
    else:
        winner = None
        print("\n— Автоперебір профілів на %s —" % test_path)
        for key in ("f", "c", "e", "a", "b"):
            st, body, _ = fetch(BASE + test_path, profs[key])
            print("  [%s] %s" % (st, PROFILE_NAMES[key]))
            if st == 200:
                winner = key
                break
            time.sleep(0.3)
        if not winner:
            sys.exit("ЖОДЕН профіль не дав 200. Якщо X-L-Session протух — скинь свіжий "
                     "з DevTools (Request Headers -> X-L-Session), або перевір VPN/IP.")

    print("\nПРОФІЛЬ: %s — %s\n" % (winner, PROFILE_NAMES[winner]))
    os.makedirs(OUTDIR, exist_ok=True)
    ok = n401 = n404 = nother = 0
    lines = []
    for path, slug in PROBES:
        st, body, hdrs = fetch(BASE + path, profs[winner])
        tag = "OK " if st == 200 else str(st)
        if st == 200:
            ok += 1
            with open(os.path.join(OUTDIR, slug + ".json"), "wb") as f:
                f.write(scrub(body))
            interesting = {k: v for k, v in hdrs.items() if k.lower() in
                           ("x-pagination-current-page", "x-pagination-page-count", "x-page",
                            "x-pagination-per-page", "content-type")}  # без x-l-session: це секрет сесії
            with open(os.path.join(OUTDIR, slug + ".headers.txt"), "w", encoding="utf-8") as f:
                f.write("GET " + BASE + path + "\n" + json.dumps(interesting, indent=2, ensure_ascii=False))
        elif st == 401:
            n401 += 1
        elif st == 404:
            n404 += 1
        else:
            nother += 1
        line = "[%s] %s" % (tag, path)
        print(line)
        lines.append(line)
        time.sleep(0.25)

    total = len(PROBES)
    summary = "ПІДСУМОК: %d/%d -> 200 | 401: %d | 404: %d | інше: %d | профіль: %s" % (
        ok, total, n401, n404, nother, winner)
    print("\n" + summary)
    with open(os.path.join(OUTDIR, "_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary + "\n\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
