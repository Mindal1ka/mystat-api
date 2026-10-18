"""Спільні моделі помилок/пагінації (формат справжнього API)."""
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, RootModel

T = TypeVar("T")


class ApiErrorItem(BaseModel):
    """Елемент масиву помилок MyStat: [{"field": ..., "message": ...}]."""

    field: str = Field(
        description="Поле форми або 'summary' для загальної помилки.",
        examples=["login", "password", "summary"],
    )
    message: str = Field(description="Людськочитабельне повідомлення.", examples=["Невірний логін або пароль"])


class ApiError(RootModel[list[ApiErrorItem]]):
    """Помилки приходять МАСИВОМ об'єктів {field,message} — так їх показує toast у фронті."""

    model_config = ConfigDict(json_schema_extra={"examples": [[{"field": "password", "message": "Мінімум 6 символів"}]]})


class PaginationMeta(BaseModel):
    """Laravel-пагінація лінивих розділів; номери сторінок — в заголовках відповіді
    X-Pagination-Current-Page / X-Pagination-Page-count."""

    model_config = ConfigDict(populate_by_name=True)

    current_page: int = Field(default=1, validation_alias="current_page")
    last_page: int = Field(default=1, validation_alias="last_page")
    per_page: int = Field(default=15)
    total: int = Field(default=0)
