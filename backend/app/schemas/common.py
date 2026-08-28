from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 25


class PaginatedMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedResponse(BaseModel):
    data: list
    meta: PaginatedMeta


class ErrorResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    errors: list[dict] | None = None


class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IDTimestamp(OrmBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
