from datetime import date
from uuid import UUID
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.models import Keyword, KeywordRanking, Website


async def create_keyword(
    db: AsyncSession,
    website_id: UUID,
    keyword: str,
    search_volume: int | None = None,
    difficulty: int | None = None,
    target_page_url: str | None = None,
    intent: str = "informational",
    tags: list[str] = None,
) -> Keyword:
    # Check if keyword already exists for this website
    stmt = select(Keyword).where(
        Keyword.website_id == website_id,
        Keyword.keyword == keyword,
    )
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise ConflictError(f"کلمه کلیدی «{keyword}» قبلاً برای این وب‌سایت ثبت شده است.")

    kw = Keyword(
        website_id=website_id,
        keyword=keyword,
        search_volume=search_volume or 1000,
        difficulty=difficulty or 35,
        target_page_url=target_page_url,
        intent=intent,
        tags=tags or [],
        last_position=None,
        best_position=None,
    )
    db.add(kw)
    await db.flush()
    return kw


async def list_website_keywords(db: AsyncSession, website_id: UUID) -> list[Keyword]:
    stmt = (
        select(Keyword)
        .where(Keyword.website_id == website_id)
        .order_by(Keyword.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_keyword(db: AsyncSession, keyword_id: UUID) -> None:
    stmt = select(Keyword).where(Keyword.id == keyword_id)
    result = await db.execute(stmt)
    kw = result.scalar_one_or_none()
    if not kw:
        raise NotFoundError("Keyword", str(keyword_id))
    await db.delete(kw)
    await db.flush()


async def get_keyword_rankings(db: AsyncSession, keyword_id: UUID) -> list[KeywordRanking]:
    stmt = (
        select(KeywordRanking)
        .where(KeywordRanking.keyword_id == keyword_id)
        .order_by(KeywordRanking.check_date.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def add_keyword_ranking(
    db: AsyncSession,
    keyword_id: UUID,
    position: float,
    url_found: str | None = None,
    check_date: date | None = None,
) -> KeywordRanking:
    c_date = check_date or date.today()

    stmt = select(Keyword).where(Keyword.id == keyword_id)
    res = await db.execute(stmt)
    kw = res.scalar_one_or_none()
    if not kw:
        raise NotFoundError("Keyword", str(keyword_id))

    ranking = KeywordRanking(
        keyword_id=keyword_id,
        position=position,
        url_found=url_found,
        check_date=c_date,
    )
    db.add(ranking)

    # Update keyword last/best position
    kw.last_position = position
    if kw.best_position is None or position < kw.best_position:
        kw.best_position = position

    await db.flush()
    return ranking
