"""Internal link suggestion engine.

The platform already stores articles (`content_articles`) but nothing ever asked
the obvious question: which of these articles should be linking to each other?
Internal links are the cheapest ranking lever a site owns — no outreach, no new
content — and the highest-value case is the *orphan*: an article with zero
inbound internal links, which search engines therefore treat as barely part of
the site.

Shape mirrors opportunity_service deliberately: pure detectors produce candidate
dicts, then one persistence pass fingerprints, upserts, and expires. A new
detector cannot get the upsert semantics wrong because it never touches the DB.

Scoring is arithmetic and inspectable, never learned weights. Every suggestion
carries a `score_breakdown` showing exactly which components fired and for how
many points, because the number is shown to a user next to an "accept" button.

WEIGHT TABLE (max 100):
    shared_term_weight    up to 40   rarity-weighted overlap of meaningful terms
    orphan_boost             25      target currently has zero inbound links
    anchor_exact_match       20      target title appears verbatim in source text
    title_term_hit        up to 10   overlap terms that sit in the target's title
    corpus_scarcity       up to  5   small corpus -> every link matters more
                          -------
                          max 100
"""

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import ContentArticle, Website
from app.models.internal_links import InternalLink, InternalLinkSuggestion

# ------------------------------------------------------------- Persian tokenising
#
# Persian text normalisation is not cosmetic here, it decides whether two
# articles look related at all. Two specific problems:
#
# 1. Arabic vs Persian codepoints. The Arabic YEH (U+064A "ي") and KAF
#    (U+0643 "ك") are visually near-identical to Persian YEH (U+06CC "ی") and
#    KEHEH (U+06AF... actually U+06A9 "ک"), and Iranian keyboards, WordPress
#    imports and copy-pasted content mix them freely. Without folding them,
#    "کلیدی" typed two ways are two different tokens and the overlap detector
#    silently finds nothing. This is the single most common cause of "why does
#    Persian search/matching not work".
# 2. Diacritics (fatha/kasra/damma/sukun/tanwin, U+064B..U+0652) and the
#    zero-width non-joiner (U+200C) are optional in Persian writing. The same
#    word appears with and without them, so they are stripped before comparison.

_ARABIC_DIACRITICS = re.compile(r"[ً-ْـٰۖ-ۭ]")

# Characters folded to their Persian canonical form.
_CHAR_FOLD = {
    "ي": "ی",  # ARABIC YEH -> PERSIAN YEH
    "ى": "ی",  # ALEF MAKSURA -> PERSIAN YEH
    "ك": "ک",  # ARABIC KAF -> PERSIAN KEHEH
    "أ": "ا",  # ALEF WITH HAMZA ABOVE -> ALEF
    "إ": "ا",  # ALEF WITH HAMZA BELOW -> ALEF
    "آ": "ا",  # ALEF WITH MADDA -> ALEF
    "ة": "ه",  # TEH MARBUTA -> HEH
    "‌": " ",       # ZWNJ -> space (word boundary, not a letter)
    "‏": " ",       # RTL mark
    "‎": " ",       # LTR mark
    # Arabic-Indic and extended digits -> ASCII, so "۱۴۰۳" == "1403".
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}

_FOLD_TABLE = str.maketrans(_CHAR_FOLD)

# Split on anything that is not a letter or digit. \w with re.UNICODE keeps
# Persian letters, so the negation is a safe word-boundary splitter.
_NON_WORD = re.compile(r"[^\w؀-ۿ]+", re.UNICODE)

# Markdown scaffolding that would otherwise become tokens ("http", "www",
# heading hashes, list bullets, image/link syntax).
_MD_NOISE = re.compile(r"!?\[[^\]]*\]\([^)]*\)|https?://\S+|`[^`]*`|[#*_>~\-]{1,}")

# Persian/Arabic function words plus a few English carry-overs common in Persian
# tech writing. A term on this list proves nothing about topical relatedness, so
# it is dropped before any overlap is computed.
PERSIAN_STOPWORDS = frozenset({
    "و", "در", "به", "از", "که", "این", "را", "با", "است", "برای", "آن", "یک",
    "می", "بر", "خود", "تا", "کرد", "بود", "شود", "شده", "هم", "اما", "یا",
    "اگر", "همه", "هر", "بین", "دو", "چه", "باید", "نیز", "دیگر", "کند",
    "کنید", "کنیم", "دارد", "دارند", "داشت", "ندارد", "بیشتر", "کمتر", "بسیار",
    "روی", "زیر", "پس", "پیش", "کل", "طور", "مانند", "مثل", "چون", "وقتی",
    "حال", "بعد", "قبل", "نه", "بله", "آیا", "کجا", "چرا", "چگونه", "چطور",
    "کدام", "کسی", "چیزی", "همین", "همان", "این‌که", "آنکه", "شما", "ما",
    "او", "آنها", "ایشان", "من", "تو", "های", "ها", "تر", "ترین", "ای",
    "شد", "بشود", "گفت", "گویا", "یعنی", "البته", "ولی", "لذا", "بنابراین",
    "سپس", "هنوز", "دوباره", "خیلی", "چند", "اول", "آخر", "جدید", "قدیم",
    "مورد", "موارد", "نوع", "انواع", "بخش", "قسمت", "صورت", "عنوان", "دلیل",
    "the", "and", "for", "with", "this", "that", "from", "you", "are", "was",
    "has", "have", "not", "but", "can", "will", "your", "all", "about", "how",
    "what", "when", "which", "one", "two", "more", "our", "their", "its",
})

# A token shorter than this is noise in Persian too ("به", "ها" are already
# stopwords; two-letter leftovers carry no topical signal).
MIN_TOKEN_LENGTH = 3

# Terms appearing in more than this share of the corpus are treated as
# site-wide boilerplate. A term present in EVERY article proves nothing about
# the relatedness of any two of them — it is the site's own vocabulary, not a
# topical link. This is the same intuition as IDF, expressed as a hard cut so
# the reason shown to the user stays explainable.
MAX_DOCUMENT_FREQUENCY_RATIO = 0.5

# ------------------------------------------------------------------ score weights
# Documented max is 100. Kept as module constants so the API can expose the
# table and the UI can explain a score without duplicating the numbers.
W_SHARED_TERMS = 40
W_ORPHAN_BOOST = 25
W_ANCHOR_EXACT = 20
W_TITLE_TERM_HIT = 10
W_CORPUS_SCARCITY = 5
MAX_SCORE = (
    W_SHARED_TERMS + W_ORPHAN_BOOST + W_ANCHOR_EXACT + W_TITLE_TERM_HIT
    + W_CORPUS_SCARCITY
)

SCORE_WEIGHTS = {
    "shared_term_weight": W_SHARED_TERMS,
    "orphan_boost": W_ORPHAN_BOOST,
    "anchor_exact_match": W_ANCHOR_EXACT,
    "title_term_hit": W_TITLE_TERM_HIT,
    "corpus_scarcity": W_CORPUS_SCARCITY,
    "max": MAX_SCORE,
}


def normalize_persian(text: str) -> str:
    """Fold a Persian/Arabic string to one canonical comparable form.

    NFKC first so presentation forms and ligatures decompose, then the explicit
    YEH/KAF folds (NFKC does *not* map Arabic YEH to Persian YEH — they are
    distinct letters in Unicode's view, which is exactly why this bites).
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.translate(_FOLD_TABLE)
    return text.casefold().strip()


def tokenize(text: str, *, strip_markdown: bool = True) -> list[str]:
    """Normalised, stopword-free, length-filtered tokens in document order."""
    if not text:
        return []
    if strip_markdown:
        text = _MD_NOISE.sub(" ", text)
    normalized = normalize_persian(text)
    raw = _NON_WORD.split(normalized)
    return [
        t for t in raw
        if len(t) >= MIN_TOKEN_LENGTH and t not in PERSIAN_STOPWORDS
    ]


def _sentences(text: str) -> list[str]:
    """Split into sentence-ish chunks for the context snippet.

    Persian uses "؟" and "،" alongside ASCII punctuation, and markdown adds
    newlines as a de-facto separator.
    """
    if not text:
        return []
    parts = re.split(r"[.!?؟\n]+|۔", text)
    return [p.strip() for p in parts if p.strip()]


def make_fingerprint(source_id: UUID, target_id: UUID, reason: str) -> str:
    """Stable id for a suggestion so a re-run updates instead of duplicating.

    Direction matters: A->B and B->A are genuinely different suggestions, so the
    ids are not sorted. The reason is included because the same pair can be
    suggested for two different, independently-actionable reasons.
    """
    raw = f"{source_id}|{target_id}|{reason}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- corpus helpers

class _ArticleProfile:
    """Pre-computed tokenisation of one article, built once per detector run.

    Tokenising inside the O(n^2) pair loop would re-tokenise every article n
    times; a site with 200 articles would tokenise 40,000 times instead of 200.
    """

    __slots__ = (
        "id", "title", "slug", "published_url", "title_tokens",
        "body_tokens", "token_set", "normalized_title", "normalized_body",
        "sentences",
    )

    def __init__(self, article: ContentArticle):
        self.id = article.id
        self.title = article.title or ""
        self.slug = article.slug or ""
        self.published_url = article.published_url
        self.title_tokens = tokenize(self.title, strip_markdown=False)
        body = article.content_markdown or ""
        self.body_tokens = tokenize(body)
        # Title terms count as body terms too: an article "about" its title.
        self.token_set = set(self.title_tokens) | set(self.body_tokens)
        self.normalized_title = normalize_persian(self.title)
        self.normalized_body = normalize_persian(body)
        self.sentences = _sentences(body)


def _document_frequencies(profiles: list[_ArticleProfile]) -> dict[str, int]:
    """How many articles each term appears in."""
    df: dict[str, int] = {}
    for p in profiles:
        for term in p.token_set:
            df[term] = df.get(term, 0) + 1
    return df


def _term_rarity(term: str, df: dict[str, int], corpus_size: int) -> float:
    """0-1 weight for one shared term. Rare terms count, common ones do not.

    A term in half or more of the corpus scores 0 — see
    MAX_DOCUMENT_FREQUENCY_RATIO. Below that the weight rises linearly as the
    term gets rarer, so a term unique to two articles is worth the most.

    The `document_count <= 2` short-circuit is load-bearing, not an
    optimisation. A shared term appears in at least 2 articles by definition, so
    the ratio test alone requires 2/corpus_size < 0.5 — i.e. more than four
    articles — before ANY shared term can score above zero. Without the
    short-circuit a site with three or four articles gets no keyword_overlap and
    no orphan_target suggestions at all, which is precisely the site that needs
    them most (everything on it is an orphan). A term in exactly two articles is
    also the strongest possible topical bridge *between those two*, so full
    weight is the right answer regardless of corpus size.
    """
    if corpus_size <= 1:
        return 0.0
    document_count = df.get(term, 0)
    if document_count <= 2:
        return 1.0
    frequency = document_count / corpus_size
    if frequency >= MAX_DOCUMENT_FREQUENCY_RATIO:
        return 0.0
    return 1.0 - (frequency / MAX_DOCUMENT_FREQUENCY_RATIO)


def _find_context(source: _ArticleProfile, needle: str) -> str | None:
    """The first sentence in the source that contains `needle`, for the UI."""
    if not needle:
        return None
    target = normalize_persian(needle)
    if not target:
        return None
    for sentence in source.sentences:
        if target in normalize_persian(sentence):
            snippet = sentence.strip()
            return snippet[:400] if len(snippet) > 400 else snippet
    return None


def _context_for_terms(source: _ArticleProfile, terms: list[str]) -> str | None:
    """Best sentence in the source containing the most of `terms`."""
    if not terms:
        return None
    wanted = set(terms)
    best: tuple[int, str] | None = None
    for sentence in source.sentences:
        sentence_terms = set(tokenize(sentence))
        hits = len(wanted & sentence_terms)
        if hits and (best is None or hits > best[0]):
            best = (hits, sentence.strip())
    if not best:
        return None
    snippet = best[1]
    return snippet[:400] if len(snippet) > 400 else snippet


# ----------------------------------------------------------------------- detectors
# Each detector is pure: profiles in, candidate dicts out. No DB access, so the
# scoring stays unit-testable and persistence semantics live in one place.


def _detect_keyword_overlap(
    profiles: list[_ArticleProfile],
    df: dict[str, int],
    inbound_counts: dict[UUID, int],
) -> list[dict]:
    """Meaningful shared terms between two articles, weighted by rarity."""
    corpus_size = len(profiles)
    # Scarcity component: on a 5-article site every internal link is
    # structurally significant; on a 500-article site one more link is noise.
    scarcity = 0.0
    if corpus_size > 0:
        scarcity = max(0.0, 1.0 - (corpus_size / 100.0)) * W_CORPUS_SCARCITY

    out: list[dict] = []
    for source in profiles:
        for target in profiles:
            if source.id == target.id:
                continue  # never suggest a self-link
            shared = source.token_set & target.token_set
            if not shared:
                continue

            # Rank shared terms by rarity and keep the informative ones.
            weighted = sorted(
                ((term, _term_rarity(term, df, corpus_size)) for term in shared),
                key=lambda pair: pair[1],
                reverse=True,
            )
            meaningful = [(t, w) for t, w in weighted if w > 0.0]
            if not meaningful:
                continue

            # Sum of the top 5 rarity weights, normalised. More than five shared
            # rare terms does not make the pair five times more related.
            top = meaningful[:5]
            overlap_strength = min(sum(w for _, w in top) / 5.0, 1.0)
            shared_points = overlap_strength * W_SHARED_TERMS

            target_title_terms = set(target.title_tokens)
            title_hits = [t for t, _ in top if t in target_title_terms]
            title_points = (
                min(len(title_hits) / 2.0, 1.0) * W_TITLE_TERM_HIT
                if title_hits else 0.0
            )

            orphan_points = (
                W_ORPHAN_BOOST if inbound_counts.get(target.id, 0) == 0 else 0.0
            )

            total = shared_points + title_points + orphan_points + scarcity
            terms = [t for t, _ in top]

            # The anchor is the target's own title: it is the most accurate,
            # least spammy description of what the reader will land on.
            out.append({
                "source_id": source.id,
                "target_id": target.id,
                "reason": "keyword_overlap",
                "anchor_text": target.title[:500],
                "context_snippet": _context_for_terms(source, terms),
                "score": total,
                "breakdown": {
                    "shared_term_weight": round(shared_points, 2),
                    "title_term_hit": round(title_points, 2),
                    "orphan_boost": round(orphan_points, 2),
                    "corpus_scarcity": round(scarcity, 2),
                    "shared_terms": terms,
                    "shared_term_count": len(meaningful),
                    "target_inbound_links": inbound_counts.get(target.id, 0),
                    "corpus_size": corpus_size,
                    "max_possible": MAX_SCORE,
                },
            })
    return out


def _detect_orphan_targets(
    profiles: list[_ArticleProfile],
    df: dict[str, int],
    inbound_counts: dict[UUID, int],
) -> list[dict]:
    """Articles nothing links to yet, matched to their most plausible source.

    Orphans are the highest-value fix in internal linking: an article with no
    inbound links is nearly invisible to crawlers regardless of its quality, so
    the boost is deliberately large and this detector emits a distinct reason
    (rather than relying on the boost inside keyword_overlap) so the UI can
    surface "these are your orphans" as its own callout.
    """
    corpus_size = len(profiles)
    orphans = [p for p in profiles if inbound_counts.get(p.id, 0) == 0]
    if not orphans:
        return []

    out: list[dict] = []
    for target in orphans:
        # Pick the single best source rather than every article: an orphan needs
        # one good inbound link, not twenty weak ones.
        best: tuple[float, _ArticleProfile, list[str]] | None = None
        for source in profiles:
            if source.id == target.id:
                continue
            shared = source.token_set & target.token_set
            if not shared:
                continue
            weighted = sorted(
                ((term, _term_rarity(term, df, corpus_size)) for term in shared),
                key=lambda pair: pair[1],
                reverse=True,
            )
            meaningful = [(t, w) for t, w in weighted if w > 0.0][:5]
            if not meaningful:
                continue
            strength = min(sum(w for _, w in meaningful) / 5.0, 1.0)
            if best is None or strength > best[0]:
                best = (strength, source, [t for t, _ in meaningful])

        if best is None:
            continue
        strength, source, terms = best
        shared_points = strength * W_SHARED_TERMS
        total = shared_points + W_ORPHAN_BOOST

        out.append({
            "source_id": source.id,
            "target_id": target.id,
            "reason": "orphan_target",
            "anchor_text": target.title[:500],
            "context_snippet": _context_for_terms(source, terms),
            "score": total,
            "breakdown": {
                "shared_term_weight": round(shared_points, 2),
                "orphan_boost": W_ORPHAN_BOOST,
                "shared_terms": terms,
                "target_inbound_links": 0,
                "corpus_size": corpus_size,
                "max_possible": MAX_SCORE,
                "note": "target has no inbound internal links",
            },
        })
    return out


def _detect_anchor_opportunities(
    profiles: list[_ArticleProfile],
    inbound_counts: dict[UUID, int],
) -> list[dict]:
    """The target's exact title already appears in the source, unlinked.

    This is the strongest signal in the whole module: the author already wrote
    the phrase, so the link needs no new copy and reads naturally. Only the
    normalised *text* is checked — whether it is already a link is settled by
    the existing-pair filter in detect_link_suggestions, not by parsing HTML.
    """
    corpus_size = len(profiles)
    out: list[dict] = []
    for target in profiles:
        needle = target.normalized_title
        # Very short titles ("خانه") match accidentally inside other words.
        if len(needle) < 8:
            continue
        for source in profiles:
            if source.id == target.id:
                continue
            if needle not in source.normalized_body:
                continue

            orphan_points = (
                W_ORPHAN_BOOST if inbound_counts.get(target.id, 0) == 0 else 0.0
            )
            # Exact phrase match implies the terms are present, so the shared
            # component is awarded in full rather than recomputed.
            total = W_ANCHOR_EXACT + W_SHARED_TERMS + orphan_points

            out.append({
                "source_id": source.id,
                "target_id": target.id,
                "reason": "anchor_opportunity",
                "anchor_text": target.title[:500],
                "context_snippet": _find_context(source, target.title),
                "score": total,
                "breakdown": {
                    "anchor_exact_match": W_ANCHOR_EXACT,
                    "shared_term_weight": W_SHARED_TERMS,
                    "orphan_boost": round(orphan_points, 2),
                    "matched_phrase": target.title[:200],
                    "target_inbound_links": inbound_counts.get(target.id, 0),
                    "corpus_size": corpus_size,
                    "max_possible": MAX_SCORE,
                },
            })
    return out


# --------------------------------------------------------------------- persistence

async def _load_articles(db: AsyncSession, website_id: UUID) -> list[ContentArticle]:
    """One explicit select, never a lazy relationship.

    Touching `website.articles` under asyncio raises MissingGreenlet — lazy
    loading needs a sync context that does not exist here. Soft-deleted
    articles are excluded: they are ghosts and must not produce suggestions.
    """
    result = await db.execute(
        select(ContentArticle).where(
            ContentArticle.website_id == website_id,
            ContentArticle.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def _purge_suggestions_of_deleted_articles(
    db: AsyncSession, website_id: UUID
) -> int:
    """Hard-delete suggestions whose source or target article is soft-deleted.

    Suggestions are derived, disposable data — once one of the two articles is
    gone the suggestion is meaningless, and keeping it meant the list showed
    links to articles that no longer exist ("اشباح"). Raw SQL: one round trip,
    no ORM bulk-delete subquery quirks.
    """
    stmt = text(
        """
        DELETE FROM internal_links
        WHERE website_id = :wid
          AND (
            source_article_id IN (
              SELECT id FROM content_articles
              WHERE website_id = :wid AND deleted_at IS NOT NULL
            )
            OR target_article_id IN (
              SELECT id FROM content_articles
              WHERE website_id = :wid AND deleted_at IS NOT NULL
            )
          )
        """
    )
    await db.execute(stmt, {"wid": str(website_id)})

    stmt = text(
        """
        DELETE FROM internal_link_suggestions
        WHERE website_id = :wid
          AND (
            source_article_id IN (
              SELECT id FROM content_articles
              WHERE website_id = :wid AND deleted_at IS NOT NULL
            )
            OR target_article_id IN (
              SELECT id FROM content_articles
              WHERE website_id = :wid AND deleted_at IS NOT NULL
            )
          )
        """
    )
    result = await db.execute(stmt, {"wid": str(website_id)})
    return result.rowcount or 0


async def _existing_link_pairs(
    db: AsyncSession, website_id: UUID
) -> tuple[set[tuple[UUID, UUID]], dict[UUID, int]]:
    """Already-linked (source, target) pairs and inbound counts per target.

    Only active links count: a deactivated link is a link that was removed, and
    the detector should be free to suggest it again.
    """
    result = await db.execute(
        select(InternalLink.source_article_id, InternalLink.target_article_id).where(
            InternalLink.website_id == website_id,
            InternalLink.is_active.is_(True),
        )
    )
    pairs: set[tuple[UUID, UUID]] = set()
    inbound: dict[UUID, int] = {}
    for source_id, target_id in result.all():
        pairs.add((source_id, target_id))
        inbound[target_id] = inbound.get(target_id, 0) + 1
    return pairs, inbound


async def detect_link_suggestions(
    db: AsyncSession,
    website_id: UUID,
    *,
    min_relevance: int = 30,
    max_per_article: int = 5,
) -> dict:
    """Run every detector for one website and upsert the suggestions.

    Returns counts, not rows: callers report progress and read results back
    through list_suggestions.
    """
    website = await db.get(Website, website_id)
    if not website:
        return {
            "website_id": website_id,
            "scanned_articles": 0,
            "created": 0,
            "updated": 0,
            "expired": 0,
            "orphan_article_count": 0,
            "purged_ghost_suggestions": 0,
            "by_reason": {},
        }

    # Suggestions pointing at soft-deleted articles are garbage — purge them
    # first so «بروزرسانی» visibly cleans the list instead of showing ghosts.
    purged = await _purge_suggestions_of_deleted_articles(db, website_id)

    articles = await _load_articles(db, website_id)
    existing_pairs, inbound_counts = await _existing_link_pairs(db, website_id)

    # One article cannot link to anything; two is the minimum for a pair.
    if len(articles) < 2:
        await db.flush()
        return {
            "website_id": website_id,
            "scanned_articles": len(articles),
            "created": 0,
            "updated": 0,
            "expired": 0,
            "orphan_article_count": len(articles),
            "purged_ghost_suggestions": purged,
            "by_reason": {},
        }

    profiles = [_ArticleProfile(a) for a in articles]
    df = _document_frequencies(profiles)
    orphan_count = sum(1 for p in profiles if inbound_counts.get(p.id, 0) == 0)

    candidates: list[dict] = []
    candidates += _detect_anchor_opportunities(profiles, inbound_counts)
    candidates += _detect_orphan_targets(profiles, df, inbound_counts)
    candidates += _detect_keyword_overlap(profiles, df, inbound_counts)

    # Strongest first, so the dedup passes below keep the best variant of any
    # pair and the per-source cap keeps the most useful suggestions.
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # ------------------------------------------------------------- filtering
    filtered: list[dict] = []
    per_source: dict[UUID, int] = {}
    # Tracks (unordered pair, reason) so the reverse of an already-accepted
    # candidate with the same reason is dropped: "A relates to B" and "B relates
    # to A" for keyword_overlap are one insight, and offering both doubles the
    # review work for no extra information. anchor_opportunity is exempt because
    # a literal phrase match is genuinely directional evidence.
    seen_undirected: set[tuple[frozenset, str]] = set()
    seen_fingerprints: set[str] = set()

    for cand in candidates:
        score = int(max(0, min(MAX_SCORE, round(cand["score"]))))
        if score < min_relevance:
            continue

        source_id = cand["source_id"]
        target_id = cand["target_id"]
        reason = cand["reason"]

        # A link that already exists needs no suggestion.
        if (source_id, target_id) in existing_pairs:
            continue

        if reason != "anchor_opportunity":
            undirected_key = (frozenset((source_id, target_id)), reason)
            if undirected_key in seen_undirected:
                continue
            seen_undirected.add(undirected_key)

        fingerprint = make_fingerprint(source_id, target_id, reason)
        if fingerprint in seen_fingerprints:
            continue

        # Cap per source article, best first, so one hub article does not
        # produce fifty suggestions and drown everything else.
        if per_source.get(source_id, 0) >= max_per_article:
            continue

        seen_fingerprints.add(fingerprint)
        per_source[source_id] = per_source.get(source_id, 0) + 1
        cand["fingerprint"] = fingerprint
        cand["final_score"] = score
        filtered.append(cand)

    # ------------------------------------------------------------- upserting
    now = datetime.now(timezone.utc)
    created = updated = 0
    by_reason: dict[str, int] = {}

    for cand in filtered:
        result = await db.execute(
            select(InternalLinkSuggestion).where(
                InternalLinkSuggestion.website_id == website_id,
                InternalLinkSuggestion.fingerprint == cand["fingerprint"],
            )
        )
        row = result.scalar_one_or_none()

        if row:
            row.anchor_text = cand["anchor_text"]
            row.context_snippet = cand["context_snippet"]
            row.relevance_score = cand["final_score"]
            row.score_breakdown = cand["breakdown"]
            row.last_seen_at = now
            # A human decision is final. Only a finding that had expired and is
            # now reproducing goes back to "suggested".
            if row.status == "expired":
                row.status = "suggested"
            updated += 1
        else:
            db.add(InternalLinkSuggestion(
                organization_id=website.organization_id,
                website_id=website_id,
                source_article_id=cand["source_id"],
                target_article_id=cand["target_id"],
                anchor_text=cand["anchor_text"],
                context_snippet=cand["context_snippet"],
                relevance_score=cand["final_score"],
                score_breakdown=cand["breakdown"],
                status="suggested",
                reason=cand["reason"],
                fingerprint=cand["fingerprint"],
                detected_at=now,
                last_seen_at=now,
            ))
            created += 1

        by_reason[cand["reason"]] = by_reason.get(cand["reason"], 0) + 1

    # Anything still merely "suggested" that this run did not reproduce is no
    # longer true — the articles changed, or a link was added by hand. Marked
    # expired rather than deleted so the audit trail survives. Decided rows
    # (accepted/rejected/applied) are never touched.
    expired = 0
    stmt = (
        update(InternalLinkSuggestion)
        .where(
            InternalLinkSuggestion.website_id == website_id,
            InternalLinkSuggestion.status == "suggested",
            # notin_ of an empty set matches everything, which is correct here:
            # a run that found nothing should expire every stale suggestion. The
            # {""} fallback keeps the generated SQL valid.
            InternalLinkSuggestion.fingerprint.notin_(seen_fingerprints or {""}),
        )
        .values(status="expired", last_seen_at=now)
    )
    result = await db.execute(stmt)
    expired = result.rowcount or 0

    await db.flush()

    return {
        "website_id": website_id,
        "scanned_articles": len(articles),
        "created": created,
        "updated": updated,
        "expired": expired,
        "orphan_article_count": orphan_count,
        "purged_ghost_suggestions": purged,
        "by_reason": by_reason,
    }


async def list_suggestions(
    db: AsyncSession,
    website_id: UUID,
    *,
    status: str | None = None,
    reason: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InternalLinkSuggestion]:
    """Suggestions for one website, highest relevance first."""
    stmt = select(InternalLinkSuggestion).where(
        InternalLinkSuggestion.website_id == website_id
    )
    if status:
        stmt = stmt.where(InternalLinkSuggestion.status == status)
    if reason:
        stmt = stmt.where(InternalLinkSuggestion.reason == reason)
    stmt = (
        stmt.order_by(
            InternalLinkSuggestion.relevance_score.desc(),
            InternalLinkSuggestion.detected_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_suggestion_summary(db: AsyncSession, website_id: UUID) -> dict:
    """Counts and averages for the page header, in as few round trips as possible."""
    by_reason_result = await db.execute(
        select(InternalLinkSuggestion.reason, func.count())
        .where(
            InternalLinkSuggestion.website_id == website_id,
            InternalLinkSuggestion.status == "suggested",
        )
        .group_by(InternalLinkSuggestion.reason)
    )
    by_reason = {row[0]: row[1] for row in by_reason_result.all()}

    by_status_result = await db.execute(
        select(InternalLinkSuggestion.status, func.count())
        .where(InternalLinkSuggestion.website_id == website_id)
        .group_by(InternalLinkSuggestion.status)
    )
    by_status = {row[0]: row[1] for row in by_status_result.all()}

    avg_result = await db.execute(
        select(func.coalesce(func.avg(InternalLinkSuggestion.relevance_score), 0)).where(
            InternalLinkSuggestion.website_id == website_id,
            InternalLinkSuggestion.status == "suggested",
        )
    )
    avg_relevance = float(avg_result.scalar_one() or 0.0)

    # Orphans are counted from live data, not from the suggestion rows: an
    # article can stop being an orphan the moment a link is accepted, and the
    # callout must reflect that immediately. Soft-deleted articles are ghosts —
    # counting them made the callout claim 19 orphans on a site with zero
    # articles.
    total_articles_result = await db.execute(
        select(func.count())
        .select_from(ContentArticle)
        .where(
            ContentArticle.website_id == website_id,
            ContentArticle.deleted_at.is_(None),
        )
    )
    total_articles = int(total_articles_result.scalar_one() or 0)

    # Which articles currently have at least one active inbound link. Selected
    # as a plain id list rather than a correlated NOT EXISTS so the orphan rows
    # below can be filtered in one further query.
    linked_result = await db.execute(
        select(func.distinct(InternalLink.target_article_id)).where(
            InternalLink.website_id == website_id,
            InternalLink.is_active.is_(True),
        )
    )
    linked_ids = {row[0] for row in linked_result.all()}

    orphan_stmt = select(ContentArticle).where(
        ContentArticle.website_id == website_id,
        ContentArticle.deleted_at.is_(None),
    )
    if linked_ids:
        orphan_stmt = orphan_stmt.where(ContentArticle.id.notin_(linked_ids))
    # Capped: a site that has never run the detector has every article orphaned,
    # and the callout only needs enough rows to be actionable.
    orphan_stmt = orphan_stmt.order_by(ContentArticle.created_at.desc()).limit(20)
    orphan_result = await db.execute(orphan_stmt)
    orphan_rows = list(orphan_result.scalars().all())

    active_links_result = await db.execute(
        select(func.count())
        .select_from(InternalLink)
        .where(
            InternalLink.website_id == website_id,
            InternalLink.is_active.is_(True),
        )
    )

    return {
        "total_suggested": sum(by_reason.values()),
        "by_reason": by_reason,
        "by_status": by_status,
        "orphan_article_count": max(total_articles - len(linked_ids), 0),
        "avg_relevance": round(avg_relevance, 1),
        "orphan_articles": [
            {
                "article_id": a.id,
                "title": a.title,
                "slug": a.slug,
                "published_url": a.published_url,
                "status": a.status,
            }
            for a in orphan_rows
        ],
        "total_articles": total_articles,
        "active_link_count": int(active_links_result.scalar_one() or 0),
    }


async def get_suggestion_in_org(
    db: AsyncSession, suggestion_id: UUID, organization_id: UUID
) -> InternalLinkSuggestion:
    """Fetch a suggestion, scoped by an explicit organization filter.

    Raises NotFoundError (404) on a cross-tenant hit rather than 403, so a UUID
    cannot be used as an existence oracle.
    """
    result = await db.execute(
        select(InternalLinkSuggestion).where(
            InternalLinkSuggestion.id == suggestion_id,
            InternalLinkSuggestion.organization_id == organization_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise NotFoundError("InternalLinkSuggestion", str(suggestion_id))
    return suggestion


async def get_link_in_org(
    db: AsyncSession, link_id: UUID, organization_id: UUID
) -> InternalLink:
    """Fetch a link, scoped by an explicit organization filter. 404 on mismatch."""
    result = await db.execute(
        select(InternalLink).where(
            InternalLink.id == link_id,
            InternalLink.organization_id == organization_id,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise NotFoundError("InternalLink", str(link_id))
    return link


async def _target_url(db: AsyncSession, target_article_id: UUID) -> str | None:
    """The published URL of the target, if it has one.

    Explicit select rather than a relationship walk: same MissingGreenlet
    reason as _load_articles.
    """
    result = await db.execute(
        select(ContentArticle.published_url).where(
            ContentArticle.id == target_article_id
        )
    )
    row = result.first()
    return row[0] if row else None


async def decide_suggestion(
    db: AsyncSession,
    suggestion: InternalLinkSuggestion,
    new_status: str,
    *,
    user_id: UUID | None = None,
) -> InternalLinkSuggestion:
    """Accept or reject a suggestion, stamping who and when.

    Accepting also records the link in `internal_links` and moves the suggestion
    to "applied", because from the user's point of view accepting *is* applying:
    there is no separate publish step in this module.
    """
    now = datetime.now(timezone.utc)

    if new_status == "rejected":
        suggestion.status = "rejected"
        suggestion.decided_at = now
        suggestion.decided_by = user_id
        await db.flush()
        await db.refresh(suggestion)
        return suggestion

    if new_status in ("accepted", "applied"):
        # Idempotent by intent: check for the existing row first. The unique
        # index on (source, target, anchor) is a backstop against a race, not
        # the plan — relying on it would abort the whole transaction.
        result = await db.execute(
            select(InternalLink).where(
                InternalLink.source_article_id == suggestion.source_article_id,
                InternalLink.target_article_id == suggestion.target_article_id,
                InternalLink.anchor_text == suggestion.anchor_text,
            )
        )
        link = result.scalar_one_or_none()

        if link:
            # Re-accepting a previously removed link reactivates it rather than
            # inserting a duplicate.
            link.is_active = True
            link.last_verified_at = now
            if link.suggestion_id is None:
                link.suggestion_id = suggestion.id
        else:
            db.add(InternalLink(
                organization_id=suggestion.organization_id,
                website_id=suggestion.website_id,
                source_article_id=suggestion.source_article_id,
                target_article_id=suggestion.target_article_id,
                anchor_text=suggestion.anchor_text,
                target_url=await _target_url(db, suggestion.target_article_id),
                is_active=True,
                suggestion_id=suggestion.id,
                first_seen_at=now,
                last_verified_at=now,
            ))

        suggestion.status = "applied"
        suggestion.decided_at = now
        suggestion.decided_by = user_id
        suggestion.applied_at = now
        await db.flush()
        await db.refresh(suggestion)
        return suggestion

    # Any other target status is a plain lifecycle write (e.g. back to
    # "suggested" after a mistaken rejection).
    suggestion.status = new_status
    suggestion.decided_at = now
    suggestion.decided_by = user_id
    await db.flush()
    await db.refresh(suggestion)
    return suggestion


async def delete_suggestion(
    db: AsyncSession,
    suggestion: InternalLinkSuggestion,
) -> dict:
    """Hard-delete one suggestion, whatever its status.

    Suggestions are derived data: a user clearing a rejected/expired row wants
    it gone from the list, not archived. An applied suggestion owns an
    InternalLink row (FK), so that link is removed first. The detector may
    re-create the suggestion later if the articles still reproduce the signal —
    that is correct behaviour.
    """
    await db.execute(
        delete(InternalLink).where(InternalLink.suggestion_id == suggestion.id)
    )
    await db.delete(suggestion)
    await db.flush()
    return {"deleted": True, "id": str(suggestion.id)}


async def bulk_decide_suggestions(
    db: AsyncSession,
    website_id: UUID,
    org_id: UUID,
    suggestion_ids: list[UUID],
    action: str,
    *,
    user_id: UUID | None = None,
) -> dict:
    """Apply reject/delete to many suggestions in one call.

    Every id is re-verified against the org through its website before the
    action runs, so a forged id from another tenant is silently skipped rather
    than leaked. Unknown ids are counted as skipped, not errors — bulk UIs
    delete rows the user is looking at while the backend re-checks each one.
    """
    if action not in ("reject", "delete"):
        raise AppException(
            status_code=422,
            detail="action باید reject یا delete باشد.",
            error_type="invalid_bulk_action",
        )

    applied = skipped = 0
    now = datetime.now(timezone.utc)
    for sid in suggestion_ids:
        result = await db.execute(
            select(InternalLinkSuggestion)
            .join(Website, Website.id == InternalLinkSuggestion.website_id)
            .where(
                InternalLinkSuggestion.id == sid,
                InternalLinkSuggestion.website_id == website_id,
                Website.organization_id == org_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            skipped += 1
            continue
        if action == "delete":
            await db.execute(
                delete(InternalLink).where(InternalLink.suggestion_id == row.id)
            )
            await db.delete(row)
        else:
            row.status = "rejected"
            row.decided_at = now
            row.decided_by = user_id
        applied += 1

    await db.flush()
    return {"applied": applied, "skipped": skipped, "action": action}


async def list_links(
    db: AsyncSession,
    website_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[InternalLink]:
    """Applied internal links for one website, newest first."""
    stmt = (
        select(InternalLink)
        .where(InternalLink.website_id == website_id)
        .order_by(InternalLink.first_seen_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def deactivate_link(
    db: AsyncSession,
    link: InternalLink,
    *,
    user_id: UUID | None = None,
) -> InternalLink:
    """Soft-remove a link.

    The row is kept and flagged inactive rather than deleted: the detector reads
    active links to decide what is already linked, and a hard delete would make
    it re-suggest a pair a user deliberately removed with no record of why. An
    inactive row is instead free to be suggested again, which is the intended
    behaviour after a manual removal.
    """
    link.is_active = False
    link.last_verified_at = datetime.now(timezone.utc)

    # If the link came from a suggestion, that suggestion is no longer applied.
    if link.suggestion_id is not None:
        result = await db.execute(
            select(InternalLinkSuggestion).where(
                InternalLinkSuggestion.id == link.suggestion_id
            )
        )
        suggestion = result.scalar_one_or_none()
        if suggestion is not None and suggestion.status == "applied":
            suggestion.status = "rejected"
            suggestion.decided_at = datetime.now(timezone.utc)
            suggestion.decided_by = user_id
            suggestion.applied_at = None

    await db.flush()
    await db.refresh(link)
    return link


__all__ = [
    "detect_link_suggestions",
    "list_suggestions",
    "get_suggestion_summary",
    "decide_suggestion",
    "list_links",
    "deactivate_link",
    "get_suggestion_in_org",
    "get_link_in_org",
    "make_fingerprint",
    "normalize_persian",
    "tokenize",
    "PERSIAN_STOPWORDS",
    "SCORE_WEIGHTS",
    "MAX_SCORE",
]
