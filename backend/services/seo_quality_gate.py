"""SEO Quality Gate - deterministic accuracy checks before anything is published.

Every piece of content must score >= SEO_PASS_THRESHOLD (80) or it is rejected
and regenerated. Checks:
  1. Title length < 60 chars
  2. Meta description < 160 chars (and > 50)
  3. Keyword density between 1-2%
  4. At least MIN_INTERNAL_LINKS internal links present in HTML
  5. Elementor-safe HTML: only whitelisted tags/attributes
  6. Fact grounding: key claims/terms must be supported by knowledge_base
"""

import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("backend.services.seo_quality_gate")

SEO_PASS_THRESHOLD = 80.0
MIN_INTERNAL_LINKS = 3

ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "em", "b", "i",
    "a", "img", "blockquote", "table", "thead", "tbody", "tr", "th", "td",
    "figure", "figcaption", "br", "hr", "span",
}
FORBIDDEN_PATTERNS = [
    r"<script",
    r"<style",
    r"<iframe",
    r"<object",
    r"<embed",
    r"<form",
    r"javascript:",
    r"onclick=",
    r"onload=",
    r"onerror=",
]


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def _count_words(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def _keyword_density(html: str, keyword: str) -> float:
    text = _strip_tags(html).lower()
    words = [w for w in text.split() if w.strip()]
    if not words or not keyword:
        return 0.0
    kw = keyword.lower().strip()
    kw_word_count = max(1, len(kw.split()))
    count = text.count(kw)
    return round((count * kw_word_count / len(words)) * 100, 2)


def _count_internal_links(html: str) -> int:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    internal = 0
    for href in hrefs:
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        if href.startswith("/") or "://" not in href:
            internal += 1
        # relative and same-site links both count; external links do not
    return len(hrefs) - sum(
        1 for h in hrefs if h.startswith("http") and "://" in h
    )


def check_elementor_safe(html: str) -> Dict[str, Any]:
    issues = []
    lower = html.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, lower):
            issues.append(f"Forbidden element/pattern detected: {pattern}")
    for tag in re.findall(r"<\s*([a-zA-Z0-9!-]+)", html):
        t = tag.lower().lstrip("/")
        if t == "!doctype":
            continue
        if t not in ALLOWED_TAGS:
            issues.append(f"Non-whitelisted tag <{t}>")
    return {"ok": len(issues) == 0, "issues": list(set(issues))}


async def check_grounding(
    website_id: str,
    title: str,
    html: str,
    min_supported_ratio: float = 0.5,
) -> Dict[str, Any]:
    """Verify the article's core topic/claims trace back to knowledge_base.

    Strategy: recall KB facts related to the title + section headings via the
    match_knowledge vector RPC. If KB has entries, at least `min_supported_ratio`
    of headings must be semantically supported by some fact (similarity above
    threshold OR meaningful token overlap). If KB is empty, grounding passes
    with a warning (nothing to contradict), so first-run sites are not blocked.
    """
    from ..database import get_supabase, get_embedding, NIMEmbeddingError

    supabase = get_supabase()
    try:
        total = (
            supabase.table("knowledge_base")
            .select("id", count="exact")
            .eq("website_id", website_id)
            .execute()
        )
        kb_count = getattr(total, "count", None) or len(total.data or [])
    except Exception as e:
        logger.warning(f"Grounding: could not count knowledge_base: {e}")
        kb_count = 0

    if kb_count == 0:
        return {
            "grounded": True,
            "kb_count": 0,
            "supported": 0,
            "checked": 0,
            "unsupported": [],
            "note": "knowledge_base empty for site - grounding waived",
        }

    # Extract claims: H2/H3 headings + title
    headings = [title]
    headings += [
        m.strip() for m in re.findall(r"<h[23][^>]*>(.*?)</h[23]>", html, flags=re.IGNORECASE | re.DOTALL)
    ]
    headings = [_strip_tags(h) for h in headings if _strip_tags(h)]
    if not headings:
        headings = [_strip_tags(title)]

    supported = 0
    unsupported = []

    # Fetch a sample of KB facts once for lexical overlap fallback
    try:
        kb_facts = (
            supabase.table("knowledge_base")
            .select("content")
            .eq("website_id", website_id)
            .limit(200)
            .execute()
            .data
            or []
        )
        kb_blob = " ".join((f.get("content") or "") for f in kb_facts).lower()
    except Exception:
        kb_blob = ""

    def _lexical_support(text: str) -> bool:
        tokens = [t for t in re.findall(r"[a-z0-9]{4,}", text.lower())][:12]
        if not tokens:
            return False
        hits = sum(1 for t in tokens if t in kb_blob)
        return hits / len(tokens) >= 0.35

    for claim in headings[:8]:
        vec_ok = False
        try:
            emb = await get_embedding(claim)
            res = (
                supabase.rpc(
                    "match_knowledge",
                    {
                        "query_embedding": emb,
                        "p_website_id": website_id,
                        "match_threshold": 0.55,
                        "match_count": 1,
                    },
                )
                .execute()
                .data
                or []
            )
            vec_ok = len(res) > 0
        except NIMEmbeddingError:
            vec_ok = False
        except Exception as e:
            logger.debug(f"Grounding vector check failed for '{claim[:40]}': {e}")

        lex_ok = _lexical_support(claim)
        if vec_ok or lex_ok:
            supported += 1
        else:
            unsupported.append(claim)

    checked = len(headings[:8])
    ratio = supported / checked if checked else 1.0
    return {
        "grounded": ratio >= min_supported_ratio,
        "kb_count": kb_count,
        "supported": supported,
        "checked": checked,
        "ratio": round(ratio, 2),
        "unsupported": unsupported[:5],
    }


async def validate_content(
    website_id: str,
    title: str,
    meta_description: str,
    keyword: str,
    html: str,
) -> Dict[str, Any]:
    """Run all checks and produce a 0-100 score with actionable issues."""
    issues: List[str] = []
    score = 100.0

    clean_title = _strip_tags(title or "")
    if not clean_title:
        score -= 25
        issues.append("Title is missing")
    elif len(clean_title) >= 60:
        score -= 10
        issues.append(f"Title too long ({len(clean_title)} chars, must be <60)")

    meta = _strip_tags(meta_description or "")
    if not meta:
        score -= 15
        issues.append("Meta description is missing")
    else:
        if len(meta) >= 160:
            score -= 8
            issues.append(f"Meta description too long ({len(meta)} chars, must be <160)")
        if len(meta) < 50:
            score -= 5
            issues.append(f"Meta description too short ({len(meta)} chars, need >=50)")

    density = _keyword_density(html, keyword)
    if keyword:
        if density < 1.0:
            score -= 10
            issues.append(f"Keyword density too low ({density}%, target 1-2%)")
        elif density > 2.0:
            score -= 10
            issues.append(f"Keyword density too high ({density}%, target 1-2%) - risk of stuffing")

    links = _count_internal_links(html)
    if links < MIN_INTERNAL_LINKS:
        score -= 10
        issues.append(f"Only {links} internal links (need >={MIN_INTERNAL_LINKS})")

    elementor = check_elementor_safe(html)
    if not elementor["ok"]:
        score -= 15
        issues.extend(elementor["issues"][:5])

    word_count = _count_words(_strip_tags(html))
    if word_count < 600:
        score -= 10
        issues.append(f"Content thin ({word_count} words, target >=600)")

    grounding = await check_grounding(website_id, clean_title, html)
    if not grounding["grounded"]:
        score -= 20
        issues.append(
            "Fact-grounding failed: sections not supported by knowledge_base: "
            + "; ".join(grounding.get("unsupported", [])[:3])
        )

    score = max(0.0, round(score, 1))
    result = {
        "score": score,
        "passed": score >= SEO_PASS_THRESHOLD,
        "threshold": SEO_PASS_THRESHOLD,
        "issues": issues,
        "metrics": {
            "title_length": len(clean_title),
            "meta_length": len(meta),
            "keyword_density": density,
            "internal_links": links,
            "word_count": word_count,
            "elementor_safe": elementor["ok"],
            "grounded": grounding["grounded"],
            "kb_count": grounding["kb_count"],
        },
    }
    logger.info(
        f"[QualityGate] website={website_id} score={score} passed={result['passed']} "
        f"issues={len(issues)}"
    )
    return result
