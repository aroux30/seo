"""Organization scoping guards.

Every resource in this platform hangs off a Website, and every Website belongs to
exactly one Organization. `require_role()` only proves that the caller is a member
of *some* organization (the one named in the `X-Organization-Id` header) — it does
NOT prove that the `{website_id}` / `{article_id}` / ... in the URL belongs to that
organization.

Without the guards in this module, any authenticated user can read or mutate another
tenant's data simply by supplying its UUID. Every endpoint that accepts a resource
id in its path or query MUST call the matching `assert_*` helper before touching it.

All helpers raise `NotFoundError` (404) rather than `ForbiddenError` (403) on a
cross-tenant hit, so an attacker cannot use the status code to distinguish
"exists but belongs to someone else" from "does not exist" (no UUID enumeration
oracle).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import (
    AiSeoStrategy,
    Alert,
    AutomationWorkflow,
    ContentArticle,
    ContentBrief,
    Keyword,
    Opportunity,
    SeoAudit,
    SeoAuditIssue,
    Website,
)

__all__ = [
    "assert_org_matches",
    "assert_website_in_org",
    "assert_keyword_in_org",
    "assert_audit_in_org",
    "assert_audit_issue_in_org",
    "assert_strategy_in_org",
    "assert_brief_in_org",
    "assert_article_in_org",
    "assert_workflow_in_org",
    "assert_opportunity_in_org",
    "assert_alert_in_org",
]


async def assert_website_in_org(
    db: AsyncSession, website_id: UUID, org_id: UUID
) -> Website:
    """Return the website if it exists and is active within the specified organization."""
    result = await db.execute(
        select(Website).where(
            Website.id == website_id,
            Website.organization_id == org_id,
            Website.deleted_at.is_(None),
        )
    )
    website = result.scalar_one_or_none()
    if not website:
        raise NotFoundError("Website", str(website_id))
    return website


async def _assert_child_in_org(
    db: AsyncSession, model, resource_id: UUID, org_id: UUID, label: str
):
    """Shared implementation for resources that reference a website directly within the organization."""
    result = await db.execute(
        select(model)
        .join(Website, Website.id == model.website_id)
        .where(
            model.id == resource_id,
            Website.organization_id == org_id,
            Website.deleted_at.is_(None),
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise NotFoundError(label, str(resource_id))
    return obj


async def assert_keyword_in_org(
    db: AsyncSession, keyword_id: UUID, org_id: UUID
) -> Keyword:
    return await _assert_child_in_org(db, Keyword, keyword_id, org_id, "Keyword")


async def assert_audit_in_org(
    db: AsyncSession, audit_id: UUID, org_id: UUID
) -> SeoAudit:
    return await _assert_child_in_org(db, SeoAudit, audit_id, org_id, "SeoAudit")


async def assert_strategy_in_org(
    db: AsyncSession, strategy_id: UUID, org_id: UUID
) -> AiSeoStrategy:
    return await _assert_child_in_org(
        db, AiSeoStrategy, strategy_id, org_id, "AiSeoStrategy"
    )


async def assert_brief_in_org(
    db: AsyncSession, brief_id: UUID, org_id: UUID
) -> ContentBrief:
    return await _assert_child_in_org(db, ContentBrief, brief_id, org_id, "ContentBrief")


async def assert_article_in_org(
    db: AsyncSession, article_id: UUID, org_id: UUID
) -> ContentArticle:
    return await _assert_child_in_org(
        db, ContentArticle, article_id, org_id, "ContentArticle"
    )


async def assert_workflow_in_org(
    db: AsyncSession, workflow_id: UUID, org_id: UUID
) -> AutomationWorkflow:
    return await _assert_child_in_org(
        db, AutomationWorkflow, workflow_id, org_id, "AutomationWorkflow"
    )


async def assert_audit_issue_in_org(
    db: AsyncSession, issue_id: UUID, org_id: UUID
) -> SeoAuditIssue:
    return await _assert_child_in_org(
        db, SeoAuditIssue, issue_id, org_id, "SeoAuditIssue"
    )


async def assert_opportunity_in_org(
    db: AsyncSession, opportunity_id: UUID, org_id: UUID
) -> Opportunity:
    # Opportunity carries organization_id of its own, but the join through
    # Website is what the other guards use and it also enforces
    # `deleted_at IS NULL`: a finding on a soft-deleted website must not be
    # reachable just because its denormalised org column still matches.
    return await _assert_child_in_org(
        db, Opportunity, opportunity_id, org_id, "Opportunity"
    )


async def assert_alert_in_org(
    db: AsyncSession, alert_id: UUID, org_id: UUID
) -> Alert:
    return await _assert_child_in_org(db, Alert, alert_id, org_id, "Alert")


def assert_org_matches(member, org_id: UUID) -> None:
    """Guard endpoints that take an `{org_id}` path param.

    `require_role()` resolves the caller's membership from the
    `X-Organization-Id` header, NOT from the URL. Without this check a viewer in
    org A could pass org B's id in the path and have the role check pass against
    their org-A membership while the service reads org B's row.
    """
    if member.organization_id != org_id:
        raise NotFoundError("Organization", str(org_id))
