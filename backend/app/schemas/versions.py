"""Schemas for content versioning.

There is no create/update schema in here, and that is the point: a revision is
never written by a client. Versions are minted by `version_service` whenever the
article itself changes, so the only client-writable payload in the whole module
is the rollback note. If a client could POST a version body it could forge
history — invent an author, backdate a change, claim an edit it never made.

Two read shapes exist because a snapshot is large:

* `ContentVersionListItem` — metadata only, for the history sidebar. Dropping
  `content_markdown` / `content_html` keeps a 50-revision list from shipping a
  megabyte of duplicated article bodies over the wire.
* `ContentVersionRead` — the full snapshot, for "view this revision".

`ContentVersionDiff` carries the unified diff as a list of classified lines
rather than one blob: the UI colours each line directly, and `kind` is resolved
server-side because the raw `difflib` prefix is ambiguous — a markdown body line
that legitimately begins with `-` is indistinguishable from a deletion once the
text is concatenated.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.versions import CONTENT_CHANGE_TYPES


# ------------------------------------------------------------------ read models

class ContentVersionDiffStats(BaseModel):
    """Character and word deltas against the immediately previous version."""
    added_chars: int = 0
    removed_chars: int = 0
    added_words: int = 0
    removed_words: int = 0


class ContentVersionListItem(BaseModel):
    """One row of the history sidebar — no bodies.

    `change_summary` is included because it is short and it is the only thing
    that explains *why* a revision exists; the bodies are fetched on demand by
    `GET /versions/{version_id}`.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID
    article_id: UUID
    version_number: int
    title: str
    seo_score: int
    change_type: str
    change_summary: str | None = None
    changed_by: UUID | None = None
    diff_stats: dict = Field(default_factory=dict)
    is_current: bool
    created_at: datetime


class ContentVersionRead(ContentVersionListItem):
    """A full snapshot, including both rendered forms of the body."""
    content_markdown: str
    content_html: str
    seo_metadata: dict = Field(default_factory=dict)


# ------------------------------------------------------------------------ diff

class ContentVersionDiffLine(BaseModel):
    """One line of a unified diff.

    `kind` is normalised out of the raw prefix so the frontend does not have to
    parse the first character (and does not mistake a hunk header `@@` for a
    context line, or a body line that legitimately starts with `-` for a
    deletion).
    """
    kind: str  # "context" | "added" | "removed" | "header" | "hunk"
    text: str


class ContentVersionDiff(BaseModel):
    """Line-level comparison of two revisions of the same article.

    Built with the stdlib `difflib` on `content_markdown` — the markdown is the
    authored form, so a diff over it reads like the change the person actually
    made, whereas diffing the generated HTML shows tag churn.
    """
    article_id: UUID
    from_version_number: int
    to_version_number: int
    from_created_at: datetime
    to_created_at: datetime

    # Title is compared separately: it lives outside the body but is the change
    # a reader notices first.
    title_changed: bool = False
    from_title: str
    to_title: str

    from_seo_score: int
    to_seo_score: int
    seo_score_delta: int = 0

    stats: ContentVersionDiffStats
    lines: list[ContentVersionDiffLine] = Field(default_factory=list)
    # True when the two snapshots have identical markdown — the UI shows "no
    # content change" rather than an empty diff pane that looks like a failure.
    identical: bool = False
    # Set when the diff was cut off at the line cap; the UI warns instead of
    # implying the change ended there.
    truncated: bool = False


# --------------------------------------------------------------------- summary

class ContentVersionSummary(BaseModel):
    """Header counters for the history panel."""
    article_id: UUID
    total_versions: int = 0
    current_version_number: int | None = None
    last_changed_at: datetime | None = None
    # Distinct non-null `changed_by`. Excludes worker/AI writes by construction,
    # so this is "how many people touched this", not "how many writes happened".
    contributors: int = 0


# ---------------------------------------------------------------- client writes

class ContentVersionRollbackRequest(BaseModel):
    """The only client-writable payload in this module.

    A note, nothing else. The target revision is the path parameter and the new
    version's content is copied from it server-side, so a client cannot restore
    one revision while claiming it restored another.
    """
    change_summary: str | None = Field(default=None, max_length=2000)


class ContentVersionRollbackResult(BaseModel):
    """What rollback produced: the appended version, plus where it came from."""
    restored_from_version_number: int
    new_version: ContentVersionRead


# --------------------------------------------------------------- vocabularies

class ContentVersionChangeType(BaseModel):
    """Wrapper used only to validate a change_type coming from a caller.

    Services are also driven by workers where no schema was involved, so the
    vocabulary check is repeated there; this exists for the rare router that
    accepts a change_type as a query filter.
    """
    change_type: str

    @field_validator("change_type")
    @classmethod
    def _known_change_type(cls, v: str) -> str:
        if v not in CONTENT_CHANGE_TYPES:
            raise ValueError(
                f"change_type must be one of {sorted(CONTENT_CHANGE_TYPES)}"
            )
        return v


__all__ = [
    "ContentVersionDiffStats",
    "ContentVersionListItem",
    "ContentVersionRead",
    "ContentVersionDiffLine",
    "ContentVersionDiff",
    "ContentVersionSummary",
    "ContentVersionRollbackRequest",
    "ContentVersionRollbackResult",
    "ContentVersionChangeType",
    "CONTENT_CHANGE_TYPES",
]
