import urllib.parse
from datetime import datetime, date, timedelta, timezone
from uuid import UUID
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.encryption import encrypt_value, decrypt_value
from app.core.exceptions import NotFoundError, AppException
from app.models import OAuthIntegration, GscQuery, GscPage, Website, Keyword, GscCountry, GscDevice, GscDate

settings = get_settings()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def get_gsc_auth_url(website_id: UUID, state: str) -> str:
    """Generate Google OAuth 2.0 authorization URL for Search Console API.

    `state` is REQUIRED and must come from core.oauth_state.issue_state. It is
    passed through verbatim — prefixing website_id here again would break
    signature verification in the callback. There is deliberately no default:
    an unsigned state is always rejected downstream, so a silent fallback would
    only produce auth URLs that fail at the callback.
    """
    if not state:
        raise ValueError("get_gsc_auth_url requires a signed state (see core.oauth_state.issue_state)")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID or "placeholder_client_id",
        "redirect_uri": settings.GOOGLE_REDIRECT_URI or "http://localhost:8000/api/v1/integrations/gsc/callback",
        "response_type": "code",
        "scope": GSC_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def save_oauth_tokens(
    db: AsyncSession,
    website_id: UUID,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int = 3600,
) -> OAuthIntegration:
    """Encrypt and store Google OAuth tokens for a website."""
    stmt = select(OAuthIntegration).where(
        OAuthIntegration.website_id == website_id,
        OAuthIntegration.provider == "google_search_console",
    )
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()

    encrypted_access = encrypt_value(access_token)
    encrypted_refresh = encrypt_value(refresh_token) if refresh_token else None
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    if not integration:
        integration = OAuthIntegration(
            website_id=website_id,
            provider="google_search_console",
            client_id=settings.GOOGLE_CLIENT_ID,
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            scopes=GSC_SCOPE,
            expires_at=expires_at,
            is_active=True,
        )
        db.add(integration)
    else:
        integration.encrypted_access_token = encrypted_access
        if encrypted_refresh:
            integration.encrypted_refresh_token = encrypted_refresh
        integration.expires_at = expires_at
        integration.is_active = True

    await db.flush()
    return integration


async def get_oauth_integration(db: AsyncSession, website_id: UUID) -> OAuthIntegration | None:
    stmt = select(OAuthIntegration).where(
        OAuthIntegration.website_id == website_id,
        OAuthIntegration.provider == "google_search_console",
        OAuthIntegration.is_active == True,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


import httpx

async def refresh_google_token(db: AsyncSession, integration: OAuthIntegration) -> str:
    refresh_token = decrypt_value(integration.encrypted_refresh_token) if integration.encrypted_refresh_token else None
    if not refresh_token:
        raise AppException(401, "No refresh token available to renew session. Please reconnect Google Search Console.")

    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data=data)
        if resp.status_code != 200:
            raise AppException(401, f"Failed to refresh Google token: {resp.text}")
        
        tokens = resp.json()
        new_access_token = tokens["access_token"]
        expires_in = tokens.get("expires_in", 3600)
        
        integration.encrypted_access_token = encrypt_value(new_access_token)
        integration.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        await db.flush()
        
        return new_access_token

async def fetch_gsc_data(site_url: str, access_token: str, start_date: str, end_date: str, dimensions: list[str], search_type: str = "web") -> list[dict]:
    api_url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site_url, safe='')}/searchAnalytics/query"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "type": search_type,
        "rowLimit": 2000
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(api_url, headers=headers, json=payload)
        
        if resp.status_code == 401:
            return {"error": "unauthorized"}
        elif resp.status_code != 200:
            raise AppException(500, f"Google API Error: {resp.text}")
            
        return resp.json().get("rows", [])

async def sync_gsc_data(
    db: AsyncSession,
    website_id: UUID,
    days: int = 30,
    search_type: str = "web",
) -> dict:
    """
    Sync GSC performance metrics (queries, pages, countries, devices).
    Requires a valid Google OAuth integration.
    """
    stmt = select(Website).where(Website.id == website_id)
    result = await db.execute(stmt)
    website = result.scalar_one_or_none()
    if not website:
        raise NotFoundError("Website", str(website_id))

    integration = await get_oauth_integration(db, website_id)
    if not integration:
        raise AppException(400, "Google Search Console integration not found. Please connect your Google account first.")

    access_token = decrypt_value(integration.encrypted_access_token)
    
    today = date.today()
    start_date = (today - timedelta(days=days)).isoformat()
    end_date = today.isoformat()
    
    # Try different combinations for site_url in case GSC property is registered differently
    base_domain = website.base_url.replace("https://", "").replace("http://", "").strip("/")
    root_domain = base_domain[4:] if base_domain.startswith("www.") else base_domain
    
    site_url_variations = []
    # Always prioritize the exact URL the user provided, so http/https are treated distinctly
    site_url_variations.append(website.base_url)
    if not website.base_url.endswith('/'):
        site_url_variations.append(website.base_url + '/')
        
    # We removed sc-domain and other protocol fallbacks here because the user
    # explicitly expects strict matching. If they add http://, it should only 
    # fetch http:// (and fail if not verified), rather than silently fetching https://.
    
    queries_data = None
    pages_data = None
    countries_data = None
    devices_data = None
    dates_data = None
    successful_url = website.base_url
    

    for test_url in site_url_variations:
        try:
            q_data = await fetch_gsc_data(test_url, access_token, start_date, end_date, ["query"], search_type)
            if isinstance(q_data, dict) and q_data.get("error") == "unauthorized":
                access_token = await refresh_google_token(db, integration)
                q_data = await fetch_gsc_data(test_url, access_token, start_date, end_date, ["query"], search_type)
                
            if isinstance(q_data, list):
                # We found a valid property (returns 200 OK), stop searching.
                # Use it immediately even if it has no data right now, to prevent
                # falling back to sc-domain for a specific HTTP/HTTPS prefix.
                queries_data = q_data
                successful_url = test_url
                break
        except AppException:
            continue
        
    if isinstance(queries_data, list):
        # Now fetch the rest of the dimensions using the successful URL
        pages_data = await fetch_gsc_data(successful_url, access_token, start_date, end_date, ["page"], search_type)
        countries_data = await fetch_gsc_data(successful_url, access_token, start_date, end_date, ["country"], search_type)
        devices_data = await fetch_gsc_data(successful_url, access_token, start_date, end_date, ["device"], search_type)
        dates_data = await fetch_gsc_data(successful_url, access_token, start_date, end_date, ["date"], search_type)
            
    if not isinstance(queries_data, list) or not isinstance(pages_data, list):
        raise AppException(403, f"Failed to access Google Search Console data for {website.base_url}. Ensure the property exists and the email has access.")
    
    # Clear old data for the timeframe
    await db.execute(GscQuery.__table__.delete().where(
        GscQuery.website_id == website_id, GscQuery.date_metric >= (today - timedelta(days=days))
    ))
    await db.execute(GscPage.__table__.delete().where(
        GscPage.website_id == website_id, GscPage.date_metric >= (today - timedelta(days=days))
    ))
    await db.execute(GscCountry.__table__.delete().where(
        GscCountry.website_id == website_id, GscCountry.date_metric >= (today - timedelta(days=days))
    ))
    await db.execute(GscDevice.__table__.delete().where(
        GscDevice.website_id == website_id, GscDevice.date_metric >= (today - timedelta(days=days))
    ))
    await db.execute(GscDate.__table__.delete().where(
        GscDate.website_id == website_id, GscDate.date_metric >= (today - timedelta(days=days))
    ))
    
    q_objects, p_objects, c_objects, d_objects, dt_objects = [], [], [], [], []
    
    # Insert new queries
    for row in queries_data:
        keys = row.get("keys", [""])
        q_objects.append(GscQuery(
            website_id=website_id, query=keys[0], clicks=int(row.get("clicks", 0)),
            impressions=int(row.get("impressions", 0)), ctr=float(row.get("ctr", 0.0)),
            position=float(row.get("position", 0.0)), date_metric=today
        ))
        
    # Insert new pages
    for row in pages_data:
        keys = row.get("keys", [""])
        p_objects.append(GscPage(
            website_id=website_id, page_url=keys[0], clicks=int(row.get("clicks", 0)),
            impressions=int(row.get("impressions", 0)), ctr=float(row.get("ctr", 0.0)),
            position=float(row.get("position", 0.0)), date_metric=today
        ))
        
    # Insert new countries
    if isinstance(countries_data, list):
        for row in countries_data:
            keys = row.get("keys", [""])
            c_objects.append(GscCountry(
                website_id=website_id, country=keys[0].upper(), clicks=int(row.get("clicks", 0)),
                impressions=int(row.get("impressions", 0)), ctr=float(row.get("ctr", 0.0)),
                position=float(row.get("position", 0.0)), date_metric=today
            ))
            
    # Insert new devices
    if isinstance(devices_data, list):
        for row in devices_data:
            keys = row.get("keys", [""])
            d_objects.append(GscDevice(
                website_id=website_id, device=keys[0].upper(), clicks=int(row.get("clicks", 0)),
                impressions=int(row.get("impressions", 0)), ctr=float(row.get("ctr", 0.0)),
                position=float(row.get("position", 0.0)), date_metric=today
            ))
            
    # Insert new dates
    if isinstance(dates_data, list):
        for row in dates_data:
            keys = row.get("keys", [""])
            try:
                row_date = datetime.strptime(keys[0], "%Y-%m-%d").date()
            except ValueError:
                row_date = today
            dt_objects.append(GscDate(
                website_id=website_id, clicks=int(row.get("clicks", 0)),
                impressions=int(row.get("impressions", 0)), ctr=float(row.get("ctr", 0.0)),
                position=float(row.get("position", 0.0)), date_metric=row_date
            ))

    if q_objects: db.add_all(q_objects)
    if p_objects: db.add_all(p_objects)
    if c_objects: db.add_all(c_objects)
    if d_objects: db.add_all(d_objects)
    if dt_objects: db.add_all(dt_objects)
        
    await db.flush()

    # Update Keywords position
    stmt = select(Keyword).where(Keyword.website_id == website_id)
    res = await db.execute(stmt)
    tracked_keywords = res.scalars().all()
    
    if tracked_keywords and q_objects:
        gsc_lookup = {}
        for q in q_objects:
            kw = q.query.lower().strip()
            pos = float(q.position)
            if kw not in gsc_lookup or pos < gsc_lookup[kw]:
                gsc_lookup[kw] = pos
                
        for kw_obj in tracked_keywords:
            clean_kw = kw_obj.keyword.lower().strip()
            if clean_kw in gsc_lookup:
                new_pos = gsc_lookup[clean_kw]
                kw_obj.last_position = new_pos
                if kw_obj.best_position is None or new_pos < kw_obj.best_position:
                    kw_obj.best_position = new_pos

        await db.flush()
        
    return {
        "status": "success",
        "message": "Google Search Console data synced successfully.",
        "website_id": str(website_id),
        "synced_date": str(today),
        "queries_added": len(q_objects),
        "pages_added": len(p_objects),
        "countries_added": len(c_objects),
        "devices_added": len(d_objects),
        "dates_added": len(dt_objects),
    }

async def get_gsc_overview(db: AsyncSession, website_id: UUID) -> dict:
    """Calculate aggregated Search Console performance metrics for a website."""
    stmt = select(
        func.coalesce(func.sum(GscQuery.clicks), 0).label("total_clicks"),
        func.coalesce(func.sum(GscQuery.impressions), 0).label("total_impressions"),
        func.coalesce(func.avg(GscQuery.ctr), 0.0).label("avg_ctr"),
        func.coalesce(func.avg(GscQuery.position), 0.0).label("avg_position"),
    ).where(GscQuery.website_id == website_id)

    result = await db.execute(stmt)
    row = result.one()
    return {
        "total_clicks": int(row.total_clicks),
        "total_impressions": int(row.total_impressions),
        "avg_ctr": round(float(row.avg_ctr), 2),
        "avg_position": round(float(row.avg_position), 1),
    }


async def list_gsc_queries(db: AsyncSession, website_id: UUID, limit: int = 100, sort_by: str = "clicks") -> list[GscQuery]:
    order_col = GscQuery.clicks
    if sort_by == "impressions":
        order_col = GscQuery.impressions
    elif sort_by == "ctr":
        order_col = GscQuery.ctr
    elif sort_by == "position":
        order_col = GscQuery.position

    stmt = (
        select(GscQuery)
        .where(GscQuery.website_id == website_id)
        .order_by(desc(order_col) if sort_by != "position" else order_col.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_gsc_pages(db: AsyncSession, website_id: UUID, limit: int = 100, sort_by: str = "clicks") -> list[GscPage]:
    order_col = GscPage.clicks
    if sort_by == "impressions":
        order_col = GscPage.impressions
    elif sort_by == "ctr":
        order_col = GscPage.ctr
    elif sort_by == "position":
        order_col = GscPage.position

    stmt = (
        select(GscPage)
        .where(GscPage.website_id == website_id)
        .order_by(desc(order_col) if sort_by != "position" else order_col.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def list_gsc_countries(db: AsyncSession, website_id: UUID, limit: int = 100, sort_by: str = "clicks") -> list[GscCountry]:
    order_col = GscCountry.clicks
    if sort_by == "impressions":
        order_col = GscCountry.impressions
    elif sort_by == "ctr":
        order_col = GscCountry.ctr
    elif sort_by == "position":
        order_col = GscCountry.position

    stmt = select(GscCountry).where(GscCountry.website_id == website_id).order_by(desc(order_col) if sort_by != "position" else order_col.asc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def list_gsc_devices(db: AsyncSession, website_id: UUID, limit: int = 100, sort_by: str = "clicks") -> list[GscDevice]:
    order_col = GscDevice.clicks
    if sort_by == "impressions":
        order_col = GscDevice.impressions
    elif sort_by == "ctr":
        order_col = GscDevice.ctr
    elif sort_by == "position":
        order_col = GscDevice.position

    stmt = select(GscDevice).where(GscDevice.website_id == website_id).order_by(desc(order_col) if sort_by != "position" else order_col.asc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def list_gsc_dates(db: AsyncSession, website_id: UUID, limit: int = 100, sort_by: str = "date") -> list[GscDate]:
    order_col = GscDate.date_metric
    if sort_by == "clicks":
        order_col = GscDate.clicks
    elif sort_by == "impressions":
        order_col = GscDate.impressions
    elif sort_by == "ctr":
        order_col = GscDate.ctr
    elif sort_by == "position":
        order_col = GscDate.position

    stmt = select(GscDate).where(GscDate.website_id == website_id).order_by(desc(order_col) if sort_by != "position" else order_col.asc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
