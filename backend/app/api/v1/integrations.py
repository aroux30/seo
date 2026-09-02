from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.core.scoping import assert_website_in_org
from app.core.oauth_state import issue_state, verify_state, InvalidOAuthState
from app.models import User, OrganizationMember
from app.schemas import (
    OAuthIntegrationRead, WordPressConnectRequest, WordPressIntegrationRead,
)
from app.services.gsc_service import (
    get_gsc_auth_url, save_oauth_tokens, get_oauth_integration, sync_gsc_data,
)
from app.services.wordpress_service import (
    connect_wordpress, get_wordpress_integration, list_wp_categories,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/gsc/auth-url", response_model=dict)
async def gsc_auth_url(
    website_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Get Google OAuth 2.0 Consent screen redirect URL for Search Console."""
    await assert_website_in_org(db, website_id, member.organization_id)
    # Signed state: the callback will not accept anything we did not issue.
    url = get_gsc_auth_url(website_id, state=issue_state(website_id))
    return {"data": {"auth_url": url, "website_id": str(website_id)}}


@router.get("/gsc/callback")
async def gsc_callback(
    state: str = Query(...),
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback and save tokens."""
    import httpx
    from fastapi import HTTPException
    from app.config import get_settings
    
    # CSRF: only accept a state this backend signed and issued recently.
    # A forged state would otherwise let an attacker bind their own Google
    # account to someone else's website.
    try:
        website_id = verify_state(state)
    except InvalidOAuthState as exc:
        raise HTTPException(status_code=400, detail=f"Invalid state parameter: {exc}")

    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        logger.error("Google token exchange timed out or network error: %s", exc)
        raise HTTPException(status_code=504, detail="Google OAuth service timed out or is unreachable")
    
    if resp.status_code != 200:
        logger.warning("Google token exchange failed with HTTP %s", resp.status_code)
        raise HTTPException(status_code=502, detail="Google authentication service failed to exchange authorization code")

    token_data = resp.json()

    integration = await save_oauth_tokens(
        db=db,
        website_id=website_id,
        access_token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        expires_in=token_data.get("expires_in", 3600),
    )
    await db.commit()
    
    from fastapi.responses import RedirectResponse
    frontend_url = f"https://{settings.DOMAIN}" if hasattr(settings, "DOMAIN") and settings.DOMAIN else "https://seo.arouxpingg.com"
    return RedirectResponse(url=f"{frontend_url}/websites/{website_id}/integrations")


@router.get("/gsc/status/{website_id}", response_model=dict)
async def gsc_status(
    website_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    integration = await get_oauth_integration(db, website_id)
    if not integration:
        return {"data": {"is_connected": False, "provider": "google_search_console"}}
    return {
        "data": {
            "is_connected": True,
            "provider": integration.provider,
            "expires_at": integration.expires_at,
            "created_at": integration.created_at,
        }
    }


@router.post("/gsc/sync/{website_id}", response_model=dict)
async def trigger_gsc_sync(
    website_id: UUID,
    days: int = Query(30, ge=1, le=90),
    search_type: str = Query("web"),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Trigger synchronous or background GSC data sync for website."""
    await assert_website_in_org(db, website_id, member.organization_id)
    res = await sync_gsc_data(db, website_id, days=days, search_type=search_type)
    await db.commit()
    return {"data": res}


@router.post("/wordpress/connect", response_model=dict, status_code=status.HTTP_201_CREATED)
async def connect_wp(
    website_id: UUID,
    body: WordPressConnectRequest,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Verify and connect WordPress site via REST API Application Password."""
    await assert_website_in_org(db, website_id, member.organization_id)
    integration = await connect_wordpress(
        db, website_id, body.wp_url, body.username, body.app_password,
    )
    await db.commit()
    return {"data": WordPressIntegrationRead.model_validate(integration)}


@router.get("/wordpress/status/{website_id}", response_model=dict)
async def wp_status(
    website_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    integration = await get_wordpress_integration(db, website_id)
    if not integration:
        return {"data": {"is_connected": False}}
    return {
        "data": {
            "is_connected": True,
            "wp_url": integration.wp_url,
            "username": integration.username,
            "status": integration.status,
            "last_synced_at": integration.last_synced_at,
        }
    }


@router.get("/wordpress/categories/{website_id}", response_model=dict)
async def wp_categories(
    website_id: UUID,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    categories = await list_wp_categories(db, website_id)
    return {"data": categories}
