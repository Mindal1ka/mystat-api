"""§14 «Тести / прогрес» (лінивий чанк `8lGH9t5Y`, endpoint `/survey`) — MYSTAT_API.md §14.

Опитування/тести, логи проходження, спроби користувача, відповіді на питання,
матеріали за UUID та збереження відповідей елемента прогресу.
Шляхи підтверджені кодом бандлів фронтенду (✅); формати тіл/відповідей відновлено
за непрямими ознаками (⚠️) — уточнювати перехопленням трафіку.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..deps import AuthCtx, auth_ctx
from ..models.common import ApiError
from ..proxy import MODE, forward, handle

router = APIRouter(prefix="/v1/mystat/{branch_alias}", tags=["Surveys & Progress"], dependencies=[Depends(auth_ctx)])


# ── Вхідні моделі ────────────────────────────────────────────────────────────


class SurveyLogIn(BaseModel):
    """Лог проходження опитування. Набір полів ⚠️."""

    model_config = ConfigDict(json_schema_extra={"examples": [{"survey_id": 123, "action": "start"}]}, extra="allow")

    survey_id: int = Field(description="UUID опитування передається рядком у шляху (див. GET /survey/{uuid}/{lang}).")
    action: str = Field(description='Дія: приклади "start" / "finish" / "view" ⚠️.', examples=["start"])


class AttemptsIn(BaseModel):
    """Збереження спроб — body підтверджено бандлами: `{attempts:[…]}` ✅ (формат елемента ⚠️)."""

    attempts: list[dict[str, Any]] = Field(default_factory=list, description="Масив об'єктів спроб.")


class AnswerIn(BaseModel):
    """Відповідь на питання. Формат `answer` залежить від типу питання ⚠️:

    рядок/число (одиночний вибір), масив значень (множинний вибір),
    uuid файлу (завдання з вкладенням — див. POST /files/file-token).
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"answer": ["for"]}, {"answer": "c3f9…uuid файлу"}]},
        extra="allow",
    )

    answer: Any = Field(description="Рядок / число / масив значень / uuid завантаженого файлу ⚠️.")


class RejectIn(BaseModel):
    """Відхилення елемента прогресу — body `{id_spec}` ✅ (тип `id_spec` ⚠️)."""

    model_config = ConfigDict(extra="allow")

    id_spec: Any = Field(description="Специфікація елемента прогресу ⚠️ (імовірно subject/спец-об'єкт групи).")


# ── Ендпоінти ─────────────────────────────────────────────────────────────────


@router.get("/survey/{survey_uuid}/{lang}", summary="Опитування/тест за UUID та мовою")
async def get_survey(
    request: Request,
    branch_alias: str,
    survey_uuid: str,
    lang: str,
    ctx: AuthCtx = Depends(auth_ctx),
) -> Any:
    """**GET /v1/mystat/{alias}/survey/{survey_uuid}/{lang}** ✅

    Виклик фронту: `survey.get(t.model.survey_uuid, t.model.survey_lang)` — параметри
    це **UUID опитування та МОВА**. У відповіді фронт
    шукає `binds[]` → елемент зі збігом `survey_lang` → `survey_binds[]`
    (`launch_uuid`, `date_time_to`, …) — так знаходиться активний launch опитування.
    Самі питання UI бере з `quiz_data[]`: `{question:{id,image_url},
    answers_list:[{id,answer_text}]}`; повний enum типів питань:
    `1`=oneRightAnswer, `2`=allCorrectOrNone,
    `3`=multipleAnswers, `4`=ownAnswer, `5`=oneOrOwnAnswer.
    """
    return await handle(
        request,
        sample={
            "survey_uuid": survey_uuid,
            "quiz_data": [
                {
                    "question": {"id": 101, "image_url": None},
                    "answers_list": [
                        {"id": 1, "answer_text": "for"},
                        {"id": 2, "answer_text": "while"},
                        {"id": 3, "answer_text": "loop"},
                    ],
                }
            ],
            "binds": [
                {
                    "survey_lang": lang,
                    "survey_binds": [
                        {"launch_uuid": "0c9f11aa-demo-4a5b-8c2d-launch01", "date_time_to": "2026-09-01 23:59:00"}
                    ],
                }
            ],
        },
    )


@router.post("/survey-logs", summary="Записати подію проходження опитування")
async def create_survey_log(body: SurveyLogIn, request: Request, branch_alias: str) -> Any:
    """**POST /v1/mystat/{alias}/survey-logs** ✅⚠️

    Лог проходження: фронту важливо фіксувати старт/фініш тесту.
    Body ⚠️: `{survey_id, action, …}` — можливі дод. поля (extra="allow").
    """
    return await handle(request, sample={"status": "ok", "log_id": 987_654})


@router.get(
    "/survey-user-attempts/{attempt_id:int}",
    summary="Спроби опитування за ID (id ОБОВ'ЯЗКОВИЙ у шляху ✅)",
)
async def list_attempts(request: Request, branch_alias: str, attempt_id: int, ctx: AuthCtx = Depends(auth_ctx)) -> Any:
    """**GET /v1/mystat/{alias}/survey-user-attempts/{id}** ✅

    Фронт: `userAttempts.get: t => GET /survey-user-attempts/${t}` —
    **`{id}` обов'язковий у шляху**. Голий шлях без id → 404 ЩЕ ДО
    авторизації (маршруту не існує), на відміну від 401 на наявних шляхах.

    Формат елемента ⚠️: `{id, survey_id, user_id, status, score, started_at, finished_at}`.
    """
    uid = ctx.logbook_id
    return await handle(
        request,
        sample={
            "id": attempt_id,
            "survey_id": 123,
            "user_id": uid,
            "status": "finished",
            "score": 8,
            "started_at": "2026-08-20 10:12:00",
            "finished_at": "2026-08-20 10:39:41",
        },
    )


@router.post(
    "/survey-user-attempts/{attempt_id:int}",
    summary="Зберегти спроби до опитування {id} (body {attempts:[…]}) ✅",
)
async def save_attempts(body: AttemptsIn, request: Request, branch_alias: str, attempt_id: int) -> Any:
    """**POST /v1/mystat/{alias}/survey-user-attempts/{id}** ✅

    Бандл: `save: (t,i) => POST /survey-user-attempts/${i}` body `{attempts:t}` —
    id опитування/прогресу в ШЛЯХУ, масив спроб у тілі.
    """
    return await handle(request, sample={"status": "ok", "created": len(body.attempts)})


@router.delete("/survey-user-attempts/{attempt_id:int}", summary="Видалити спробу за ID")
async def delete_attempt(request: Request, branch_alias: str, attempt_id: int) -> Any:
    """**DELETE /v1/mystat/{alias}/survey-user-attempts/{attempt_id}** ✅⚠️

    Видалення спроби (напр., скидання чернетки тесту). Реальний шлях:
    `https://mystat.itstep.org/v1/mystat/{alias}/survey-user-attempts/55101`.
    """
    if MODE == "proxy":
        return await forward(request)
    return {"status": "deleted", "id": attempt_id}


# ── Відповіді на питання (три окремі шляхи під кожен тип) ─────────────────────


async def _post_answer(question_id: int, body: AnswerIn, request: Request, branch_alias: str) -> Any:
    """Загальна реалізація для трьох варіантів `/answers/{type}/{question_id}`."""
    kind = request.url.path.rsplit("/", 2)[-2]  # quiz | exercise | multi
    return await handle(
        request,
        sample={"question_id": question_id, "kind": kind, "answer": body.answer, "correct": True, "points": 1},
    )


@router.post("/answers/quiz/{question_id}", summary="Відповідь на питання типу quiz")
async def answer_quiz(request: Request, branch_alias: str, question_id: int, body: AnswerIn) -> Any:
    """**POST /v1/mystat/{alias}/answers/quiz/{question_id}** ✅⚠️

    Відповідь на питання квіза. `answer` — рядок/число (одиночний вибір) або масив
    (множинний вибір) ⚠️; uuid файлу — для питань із вкладенням.
    """
    return await _post_answer(question_id, body, request, branch_alias)


@router.post("/answers/exercise/{question_id}", summary="Відповідь на питання типу exercise")
async def answer_exercise(request: Request, branch_alias: str, question_id: int, body: AnswerIn) -> Any:
    """**POST /v1/mystat/{alias}/answers/exercise/{question_id}** ✅⚠️

    Відповідь на вправу: як правило текстова відповідь та/або uuid файлу розв'язку ⚠️.
    """
    return await _post_answer(question_id, body, request, branch_alias)


@router.post("/answers/multi/{question_id}", summary="Відповідь на питання типу multi")
async def answer_multi(request: Request, branch_alias: str, question_id: int, body: AnswerIn) -> Any:
    """**POST /v1/mystat/{alias}/answers/multi/{question_id}** ✅⚠️

    Відповідь на питання з кількома варіантами: `answer` зазвичай масив id/значень ⚠️.
    """
    return await _post_answer(question_id, body, request, branch_alias)


# ── Інтерв'ю-квізи (/quiz/*, окремий сервіс з endpoint `/`) ────────────────


class QuizRunIn(BaseModel):
    """Старт квіза — бандл: `runQuiz(t)` → `POST /quiz/run/${t}` body `{id:t}`."""

    id: int = Field(description="ID квіза (дублює шлях).")


class QuizDelayIn(BaseModel):
    """Відкласти інтерв'ю — бандл: `delayInterview(t)` → body `{id:t}`."""

    id: int = Field(description="ID інтерв'ю/запуску для відкладення.")


class QuizFinishData(BaseModel):
    """`data` усередині тіла finish — за кодом фронту."""

    model_config = ConfigDict(extra="allow")

    id: int = Field(description="ID квіза.")
    answers: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "{<question_id>: [answer_id,…]} — чекбокси дають масив id; "
            "для типів ownAnswer(4)/oneOrOwnAnswer(5) можливий текст."
        ),
    )


class QuizFinishIn(BaseModel):
    """Тіло `POST /quiz/finish/{id}` — фронт шле весь `t`: `finishQuiz(t.data.id, t)`."""

    data: QuizFinishData


@router.get("/quiz/opened-interview", summary="Відкритий запуск інтерв'ю (?params)")
async def quiz_opened_interview(request: Request, branch_alias: str) -> Any:
    """**GET /v1/mystat/{alias}/quiz/opened-interview** ✅⚠️

    Фронт: `getOpenedInterview(t)` → GET c query `Qn(t)`
    (склад параметрів ⚠️). Відповідь — відкритий запуск інтерв'ю або порожньо ⚠️.
    """
    return await handle(
        request,
        sample={"id": 55_101, "launch_uuid": "0c9f11aa-demo-4a5b-8c2d-launch01", "status": "opened"},
    )


@router.get("/quiz/get-time-between-retries", summary="Період між спробами (за параметрами)")
async def quiz_retry_period(request: Request, branch_alias: str) -> Any:
    """**GET /v1/mystat/{alias}/quiz/get-time-between-retries** ✅⚠️

    Бандл: `getPeriodInterview(t)` → GET c query `Qn(t)` (параметри ⚠️).
    Форма відповіді ⚠️ — імовірно число секунд/хвилин між спробами.
    """
    return await handle(request, sample=86_400)


@router.get("/quiz/get-time-between-retries/{quiz_id:int}", summary="Пауза між спробами конкретного квіза")
async def quiz_retry_for(request: Request, branch_alias: str, quiz_id: int) -> Any:
    """**GET /v1/mystat/{alias}/quiz/get-time-between-retries/{id}** ✅⚠️

    Бандл: `getTimeBetweenRetries(t)` → GET `/quiz/get-time-between-retries/${t}`.
    Форма відповіді ⚠️ — імовірно число (секунди до наступної спроби).
    """
    return await handle(request, sample=3_600)


@router.get("/quiz/{quiz_id:int}", summary="Картка квіза за ID")
async def get_quiz(request: Request, branch_alias: str, quiz_id: int) -> Any:
    """**GET /v1/mystat/{alias}/quiz/{id}** ✅⚠️

    Бандл: `getQuizInfo(t)` → GET `/quiz/${t}`. Формат відповіді ⚠️ — очікується
    об'єкт квіза; питання UI рендерить як `question{id,image_url}` +
    `answers_list[{id,answer_text}]` (та сама форма, що `quiz_data` у survey).
    """
    return await handle(
        request,
        sample={
            "id": quiz_id,
            "title": "Опитування після інтерв'ю",
            "questions": [
                {
                    "question": {"id": 101, "image_url": None},
                    "answers_list": [
                        {"id": 1, "answer_text": "for"},
                        {"id": 2, "answer_text": "while"},
                    ],
                }
            ],
        },
    )


@router.post("/quiz/run/{quiz_id:int}", summary="Стартувати спробу квіза")
async def run_quiz(request: Request, branch_alias: str, quiz_id: int, body: QuizRunIn) -> Any:
    """**POST /v1/mystat/{alias}/quiz/run/{id}** ✅⚠️

    Бандл: `runQuiz(parseInt(params.id))`, body `{id:t}`; при помилці фронт
    показує тост за `error.code` і йде на /materials.

    Коди помилок родини (enum фронту): `7001`
    two_quizzes_at_the_same_time_error · `7002` closed_quiz_error · `7003`
    group_closed_quiz_error · `7004` too_frequent_attempts_error · `7005`
    attempts_are_exhausted_error · `7006` question_not_found_error · `7007`
    quiz_not_found_error · `7008` interview_passed · `7009`
    two_interviews_at_the_same_time_error · `7010` interview_closed_error ·
    `7011` can_not_retake_quiz_lack_of_funds · `7012` interview_inner_exception ·
    `7013` interview_inner_exception_log. Форма успіху ⚠️ — розпочата спроба.
    """
    return await handle(
        request,
        sample={"attempt_id": 777_001, "quiz_id": quiz_id, "status": "started"},
    )


@router.post("/quiz/delay-interview", summary="Відкласти інтерв'ю (body {id})")
async def delay_interview(request: Request, branch_alias: str, body: QuizDelayIn) -> Any:
    """**POST /v1/mystat/{alias}/quiz/delay-interview** ✅

    Бандл: `delayInterview(t)` → body `{id:t}` — «продовжити пізніше».
    """
    return await handle(request, sample={"status": "delayed", "id": body.id})


@router.post("/quiz/finish/{quiz_id:int}", summary="Завершити квіз (body {data:{id,answers}})")
async def finish_quiz(request: Request, branch_alias: str, quiz_id: int, body: QuizFinishIn) -> Any:
    """**POST /v1/mystat/{alias}/quiz/finish/{id}** ✅⚠️

    Тіло за кодом фронту: `finishQuiz(t.data.id, t)` — шлється весь `t`,
    тобто `{data:{id, answers:{<qid>:[answer_id,…]}}}`. Відповідь потрапляє у фронтовий
    `testFinished={finished:true, data:<відповідь>}` — форма результату ⚠️.
    """
    return await handle(
        request,
        sample={"result": "passed", "score": 8, "max_score": 10, "correct": 8, "total": 10},
    )


@router.get("/materials/uuid/{uuid}/{sub}", summary="Матеріал за UUID (+підсторінка/вкладення)")
async def material_by_uuid(request: Request, branch_alias: str, uuid: str, sub: str) -> Any:
    """**GET /v1/mystat/{alias}/materials/uuid/{uuid}/{sub}** ✅⚠️

    Матеріал за UUID (сестринський шлях до `/materials/id/{id}` з розділу Homework).

    - **sub** — підсторінка/вкладення: наприклад `view` (картка) або ім'я файлу;
    - реальний URL: `https://mystat.itstep.org/v1/mystat/{alias}/materials/uuid/c3f9…/view`.
    Структура відповіді ⚠️.
    """
    return await handle(
        request,
        sample={
            "id": 90_210,
            "uuid": uuid,
            "sub": sub,
            "title": "Лекція 05 — Цикли.pdf",
            "type": "file",
            "mime": "application/pdf",
            "size": 1_048_576,
            "url": f"https://mystat.itstep.org/uploads/materials/{uuid}/{sub}",
        },
    )


@router.post(
    "/progress-item-answers/quizzes/{item_id}",
    summary="Зберегти відповіді квіза елемента прогресу (?expand=answers)",
    responses={401: {"model": ApiError}},
)
async def save_progress_quiz(
    request: Request,
    branch_alias: str,
    item_id: int,
    body: AnswerIn,
    expand: Optional[str] = Query("answers", description="Підвантажувані зв'язки; бандли викликають з expand=answers."),
) -> Any:
    """**POST /v1/mystat/{alias}/progress-item-answers/quizzes/{item_id}?expand=answers** ✅⚠️

    Збереження відповідей на питання квіза всередині елемента прогресу.
    Фронт викликає саме з query `expand=answers` — у відповіді очікуються розгорнуті
    відповіді (структура ⚠️).
    """
    return await handle(request, sample={"id": item_id, "expand": expand, "answers": [body.answer], "status": "saved"})


@router.post(
    "/progress-item-answers/exercises/{item_id}",
    summary="Зберегти відповідь вправи елемента прогресу (?expand=multiProgressItem)",
    responses={401: {"model": ApiError}},
)
async def save_progress_exercise(
    request: Request,
    branch_alias: str,
    item_id: int,
    body: AnswerIn,
    expand: Optional[str] = Query(
        "multiProgressItem", description="Підвантажувані зв'язки; бандли викликають з expand=multiProgressItem."
    ),
) -> Any:
    """**POST /v1/mystat/{alias}/progress-item-answers/exercises/{item_id}?expand=multiProgressItem** ✅⚠️

    Збереження відповіді вправи елемента прогресу. Фронт викликає з query
    `expand=multiProgressItem` — у відповіді очікується сам multiProgressItem ⚠️.
    """
    return await handle(
        request,
        sample={
            "id": item_id,
            "expand": expand,
            "multiProgressItem": {"id": item_id, "answer": body.answer, "status": "pending_review"},
        },
    )


@router.put("/progress-items/reject/{item_id}", summary="Відхилити елемент прогресу (body {id_spec}) ✅")
async def reject_progress_item(request: Request, branch_alias: str, item_id: int, body: RejectIn) -> Any:
    """**PUT /v1/mystat/{alias}/progress-items/reject/{item_id}** ✅⚠️

    Відхилити елемент прогресу (наприклад, відмовитися від дод. завдання).
    Тіло підтверджено бандлами: `{id_spec}`; тип значення `id_spec` ⚠️
    (імовірно, специфікація предмета/елемента з group-specs).
    """
    if MODE == "proxy":
        return await forward(request)
    return {"status": "rejected", "id": item_id, "id_spec": body.id_spec}


@router.get(
    "/progress-items/get-entity-task-progress-item",
    summary="ProgressItem за матеріалом (?entity_name=material&task_type=multi)",
    responses={401: {"model": ApiError}},
)
async def get_entity_task_progress_item(
    request: Request,
    branch_alias: str,
    entity_id: int = Query(description="ID матеріалу (material.id)."),
    task_id: int = Query(description="ID multi-завдання."),
    entity_name: str = Query("material", description="У бандлі завжди `material`."),
    task_type: str = Query("multi", description="У бандлі завжди `multi`."),
    expand: Optional[str] = Query("multiProgressItems", description="Бандл шле expand=multiProgressItems."),
) -> Any:
    """**GET /v1/mystat/{alias}/progress-items/get-entity-task-progress-item** ✅⚠️

    Бандл (`8lGH9t5Y`): `getEntityProgressItem(entity_id, task_id)` → query
    `entity_name=material&entity_id=…&task_type=multi&task_id=…&expand=multiProgressItems`.
    Відповідь — об'єкт ProgressItem (структура ⚠️).
    """
    return await handle(
        request,
        sample={
            "id": 77_001,
            "entity_name": entity_name,
            "entity_id": entity_id,
            "task_type": task_type,
            "task_id": task_id,
            "status": "in_progress",
        },
    )


@router.get(
    "/progress-items/{item_id:int}",
    summary="Елемент прогресу за ID (?expand=CSV зв'язків)",
    responses={401: {"model": ApiError}},
)
async def get_progress_item(
    request: Request,
    branch_alias: str,
    item_id: int,
    expand: Optional[str] = Query(
        None,
        description=(
            "Повний список із бандлу: student,file,comment,answer.file,answer.task_file,"
            "answer.points.file,answer.question,answer.questions.task.quiz,"
            "answer.questions.answers.task,answer.questions.points,answer.questions.file,"
            "answer.questions.task_file"
        ),
    ),
) -> Any:
    """**GET /v1/mystat/{alias}/progress-items/{id}?expand=…** ✅⚠️

    Розгорнутий елемент прогресу. Expand-список підтверджено бандлом (12 зв'язків,
    включно з вкладеними answer.questions.*). Структура відповіді ⚠️.
    """
    return await handle(request, sample={"id": item_id, "status": "submitted", "expand": expand})
