"""Content versioning service.

Every write path is built around one invariant: **exactly one `is_current=True`
row per article, and `version_number` only ever goes up.** Two things threaten
that invariant and both are handled here rather than left to the caller:

* **Concurrent writers.** Two requests saving the same article at once (a human
  in the editor and a worker doing an AI rewrite) can both read
  `max(version_number) == 4` before either inserts. Without a lock both would
  try to insert version 5, and the unique index on (article_id, version_number)
  would let exactly one through while the other 500s with an IntegrityError the
  caller never expects. `_next_version_number` takes `SELECT ... FOR UPDATE` on
  every existing row of the article before computing the max, which serialises
  the two writers: the second one blocks until the first commits, then computes
  5 for itself, not 6 wrongly guessed on stale state.
* **The current-flag flip.** Demoting the old `is_current` row and inserting the
  new one must happen atomically from the caller's point of view. Both are done
  inside `create_version`, which the caller commits as one transaction — never
  split across two.
"""

import difflib
import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.content import ContentArticle
from app.models import Website
from app.models.versions import CONTENT_CHANGE_TYPES, ContentVersion

logger = logging.getLogger(__name__)

# Hard cap on lines returned by diff_versions. A pasted-in translation or a
# full rewrite can produce tens of thousands of diff lines; the UI cannot
# usefully render that and the response would be multiple MB.
MAX_DIFF_LINES = 2000


def _word_count(text: str) -> int:
    return len(text.split())


def _compute_diff_stats(previous_markdown: str, new_markdown: str) -> dict:
    """Char/word added-removed against the previous snapshot.

    Uses `difflib.SequenceMatcher` opcodes rather than counting `+`/`-` unified
    diff lines: line-based counting overcounts a one-word edit inside a long
    paragraph as "removed the whole line, added the whole line".
    """
    matcher = difflib.SequenceMatcher(a=previous_markdown, b=new_markdown, autojunk=False)
    added_chars = 0
    removed_chars = 0
    added_words = 0
    removed_words = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed_chars += i2 - i1
            removed_words += _word_count(previous_markdown[i1:i2])
        if tag in ("replace", "insert"):
            added_chars += j2 - j1
            added_words += _word_count(new_markdown[j1:j2])
    return {
        "added_chars": added_chars,
        "removed_chars": removed_chars,
        "added_words": added_words,
        "removed_words": removed_words,
    }


async def _resolve_org_id(db: AsyncSession, article: ContentArticle) -> UUID:
    """Look up the owning organization for an article.

    `ContentArticle` has only `website_id` — the org lives one hop away on
    `Website`. Reading `article.website.organization_id` would be a lazy
    relationship load and raises MissingGreenlet under asyncio, so this is an
    explicit select. Worth the extra round trip: `content_versions` denormalises
    `organization_id` precisely so that every later read (list, get, diff) can
    skip this join.
    """
    result = await db.execute(
        select(Website.organization_id).where(Website.id == article.website_id)
    )
    org_id = result.scalar_one_or_none()
    if org_id is None:
        # An article whose website vanished cannot be attributed to a tenant, and
        # a version row with a NULL organization_id would be invisible to every
        # org-scoped read while still occupying the article's number sequence.
        raise NotFoundError("Website", str(article.website_id))
    return org_id


async def _next_version_number(db: AsyncSession, article_id: UUID) -> int:
    """Compute the next version number under a row lock.

    Locks every existing `ContentVersion` row of this article (there are at
    most a few dozen for any real article) so a concurrent caller doing the
    same computation blocks until this transaction commits or rolls back — see
    the module docstring for why an unlocked max() is not safe here.
    """
    result = await db.execute(
        select(ContentVersion.version_number)
        .where(ContentVersion.article_id == article_id)
        .with_for_update()
    )
    numbers = result.scalars().all()
    return (max(numbers) + 1) if numbers else 1


async def _clear_current_flag(db: AsyncSession, article_id: UUID) -> None:
    """Flip any existing is_current=True row of this article to False.

    Runs inside the same lock window as `_next_version_number` (both are called
    from `create_version` under the row lock acquired above), so the flip and
    the new insert are never observed as two separate states by a concurrent
    reader.
    """
    result = await db.execute(
        select(ContentVersion).where(
            ContentVersion.article_id == article_id,
            ContentVersion.is_current.is_(True),
        )
    )
    for row in result.scalars().all():
        row.is_current = False


async def create_version(
    db: AsyncSession,
    article: ContentArticle,
    *,
    change_type: str,
    changed_by: UUID | None = None,
    change_summary: str | None = None,
) -> ContentVersion:
    """Snapshot `article`'s current in-memory state as a new version.

    `article` must already carry the state to be captured — this function does
    not re-read it from the DB, so the caller must snapshot *after* applying
    whatever edit is being recorded (but before or after flush, either works
    since we read attributes off the Python object).
    """
    if change_type not in CONTENT_CHANGE_TYPES:
        raise ValidationError(f"change_type must be one of {sorted(CONTENT_CHANGE_TYPES)}")

    organization_id = await _resolve_org_id(db, article)

    # Lock scope: acquiring the lock first, then reading the previous snapshot
    # for the diff, ensures no other writer's insert can land between our read
    # of "previous" and our insert of "new".
    version_number = await _next_version_number(db, article.id)

    prev_result = await db.execute(
        select(ContentVersion)
        .where(ContentVersion.article_id == article.id, ContentVersion.is_current.is_(True))
    )
    previous = prev_result.scalar_one_or_none()
    previous_markdown = previous.content_markdown if previous else ""

    diff_stats = _compute_diff_stats(previous_markdown, article.content_markdown or "")

    await _clear_current_flag(db, article.id)

    version = ContentVersion(
        organization_id=organization_id,
        website_id=article.website_id,
        article_id=article.id,
        version_number=version_number,
        title=article.title,
        content_markdown=article.content_markdown,
        content_html=article.content_html,
        seo_score=article.seo_score,
        seo_metadata=article.seo_metadata or {},
        change_type=change_type,
        change_summary=change_summary,
        changed_by=changed_by,
        diff_stats=diff_stats,
        is_current=True,
    )
    db.add(version)
    await db.flush()

    logger.info(
        "[versions] article=%s version=%d change_type=%s by=%s",
        article.id, version_number, change_type, changed_by,
    )
    return version


async def list_versions(
    db: AsyncSession,
    article_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ContentVersion]:
    """History for one article, newest first."""
    result = await db.execute(
        select(ContentVersion)
        .where(ContentVersion.article_id == article_id)
        .order_by(ContentVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_version(db: AsyncSession, version_id: UUID, org_id: UUID) -> ContentVersion:
    """Fetch one version, scoped to the caller's organization.

    404 (never 403) on a cross-tenant id — matching `app.core.scoping`'s
    anti-enumeration stance, since versions.py cannot add a helper there.
    """
    result = await db.execute(
        select(ContentVersion).where(
            ContentVersion.id == version_id,
            ContentVersion.organization_id == org_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise NotFoundError("ContentVersion", str(version_id))
    return row


async def _get_version_by_number(
    db: AsyncSession, article_id: UUID, version_number: int
) -> ContentVersion:
    result = await db.execute(
        select(ContentVersion).where(
            ContentVersion.article_id == article_id,
            ContentVersion.version_number == version_number,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise NotFoundError("ContentVersion", f"article={article_id} version={version_number}")
    return row


def _classify_diff_line(raw: str) -> tuple[str, str]:
    """Map one `difflib.unified_diff` line to (kind, display text).

    `unified_diff` prefixes every real content line with a space/+/-, so the
    prefix is stripped before it reaches the UI — otherwise every context line
    would visibly start with a leading space.
    """
    if raw.startswith("+++") or raw.startswith("---"):
        return "header", raw
    if raw.startswith("@@"):
        return "hunk", raw
    if raw.startswith("+"):
        return "added", raw[1:]
    if raw.startswith("-"):
        return "removed", raw[1:]
    if raw.startswith(" "):
        return "context", raw[1:]
    return "context", raw


async def diff_versions(
    db: AsyncSession,
    article_id: UUID,
    from_version_number: int,
    to_version_number: int,
) -> dict:
    """Line-level unified diff of two revisions' `content_markdown`.

    Stdlib `difflib.unified_diff` only, per the constraint against adding a
    dependency. `n=1` (one line of context) keeps the payload small; the UI is
    not a merge tool, it is a "what changed" viewer.
    """
    from_v = await _get_version_by_number(db, article_id, from_version_number)
    to_v = await _get_version_by_number(db, article_id, to_version_number)

    from_lines = from_v.content_markdown.splitlines(keepends=True)
    to_lines = to_v.content_markdown.splitlines(keepends=True)

    raw_diff = list(
        difflib.unified_diff(from_lines, to_lines, lineterm="", n=1)
    )

    truncated = len(raw_diff) > MAX_DIFF_LINES
    if truncated:
        raw_diff = raw_diff[:MAX_DIFF_LINES]

    lines = []
    for raw in raw_diff:
        kind, text = _classify_diff_line(raw)
        lines.append({"kind": kind, "text": text})

    stats = _compute_diff_stats(from_v.content_markdown, to_v.content_markdown)
    identical = from_v.content_markdown == to_v.content_markdown

    return {
        "article_id": article_id,
        "from_version_number": from_version_number,
        "to_version_number": to_version_number,
        "from_created_at": from_v.created_at,
        "to_created_at": to_v.created_at,
        "title_changed": from_v.title != to_v.title,
        "from_title": from_v.title,
        "to_title": to_v.title,
        "from_seo_score": from_v.seo_score,
        "to_seo_score": to_v.seo_score,
        "seo_score_delta": to_v.seo_score - from_v.seo_score,
        "stats": stats,
        "lines": lines,
        "identical": identical,
        "truncated": truncated,
    }


async def rollback_to_version(
    db: AsyncSession,
    article: ContentArticle,
    version_id: UUID,
    *,
    user_id: UUID,
    change_summary: str | None = None,
) -> ContentVersion:
    """Restore an old snapshot onto `article` and append a new version for it.

    Rollback is forward-only by design: it never deletes the versions created
    after the target, and it never reuses or rewinds `version_number`. Two
    reasons. First, the history must stay a true log of everything that
    happened, including mistakes and their correction — deleting the
    "bad" versions would erase the very evidence a reviewer wants to see.
    Second, rewinding the counter would collide with `_next_version_number`'s
    race guard: two writers could then legitimately compute the same "next"
    number for genuinely different content. Restoring old content as a *new*
    latest version sidesteps both problems for free.
    """
    # Resolved through Website rather than read off the article: ContentArticle
    # carries no organization_id, and get_version must be org-scoped or a
    # version id from another tenant would be restorable onto this article.
    organization_id = await _resolve_org_id(db, article)
    target = await get_version(db, version_id, organization_id)
    if target.article_id != article.id:
        # Cross-article version id: same anti-enumeration stance as get_version.
        raise NotFoundError("ContentVersion", str(version_id))

    article.title = target.title
    article.content_markdown = target.content_markdown
    article.content_html = target.content_html
    article.seo_score = target.seo_score
    article.seo_metadata = target.seo_metadata or {}
    await db.flush()

    new_version = await create_version(
        db,
        article,
        change_type="rollback",
        changed_by=user_id,
        # The caller's note wins when given; otherwise record which revision was
        # restored, so a rollback row is never left with an empty explanation.
        change_summary=change_summary or f"بازگردانی به نسخه {target.version_number}",
    )
    logger.info(
        "[versions] article=%s rolled back to version=%d by=%s -> new version=%d",
        article.id, target.version_number, user_id, new_version.version_number,
    )
    return new_version


async def get_version_summary(db: AsyncSession, article_id: UUID) -> dict:
    """Header counters for the history panel: totals, current pointer, contributors."""
    result = await db.execute(
        select(
            func.count().label("total"),
            func.max(ContentVersion.created_at).label("last_changed_at"),
            func.count(func.distinct(ContentVersion.changed_by)).label("contributors"),
        ).where(ContentVersion.article_id == article_id)
    )
    row = result.one()

    current_result = await db.execute(
        select(ContentVersion.version_number).where(
            ContentVersion.article_id == article_id,
            ContentVersion.is_current.is_(True),
        )
    )
    current_number = current_result.scalar_one_or_none()

    return {
        "article_id": article_id,
        "total_versions": row.total or 0,
        "current_version_number": current_number,
        "last_changed_at": row.last_changed_at,
        "contributors": row.contributors or 0,
    }
