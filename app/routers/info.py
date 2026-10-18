"""Службові info-ендпоінти (їх немає в справжньому API — це довідка всередині Swagger)."""
from typing import Any

from fastapi import APIRouter, Request

from ..config import VERSION

router = APIRouter(prefix="/v1/info", tags=["Docs & Info"])

SOCKET_EVENTS: dict[str, Any] = {
    "connection_options": {
        "path": "/socket.io",
        "query": {"alias": "<branch_alias>"},
        "auth": {"token": "<access_token>"},
        "extraHeaders": {"ngrok-skip-browser-warning": "69420"},
        "note": "при reconnect query+auth обновляются",
    },
    "notify-socket-logbook.itstep.org": {
        "client_emits": {
            "notification_filter": "{user_id, unread}",
            "notification_next_page": "{user_id, count, unread}",
            "notification_status_all_read": "{user_id}",
            "notification_remove_handler": "{id, user_id}",
            "notification_remove_room_handler": "{id, roomId}",
            "notification_hide_until": "{id, user_id, hide_until(ms)}",
        },
        "server_emits": {
            "socket_notification": "новая нотификация {notifications..., pagination}",
            "socket_notification_counter": "{type:'total_counter', unread:n}",
            "socket_notification_more": "{notifications[], pagination:{total}}",
            "notification_filtered": "{notifications[], pagination}",
            "marked_all_read": "підтвердження прочитання всіх",
            "socket_notification_handler": (
                "{id, handler, data:{…}, hide_until?<ms>} — подія-хендлер "
                "(модальні сценарії), реєстр див. ключ 'handler_notifications'"
            ),
        },
        "handler_notifications": {
            "envelope": "{id, handler, data, hide_until?, isGlobal?, roomId?} — при hide_until > now показ молча пропускается",
            "queue": "очередь с cooldown 800 мс; подряд идущие evaluation_notification батчатся в один диалог",
            "permission_gate": "handlers_<handler> | handlers_* (permissionSome)",
            "handlers": {
                "evaluation_notification": {
                    "data": "{evaluation_lesson_id, teach_name, teach_photo, theme}",
                    "ui": "диалог «Оцените занятие» (очередь rateClassArr)",
                    "submit": "POST /students/evaluate-lesson {mark_lesson, mark_teach, comment, id: data.evaluation_lesson_id}",
                    "skip": "emit notification_hide_until {user_id:<id_user_storage>, id, hide_until: Date.now()+3 600 000} — 1 час",
                },
                "happy_birthday_student_handler": "модалка привітання; закриття → notification_remove_handler {id, user_id}",
                "new_survey": "surveyService.initSurvey(payload)",
                "update_student_photo_handler": "диалог загрузки фото (data); отклонить → notification_hide_until на 24 ч; принять → notification_remove_handler",
                "new_news_handler": "довантажує новину за data.news_id → діалог; закриття → notification_remove_handler",
                "homework_rejected_notification": "ДЗ отправлено на доработку ⚠️ тело data не зафиксировано",
                "payment_required_notification": "требуется оплата ⚠️ тело data не зафиксировано",
                "nutrition_order_notification": "заказ питания ⚠️ тело data не зафиксировано",
            },
        },
    },
    "log-socket-mystat.itstep.org": {
        "client_emits": {
            "user.log": "{user:{accessToken}, u_tta:<время из localStorage 'tta'>, app_id:1, app_version}",
            "<operation log>": "{user:{accessToken}, data:{...}, app_id, app_version}",
        }
    },
    "chat-socket-logbook.itstep.org": {
        "client_emits": {
            "identify": "{profile:'student'|…, userId:<id_user_storage>} → чекаємо on('identified')",
            "join_room": "{rooms:['chat_<branch_id>_<conversation_id>', …, '<branch_id>']}",
            "message_out_send": "{roomId:<conversation_id>, message:{message, attachments[файли], created_at ISO, size_kb,…}}",
        },
        "server_emits": {
            "socket.incoming.message": (
                "{conversation_id, id, type_send, message, status, created_at, "
                "user_id, user_fio, user_photo, attachments[]} — фронт кладе в messages[дата]"
            ),
            "conversation_messages_counter": "оновлення лічильників непрочитаних",
            "conversation_updated": "оновлення статусу бесіди",
            "note": "identify/join_room присутні у поточній збірці (основний бандл, не лінивий чанк чату)",
        },
    },
}


@router.get("/endpoints", summary="[довідка] Усі зареєстровані операції цього сервісу")
async def endpoints(request: Request) -> dict[str, Any]:
    def _node_ops(obj: Any) -> list[dict[str, str]]:
        """Операції одного вузла дерева роутів. У FastAPI ≥0.141
        include_router() кладе в app.routes об'єкти _IncludedRouter,
        чиї APIRoute сховані в original_router.routes (+ контекстний префікс)."""
        out: list[dict[str, str]] = []
        if getattr(obj, "original_router", None) is not None:
            ctx = getattr(obj, "include_context", None)
            add = ctx.get("prefix", "") if isinstance(ctx, dict) else ""
            for sub in getattr(obj.original_router, "routes", []) or []:
                if getattr(sub, "original_router", None) is not None:
                    out.extend(_node_ops(sub))
                    continue
                methods = getattr(sub, "methods", None)
                path = getattr(sub, "path", None)
                if methods and path:
                    p = add + path if add and not path.startswith(add) else path
                    for m in sorted(methods - {"HEAD", "OPTIONS"}):
                        out.append({"method": m.upper(), "path": p})
            return out
        inner = getattr(obj, "routes", None)
        if inner is not None:  # вкладений Router/Mount — шляхи вже повні
            for sub in inner:
                if getattr(sub, "original_router", None) is not None:
                    out.extend(_node_ops(sub))
                    continue
                methods = getattr(sub, "methods", None)
                path = getattr(sub, "path", None)
                if methods and path:
                    for m in sorted(methods - {"HEAD", "OPTIONS"}):
                        out.append({"method": m.upper(), "path": path})
            return out
        methods = getattr(obj, "methods", None)
        path = getattr(obj, "path", None)
        if methods and path:
            for m in sorted(methods - {"HEAD", "OPTIONS"}):
                out.append({"method": m.upper(), "path": path})
        return out

    ops = sorted(
        [op for r in request.app.routes for op in _node_ops(r)],
        key=lambda o: o["path"],
    )
    return {"count": len(ops), "operations": ops}


@router.get("/sockets", summary="[довідка] Події всіх трьох socket.io серверів (§9 MYSTAT_API.md)")
async def sockets() -> dict[str, Any]:
    return SOCKET_EVENTS


@router.get("/legend", summary="[довідка] Легенда позначок і ключові інваріанти API")
async def legend() -> dict[str, Any]:
    return {
        "frontend_version": VERSION,
        "markers": {
            "🟢": "підтверджено живим запитом реального акаунта",
            "✅": "подтверждено кодом бандлов фронтенда",
            "⚠️": "відновлено за непрямими ознаками — уточнити перехопленням трафіку",
            "❌": "справжнє API відповідає 404 — фіча вимкнена у філії",
        },
        "two_ids_warning": {
            "logbook_id": "JWT.sub/JWT.id; balances[].user_id; admin list-students id_stud",
            "id_user_storage": "заголовок X-UserId; user_profiles[*][*].user_id",
        },
        "pagination_styles": {
            "laravel": "pagination[page], pagination[per_page] (+ заголовки X-Pagination-*)",
            "yii": "page, per_page",
            "flask": "limit, offset",
        },
    }
