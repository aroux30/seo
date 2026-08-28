from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.resources import projects_router, websites_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.audits import router as audits_router
from app.api.v1.strategies import router as strategies_router
from app.api.v1.content import router as content_router
from app.api.v1.automations import router as automations_router
from app.api.v1.insights import (
    opportunities_router,
    alerts_router,
    notifications_router,
)
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.categories import router as categories_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.reports import router as reports_router
from app.api.v1.versions import router as versions_router
from app.api.v1.internal_links import router as internal_links_router
from app.api.v1.agent_activity import router as agent_activity_router
from app.api.v1.kpi import router as kpi_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(projects_router)
api_router.include_router(websites_router)
api_router.include_router(integrations_router)
api_router.include_router(analytics_router)
api_router.include_router(keywords_router)
api_router.include_router(audits_router)
api_router.include_router(strategies_router)
api_router.include_router(content_router)
api_router.include_router(automations_router)
api_router.include_router(opportunities_router)
api_router.include_router(alerts_router)
api_router.include_router(notifications_router)
api_router.include_router(dashboard_router)
api_router.include_router(approvals_router)
api_router.include_router(categories_router)
api_router.include_router(calendar_router)
api_router.include_router(reports_router)
api_router.include_router(versions_router)
api_router.include_router(internal_links_router)
api_router.include_router(agent_activity_router)
api_router.include_router(kpi_router)

__all__ = ["api_router"]

