"""Кастомізація сторінки документації: темна тема Swagger UI (за замовчуванням) та UX-покращення.

FastAPI віддає стандартний білий Swagger UI; тут ми перехоплюємо /docs і інжектимо
свій CSS + параметри SwaggerUIBundle (фільтр-пошук, monokai-підсвітка, persist Authorization)."""
from typing import Any

from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse

# Параметри SwaggerUIBundle (мержаться з дефолтами FastAPI)
SWAGGER_UI_PARAMETERS: dict[str, Any] = {
    "persistAuthorization": True,       # токен Authorize переживає F5
    "displayRequestDuration": True,     # час виконання запиту в відповіді
    "filter": True,                     # рядок пошуку по ендпоінтах зверху
    "docExpansion": "none",             # групи згорнуті — не стіна тексту
    "syntaxHighlight": {"theme": "monokai"},
}

_CSS = """
:root { color-scheme: dark; }
html, body { background:#141417 !important; }
.swagger-ui { color:#d7dae0; }
.swagger-ui *::-webkit-scrollbar { width:10px; height:10px; }
.swagger-ui *::-webkit-scrollbar-thumb { background:#33333c; border-radius:8px; }
.swagger-ui *::-webkit-scrollbar-track { background:transparent; }

/* ── контейнер схем (рядок Authorize зверху) ─────────────────────────────── */
.swagger-ui .scheme-container {
    background:#1c1c21 !important; box-shadow:0 2px 10px rgba(0,0,0,.45) !important;
    border-bottom:1px solid #2b2b33;
}
.swagger-ui .scheme-container .schemes > label { color:#9aa0aa; }
.swagger-ui .scheme-container .schemes select {
    background:#232329 !important; color:#e6e9ef !important; border-color:#3a3a44 !important;
}

/* ── шапка опису ─────────────────────────────────────────────────────────── */
.swagger-ui .info .title {
    color:transparent !important;
    background:linear-gradient(92deg,#7dd3fc,#6ee7b7);
    -webkit-background-clip:text; background-clip:text;
}
.swagger-ui .info hgroup.main a { color:#7dd3fc; }
.swagger-ui .info p, .swagger-ui .info li, .swagger-ui .info .markdown p,
.swagger-ui .info .markdown li, .swagger-ui .info td, .swagger-ui .info th { color:#c3c8d1; }
.swagger-ui .info .base-url { color:#8b93a1 !important; }
.swagger-ui .info table tr { background:transparent; }
.swagger-ui .info table td, .swagger-ui .info table th { border-color:#2e2e36; }
.swagger-ui .info .main .link span { display:inline-block; margin-left:8px; }

/* ── теги-групи ──────────────────────────────────────────────────────────── */
.swagger-ui .opblock-tag {
    color:#eceef2 !important; border-bottom:1px solid #33333c !important;
    padding:10px 4px; letter-spacing:.02em;
}
.swagger-ui .opblock-tag:hover { background:#1e1e24; }
.swagger-ui .opblock-tag small { color:#8b93a1 !important; }
.swagger-ui .opblock-tag svg { fill:#8b93a1; }

/* ── картки операцій ─────────────────────────────────────────────────────── */
.swagger-ui .opblock {
    border-radius:10px !important; box-shadow:0 1px 5px rgba(0,0,0,.35) !important;
}
.swagger-ui .opblock .opblock-summary { border-radius:8px; }
.swagger-ui .opblock .opblock-summary-method {
    text-shadow:none !important; font-weight:700; border-radius:6px; min-width:64px;
}
.swagger-ui .opblock .opblock-summary-path,
.swagger-ui .opblock .opblock-summary-path__deprecated { color:#e6e9ef !important; font-size:14px; }
.swagger-ui .opblock .opblock-summary-description { color:#98a0ad !important; }
.swagger-ui .opblock.is-open .opblock-summary { border-bottom:1px solid #2c2c34; }
.swagger-ui .opblock .opblock-body { color:#c3c8d1; }

.swagger-ui .opblock-get    { background:rgba(97,175,255,.08) !important;  border-color:rgba(97,175,255,.5) !important; }
.swagger-ui .opblock-get .opblock-summary-method    { background:#2f6db8; }
.swagger-ui .opblock-post   { background:rgba(73,204,144,.08) !important;  border-color:rgba(73,204,144,.45) !important; }
.swagger-ui .opblock-post .opblock-summary-method   { background:#2f9c6e; }
.swagger-ui .opblock-put    { background:rgba(252,161,48,.08) !important;  border-color:rgba(252,161,48,.45) !important; }
.swagger-ui .opblock-put .opblock-summary-method    { background:#bd7b28; }
.swagger-ui .opblock-delete { background:rgba(249,62,62,.08) !important;   border-color:rgba(249,62,62,.45) !important; }
.swagger-ui .opblock-delete .opblock-summary-method { background:#b23434; }
.swagger-ui .opblock-head .opblock-summary-method   { background:#7b3fb8; }
.swagger-ui .opblock-patch .opblock-summary-method  { background:#3ba58b; }
.swagger-ui .opblock-options .opblock-summary-method{ background:#5a6474; }

/* ── таблиці параметрів ──────────────────────────────────────────────────── */
.swagger-ui table.parameters thead tr th,
.swagger-ui table.parameters thead tr td { color:#aab1bd; border-bottom:1px solid #33333c; }
.swagger-ui table.parameters tbody tr td { border-bottom:1px solid #26262d; }
.swagger-ui table.parameters .parameter__name { color:#dfe3ea; }
.swagger-ui table.parameters .parameter__name.required::after { color:#e05f65; }
.swagger-ui table.parameters .parameter__type { color:#8fd4c1; }
.swagger-ui .parameter__in, .swagger-ui .parameter__extension { color:#8b93a1; }
.swagger-ui .table-container { background:transparent; }

/* ── кнопки / execute ────────────────────────────────────────────────────── */
.swagger-ui .btn {
    background:#26262d !important; border:1px solid #3a3a44 !important;
    color:#d7dae0 !important; box-shadow:none !important; border-radius:6px;
}
.swagger-ui .btn:hover { background:#30303a !important; }
.swagger-ui .btn.cancel { color:#e07a7a !important; }
.swagger-ui .btn.execute { background:#2f6db8 !important; border-color:#2f6db8 !important; color:#fff !important; }
.swagger-ui .btn.authorize, .swagger-ui .auth-wrapper .authorize.btn {
    background:rgba(73,204,144,.14) !important; border-color:#49cc90 !important; color:#6ee7b7 !important;
}
.swagger-ui .btn.authorize svg { fill:#6ee7b7; }

/* ── поля вводу ──────────────────────────────────────────────────────────── */
.swagger-ui input[type=text], .swagger-ui input[type=password], .swagger-ui input[type=search],
.swagger-ui input[type=email], .swagger-ui input[type=file], .swagger-ui textarea,
.swagger-ui select {
    background:#131318 !important; color:#e6e9ef !important;
    border:1px solid #3a3a44 !important; border-radius:6px;
}
.swagger-ui input:focus, .swagger-ui textarea:focus, .swagger-ui select:focus { outline:1px solid #4f83ff; }
.swagger-ui ::placeholder { color:#6b7280; opacity:1; }
.swagger-ui .filter-container .operation-filter-input { border-radius:999px; padding:8px 16px; }

/* ── відповіді, curl, моделі ─────────────────────────────────────────────── */
.swagger-ui .responses-inner h4, .swagger-ui .responses-inner h5 { color:#d7dae0; }
.swagger-ui .response-col_status { color:#d7dae0; }
.swagger-ui .response-col_status .response-undocumented,
.swagger-ui .response-col_description .response-undocumented { color:#6f7680; }
.swagger-ui .response-col_description .markdown p, .swagger-ui .response-col_description div { color:#c3c8d1; }
.swagger-ui .model-box { background:#191920 !important; border:1px solid #2c2c34; border-radius:8px; }
.swagger-ui .model-title { color:#d7dae0; }
.swagger-ui .model .property, .swagger-ui .model .property.primitive { color:#c3c8d1; }
.swagger-ui section.models { border:1px solid #2c2c34 !important; border-radius:8px; background:#18181d; }
.swagger-ui section.models h4 { color:#eceef2; border-bottom:1px solid #2c2c34; }
.swagger-ui section.models h5 { color:#c3c8d1; border-bottom:1px solid #26262d; }
.swagger-ui .model-toggle::after { background:#9aa0aa; }
.swagger-ui pre:not(.hljs) { background:#121216; color:#cdd6f4; border-radius:8px; }

/* ── вкладки / діалоги ───────────────────────────────────────────────────── */
.swagger-ui .tab li, .swagger-ui .tabs__item { color:#9aa0aa; }
.swagger-ui .tab li.button.is-active, .swagger-ui .tabs__item.active { color:#7dd3fc; }
.swagger-ui .dialog-ux .backdrop-ux { background:rgba(0,0,0,.65); }
.swagger-ui .dialog-ux .modal-ux { background:#1c1c21 !important; border:1px solid #33333c; color:#d7dae0; }
.swagger-ui .dialog-ux .modal-ux-header h3 { color:#eceef2; }
.swagger-ui .dialog-ux .modal-ux-content p { color:#c3c8d1; }
.swagger-ui .auth-container { border-bottom:1px solid #2c2c34; }
.swagger-ui .auth-container .errors { background:#2a1d1d; color:#e07a7a; border-radius:6px; }
.swagger-ui .loading-container .loading::before { border-color:#33333c; }
.swagger-ui .loading-container .loading::after { border-color:#7dd3fc transparent transparent; }

/* ── бейдж унизу праворуч ────────────────────────────────────────────────── */
.mystat-footer {
    position:fixed; bottom:10px; right:14px; z-index:9999; pointer-events:none;
    font:11px/1.5 Consolas,'Cascadia Mono',monospace; color:#8b93a1;
    background:rgba(20,20,23,.88); border:1px solid #2c2c34; border-radius:999px; padding:4px 12px;
}
.mystat-footer b { color:#6ee7b7; }
"""

_FOOTER_HTML = (
    '<div class="mystat-footer">⚡ MyStat API · реверс mystat.itstep.org · '
    "<b>MYSTAT_API.md</b></div>"
)


def _inject(html_response: HTMLResponse) -> HTMLResponse:
    """Вшити <style> і бейдж у готовий HTML від FastAPI."""
    style = f"<style>{_CSS}</style>".encode()
    body = html_response.body
    body = body.replace(b"</head>", style + b"</head>", 1)
    body = body.replace(b"</body>", _FOOTER_HTML.encode() + b"</body>", 1)
    return HTMLResponse(content=body, status_code=html_response.status_code)


def swagger_ui(
    *, openapi_url: str, title: str, oauth2_redirect_url: str | None = None
) -> HTMLResponse:
    """Темна сторінка /docs з розширеними параметрами."""
    resp = get_swagger_ui_html(
        openapi_url=openapi_url,
        title=title,
        oauth2_redirect_url=oauth2_redirect_url,
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
    )
    return _inject(resp)


def redoc_ui(*, openapi_url: str, title: str) -> HTMLResponse:
    """ReDoc як є (у нього власна темізація через тему специфікації)."""
    return get_redoc_html(openapi_url=openapi_url, title=title)
