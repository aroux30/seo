"""Markdown rendering and HTML sanitization.

Article bodies come from two untrusted-ish places: an LLM, and a human editor.
Neither output may be inserted into a page verbatim — the frontend renders
`content_html` with `dangerouslySetInnerHTML`, so any `<script>`, `onerror=`, or
`javascript:` URL that survives to storage becomes stored XSS against every
authenticated user who opens the article.

Sanitizing on write (here) rather than only on render means the database never
holds a hostile payload, and every consumer — the app, the WordPress publisher,
any future export — inherits the guarantee.
"""

import bleach
import markdown as _markdown

# Tags an SEO article legitimately needs. Deliberately excludes <script>,
# <style>, <iframe>, <object>, <embed>, <form>, and event-handler carriers.
ALLOWED_TAGS = [
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "del", "mark", "small", "sub", "sup",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "a", "img",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "div", "span", "figure", "figcaption",
]

ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "dir", "lang", "title"],
    "a": ["href", "rel", "target"],
    "img": ["src", "alt", "width", "height", "loading"],
    "td": ["colspan", "rowspan", "align"],
    "th": ["colspan", "rowspan", "align", "scope"],
}

# Anything else (javascript:, data:, vbscript:) is stripped.
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def sanitize_html(html: str) -> str:
    """Strip every tag/attribute/URL scheme not on the allowlist."""
    if not html:
        return ""
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    # Force external links to be safe to click.
    return bleach.linkifier.Linker(
        callbacks=[bleach.callbacks.nofollow, bleach.callbacks.target_blank],
        skip_tags=["pre", "code"],
    ).linkify(cleaned)


def markdown_to_html(md: str) -> str:
    """Render markdown to sanitized HTML.

    Replaces the previous behaviour, which wrote the *literal* string
    "{content_markdown}" into content_html because of a doubled brace in an
    f-string — silently discarding the author's real content on every edit.
    """
    if not md:
        return ""
    rendered = _markdown.markdown(
        md,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html",
    )
    return sanitize_html(rendered)
