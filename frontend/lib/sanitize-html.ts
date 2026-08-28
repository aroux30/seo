/**
 * Client-side HTML sanitizer for `dangerouslySetInnerHTML`.
 *
 * The backend now sanitizes article HTML on write (see `app/core/html.py`), so this
 * is defense-in-depth: articles stored *before* that fix still hold whatever the LLM
 * or a human editor produced, and this component renders them into an authenticated
 * page. A stored `<script>` or `onerror=` there is XSS against every user who opens
 * the article.
 *
 * Implemented with the browser's own DOMParser instead of a dependency so it works
 * without touching package.json. Parsing happens in an inert document — no scripts
 * execute, no images load, no network requests fire during parse.
 *
 * On the server (SSR) there is no DOMParser, so we return an empty string rather
 * than passing raw HTML through. Callers render this in a client component after
 * mount, so the only cost is that the first paint has no body.
 */

const ALLOWED_TAGS = new Set([
  "P", "BR", "HR",
  "H1", "H2", "H3", "H4", "H5", "H6",
  "STRONG", "B", "EM", "I", "U", "S", "DEL", "MARK", "SMALL", "SUB", "SUP",
  "UL", "OL", "LI",
  "BLOCKQUOTE", "PRE", "CODE",
  "A", "IMG",
  "TABLE", "THEAD", "TBODY", "TFOOT", "TR", "TH", "TD", "CAPTION",
  "DIV", "SPAN", "FIGURE", "FIGCAPTION",
]);

const ALLOWED_ATTRS: Record<string, Set<string>> = {
  "*": new Set(["class", "id", "dir", "lang", "title"]),
  A: new Set(["href", "rel", "target"]),
  IMG: new Set(["src", "alt", "width", "height", "loading"]),
  TD: new Set(["colspan", "rowspan", "align"]),
  TH: new Set(["colspan", "rowspan", "align", "scope"]),
};

const URL_ATTRS = new Set(["href", "src"]);
const SAFE_PROTOCOLS = ["http:", "https:", "mailto:"];

/** Reject `javascript:`, `data:`, and other scheme-based script vectors. */
function isSafeUrl(value: string): boolean {
  const trimmed = value.trim();
  // Protocol-relative and same-document/relative URLs carry no scheme, so they're safe.
  if (trimmed.startsWith("/") || trimmed.startsWith("#") || trimmed.startsWith("?")) {
    return true;
  }
  try {
    // A base is required so relative URLs resolve instead of throwing.
    const parsed = new URL(trimmed, "https://example.invalid");
    return SAFE_PROTOCOLS.includes(parsed.protocol);
  } catch {
    return false;
  }
}

function isAttrAllowed(tagName: string, attrName: string): boolean {
  if (ALLOWED_ATTRS["*"].has(attrName)) return true;
  return ALLOWED_ATTRS[tagName]?.has(attrName) ?? false;
}

export function sanitizeHtml(dirty: string): string {
  if (!dirty) return "";
  if (typeof window === "undefined" || typeof DOMParser === "undefined") return "";

  const doc = new DOMParser().parseFromString(dirty, "text/html");

  // Walk depth-first over a static list: the tree is mutated during the walk, and a
  // live NodeList would skip siblings as elements are unwrapped.
  const elements = Array.from(doc.body.querySelectorAll("*"));

  for (const el of elements) {
    // Element may already have been removed along with a discarded ancestor.
    if (!el.isConnected) continue;

    const tag = el.tagName.toUpperCase();

    if (!ALLOWED_TAGS.has(tag)) {
      // Drop script/style/iframe outright — keeping their text would dump code into
      // the page. Everything else is unwrapped so the author's prose survives.
      if (tag === "SCRIPT" || tag === "STYLE" || tag === "IFRAME" || tag === "OBJECT" ||
          tag === "EMBED" || tag === "TEMPLATE" || tag === "NOSCRIPT") {
        el.remove();
      } else {
        el.replaceWith(...Array.from(el.childNodes));
      }
      continue;
    }

    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();

      // Every `on*` handler is an execution vector; drop the whole family rather
      // than enumerating them.
      if (name.startsWith("on") || !isAttrAllowed(tag, name)) {
        el.removeAttribute(attr.name);
        continue;
      }
      if (URL_ATTRS.has(name) && !isSafeUrl(attr.value)) {
        el.removeAttribute(attr.name);
      }
    }

    // Anything we render came from outside, so external links must not be able to
    // reach back into this window via `window.opener`.
    if (tag === "A" && el.getAttribute("target") === "_blank") {
      el.setAttribute("rel", "noopener noreferrer");
    }
  }

  return doc.body.innerHTML;
}
