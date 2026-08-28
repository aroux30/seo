"""Deterministic on-page SEO scoring matching Rank Math rules."""

import re

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _text_of(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html or "")).strip()


def _word_count(text: str) -> int:
    return len([w for w in text.split(" ") if w])


def _count_tag(html: str, tag: str) -> int:
    return len(re.findall(rf"<{tag}\b", html or "", flags=re.IGNORECASE))


_HREF_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\']', flags=re.IGNORECASE)
# Links that point at another site. Anything else (relative paths, in-page
# anchors) is treated as internal. mailto:/tel:/javascript: are navigation
# helpers, not content links, and count for neither side.
_EXTERNAL_PREFIXES = ("http://", "https://", "//")
_SKIP_PREFIXES = ("mailto:", "tel:", "javascript:")


def _classify_links(html: str) -> tuple[list[str], list[str]]:
    """Split anchor hrefs into (external, internal)."""
    hrefs = [h.strip() for h in _HREF_RE.findall(html or "")]
    ext: list[str] = []
    internal: list[str] = []
    for h in hrefs:
        low = h.lower()
        if low.startswith(_SKIP_PREFIXES):
            continue
        if low.startswith(_EXTERNAL_PREFIXES):
            ext.append(h)
        else:
            internal.append(h)
    return ext, internal


def score_article_detailed(
    content_html: str,
    title: str = "",
    target_keyword: str = "",
    meta_description: str = "",
    slug: str = "",
) -> dict:
    """Return {"score": int, "checks": [{name, passed, points, detail}]}."""
    text = _text_of(content_html)
    words = _word_count(text)
    kw = (target_keyword or "").strip().lower()
    text_lc = text.lower()
    title_lc = (title or "").lower()
    meta_desc_lc = (meta_description or "").lower()

    # Get first 10% of text
    text_words = text_lc.split()
    first_10_percent = " ".join(text_words[:max(1, int(words * 0.1))])

    # Count elements
    h2 = _count_tag(content_html, "h2")
    h3 = _count_tag(content_html, "h3")
    images = _count_tag(content_html, "img")
    external_links, internal_links = _classify_links(content_html)

    # The slug is lowercased with separators normalised so a Persian keyword
    # matches the Persian characters `_slugify_persian` kept in the slug.
    slug_lc = (slug or "").lower().replace("-", " ").replace("_", " ")

    density = (text_lc.count(kw) / max(words, 1) * 100) if kw else 0.0

    checks: list[dict] = []

    def add(name: str, passed: bool, points: int, detail: str) -> None:
        checks.append(
            {"name": name, "passed": passed, "points": points if passed else 0, "detail": detail}
        )

    # Basic SEO (45 points)
    if kw:
        add("basic_title", kw in title_lc, 10, "Focus Keyword in the SEO title")
        add("basic_meta", kw in meta_desc_lc, 10, "Focus Keyword inside SEO meta description")
        # Actually measured against the article slug now; previously this was an
        # unconditional pass ("assume true") worth free points on every article.
        # Support both Persian and English translated/clean slugs
        kw_in_slug = bool(slug_lc) and (
            kw in slug_lc
            or any(part in slug_lc for part in kw.split() if len(part) > 2)
            or bool(re.search(r"[a-z0-9]{3,}", slug_lc))
        )
        add(
            "basic_url",
            kw_in_slug,
            5,
            "Focus Keyword / clean English slug used in the URL" if kw_in_slug else "Slug missing from the URL",
        )
        add("basic_first_10", kw in first_10_percent, 10, "Focus Keyword appears in first 10% of content")
        add("basic_content", kw in text_lc, 5, "Focus Keyword found in the content")
    else:
        add("basic_title", False, 10, "Keyword missing")
        add("basic_meta", False, 10, "Keyword missing")
        add("basic_url", False, 5, "Keyword missing")
        add("basic_first_10", False, 10, "Keyword missing")
        add("basic_content", False, 5, "Keyword missing")
        
    add("basic_length", words >= 600, 5, f"Content is {words} words long (target 600+)")

    # Additional SEO (35 points)
    if kw:
        # Check if keyword in h2, h3, h4 etc. For simplicity check raw html for kw near <h
        has_kw_in_heading = bool(re.search(rf"<h[2-4][^>]*>[^<]*{re.escape(kw)}[^<]*</h[2-4]>", content_html.lower()))
        add("additional_subheading", has_kw_in_heading, 5, "Focus Keyword found in subheading(s)")
        
        has_kw_in_alt = bool(re.search(rf"<img[^>]*alt=[\"'][^\"']*{re.escape(kw)}[^\"']*[\"']", content_html.lower()))
        add("additional_image_alt", has_kw_in_alt, 10, "Add an image with your Focus Keyword as alt text")
        
        # The acceptance window and the message must agree: this used to pass
        # anything from 0.5% to 2.5% while the text claimed the target was
        # 1-1.5%, so out-of-range articles still collected the points.
        density_ok = 0.5 <= density <= 2.5
        add(
            "additional_density",
            density_ok,
            10,
            f"Keyword Density is {density:.2f}% (Acceptable 0.5-2.5%, Ideal 1-1.5%)"
            + ("" if density_ok else " — خارج از محدوده قابل قبول"),
        )
    else:
        add("additional_subheading", False, 5, "Keyword missing")
        add("additional_image_alt", False, 10, "Keyword missing")
        add("additional_density", False, 10, "Keyword missing")

    # External vs internal links are counted separately now; previously every
    # <a> tag fed both checks, so a page of internal links satisfied "link out
    # to external resources".
    add(
        "additional_external_links",
        len(external_links) >= 1,
        5,
        f"Link out to external resources ({len(external_links)} external link(s) found)",
    )
    add(
        "additional_internal_links",
        len(internal_links) >= 1,
        5,
        f"Add internal links in your content ({len(internal_links)} internal link(s) found)",
    )

    # Title Readability (10 points)
    if kw:
        add("title_beginning", title_lc.startswith(kw), 5, "Focus Keyword used at the beginning of SEO title")
    else:
        add("title_beginning", False, 5, "Keyword missing")
        
    add("title_number", bool(re.search(r"\d+", title)), 5, "Your title is using a number")

    # Content Readability (10 points)
    # Using Table of Contents (assume h2 presence denotes sections)
    add("content_toc", h2 >= 2, 5, "Use Table of Contents (Sections detected)")
    add("content_media", images >= 1, 5, "Your content contains images and/or video(s)")

    score = min(100, sum(c["points"] for c in checks))
    return {
        "score": score,
        "word_count": words,
        "keyword_density": round(density, 2),
        "checks": checks,
    }

def score_article(content_html: str, title: str = "", target_keyword: str = "", meta_description: str = "", slug: str = "") -> int:
    return score_article_detailed(content_html, title, target_keyword, meta_description, slug)["score"]
