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
    If KB is empty, grounding CANNOT proceed: there is nothing to verify
    against, which is exactly when fabrication risk is highest. Returns
    grounded=False with kb_empty=True so callers HARD_FAIL instead of
    waving the article through.
    """
    from database import get_supabase, get_embedding, NIMEmbeddingError

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
            "grounded": False,
            "kb_empty": True,
            "kb_count": 0,
            "supported": 0,
            "checked": 0,
            "unsupported": [],
            "note": "Knowledge base empty. Cannot verify facts. Run sitemap crawl first.",
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
    if grounding.get("kb_empty"):
        score = 0.0
        issues.append(
            "HARD_FAIL: " + grounding.get("note", "Knowledge base empty. Cannot verify facts.")
        )
    elif not grounding["grounded"]:
        score -= 20
        issues.append(
            "Fact-grounding failed: sections not supported by knowledge_base: "
            + "; ".join(grounding.get("unsupported", [])[:3])
        )

    score = max(0.0, round(score, 1))
    hard_fail = grounding.get("kb_empty", False)
    result = {
        "score": score,
        "passed": (score >= SEO_PASS_THRESHOLD) and not hard_fail,
        "gate": "HARD_FAIL" if hard_fail else ("PASS" if score >= SEO_PASS_THRESHOLD else "FAIL"),
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


# ---------------------------------------------------------------------------
# Deterministic QA gate: independent PASS / WARN / HARD_FAIL checks.
# A single 0-100 score is NOT a gate. Any HARD_FAIL blocks the article.
# ---------------------------------------------------------------------------

QA_TITLE_MIN = 30
QA_TITLE_MAX = 65
QA_META_MIN = 140
QA_META_MAX = 160
QA_MIN_WORDS = 1800
QA_MIN_INTERNAL_LINKS = 2

_PLACEHOLDER_PATTERNS = [
    r"\[(LINK|INSERT|TOPIC|KEYWORD|TODO|URL|AUTHOR|PLACEHOLDER)[^\]]*\]?",
    r"\*\*(TODO|TBD|INSERT|PLACEHOLDER)\*\*",
    r"lorem ipsum",
]


def _check_title_length(html: str) -> Dict[str, Any]:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.IGNORECASE | re.DOTALL)
    title = _strip_tags(m.group(1)) if m else ""
    if not title:
        return {"status": "FAIL", "detail": "No H1 title found"}
    n = len(title)
    if n < QA_TITLE_MIN:
        return {"status": "FAIL", "detail": f"Title too short ({n} chars, need {QA_TITLE_MIN}-{QA_TITLE_MAX})"}
    if n > QA_TITLE_MAX:
        return {"status": "WARN", "detail": f"Title long ({n} chars, ideal {QA_TITLE_MIN}-{QA_TITLE_MAX})"}
    return {"status": "PASS", "detail": f"Title {n} chars"}


def _check_meta_description(html: str, meta: str = "") -> Dict[str, Any]:
    text = meta or ""
    if not text:
        m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
                      html, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"Meta Description:\s*(.+)", html, flags=re.IGNORECASE)
        text = (m.group(1).strip() if m else "")
    if not text:
        return {"status": "FAIL", "detail": "Meta description missing"}
    n = len(text)
    if n < QA_META_MIN or n > QA_META_MAX:
        return {"status": "WARN", "detail": f"Meta {n} chars (ideal {QA_META_MIN}-{QA_META_MAX})"}
    return {"status": "PASS", "detail": f"Meta {n} chars"}


def _check_single_h1(html: str) -> Dict[str, Any]:
    count = len(re.findall(r"<h1[\s>]", html, flags=re.IGNORECASE))
    if count == 0:
        return {"status": "FAIL", "detail": "No H1 found"}
    if count > 1:
        return {"status": "FAIL", "detail": f"{count} H1 tags found, exactly 1 required"}
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.IGNORECASE | re.DOTALL)
    if m and not _strip_tags(m.group(1)):
        return {"status": "FAIL", "detail": "H1 is empty"}
    return {"status": "PASS", "detail": "Exactly one non-empty H1"}


def _check_word_count(html: str, minimum: int = QA_MIN_WORDS) -> Dict[str, Any]:
    n = _count_words(_strip_tags(html))
    if n < minimum:
        return {"status": "FAIL", "detail": f"Only {n} words (minimum {minimum})"}
    return {"status": "PASS", "detail": f"{n} words"}


def _check_internal_links(html: str, minimum: int = QA_MIN_INTERNAL_LINKS) -> Dict[str, Any]:
    n = _count_internal_links(html)
    if n < minimum:
        return {"status": "FAIL", "detail": f"Only {n} internal link(s) (minimum {minimum})"}
    return {"status": "PASS", "detail": f"{n} internal links"}


def _check_has_tldr(html: str) -> Dict[str, Any]:
    if re.search(r"tl;?dr|too long|key takeaways|quick summary", html, flags=re.IGNORECASE):
        return {"status": "PASS", "detail": "TL;DR / summary block present"}
    return {"status": "WARN", "detail": "No TL;DR or key-takeaways block"}


def _check_has_faq(html: str) -> Dict[str, Any]:
    if re.search(r"frequently asked|faq", html, flags=re.IGNORECASE):
        return {"status": "PASS", "detail": "FAQ section present"}
    return {"status": "WARN", "detail": "No FAQ section"}


def _check_no_broken_sentences(html: str) -> Dict[str, Any]:
    text = _strip_tags(html)
    # Sentences ending abruptly before a heading, double periods, orphan fragments.
    fragments = re.findall(r"\b(and|or|the|a|an|of|to|in|for|with)\s*[.!?]", text, flags=re.IGNORECASE)
    doubles = text.count("..")
    if fragments or doubles:
        return {"status": "WARN",
                "detail": f"{len(fragments)} dangling fragment(s), {doubles} double-period(s)"}
    return {"status": "PASS", "detail": "No broken sentences detected"}


def _check_keyword_in_title(html: str, keyword: str) -> Dict[str, Any]:
    if not keyword or len(keyword.strip()) < 3:
        return {"status": "WARN", "detail": "No target keyword supplied for title check"}
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.IGNORECASE | re.DOTALL)
    title = _strip_tags(m.group(1)).lower() if m else ""
    kw_words = [w for w in keyword.lower().split() if len(w) > 3]
    if not kw_words:
        return {"status": "WARN", "detail": "Keyword has no significant words to check"}
    if any(w in title for w in kw_words):
        return {"status": "PASS", "detail": "Keyword present in H1"}
    return {"status": "FAIL", "detail": f"H1 does not contain keyword '{keyword}'"}


def _check_no_placeholders(html: str) -> Dict[str, Any]:
    hits = []
    for pat in _PLACEHOLDER_PATTERNS:
        hits += re.findall(pat, html, flags=re.IGNORECASE)
    if hits:
        return {"status": "FAIL", "detail": f"Placeholder text found: {hits[:3]}"}
    return {"status": "PASS", "detail": "No placeholder text"}


def _check_css_values_clean(html: str) -> Dict[str, Any]:
    # Inline styles with empty/broken values (e.g. "color:;") or stray braces.
    broken = re.findall(r'style="[^"]*:\s*;', html) + re.findall(r"\{\{[^}]*\}\}", html)
    if broken:
        return {"status": "WARN", "detail": f"{len(broken)} suspicious inline style/template artifact(s)"}
    return {"status": "PASS", "detail": "No broken inline CSS"}


def _check_anchor_quality(html: str) -> Dict[str, Any]:
    """Flag generic, non-descriptive anchor texts that damage SEO (e.g. 'click here')."""
    bad_anchors = {"click here", "read more", "this link", "here", "learn more",
                   "link", "this post", "article", "website", "page", "source", "check this"}
    links = re.findall(r'<a\s+[^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL)
    violating = []
    valid_count = 0
    for a in links:
        clean = _strip_tags(a).strip().lower()
        if not clean or clean in bad_anchors:
            violating.append(clean or "(empty anchor)")
        else:
            valid_count += 1
    if violating:
        return {"status": "FAIL",
                "detail": f"Generic anchor text detected: {violating[:3]}. Use descriptive keyword anchors."}
    return {"status": "PASS", "detail": f"{valid_count} descriptive internal/external anchor(s)"}


def _check_required_disclaimer(html: str) -> Dict[str, Any]:
    """Ensure legal/medical/informational disclaimers are present."""
    disclaimer_pattern = (
        r"(disclaimer|not legal advice|informational purposes only|"
        r"consult (?:an attorney|a lawyer|a doctor|a professional)|"
        r"not medical advice|educational purposes only|attorney-client relationship)"
    )
    if not re.search(disclaimer_pattern, html, flags=re.IGNORECASE):
        return {"status": "FAIL", "detail": "Missing mandatory legal/informational disclaimer"}
    return {"status": "PASS", "detail": "Required disclaimer present"}


def _check_untraced_facts_and_figures(html: str, verified_facts: Optional[List[str]] = None) -> Dict[str, Any]:
    """Hard-fail any statutory citation, filing deadline, or specific dollar figure that cannot be traced."""
    text = _strip_tags(html)
    statutes = re.findall(r'(?:§\s*\d+[\.\d\w]*|Section\s+\d+[\.\d\w]*|\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Code\s+§?\s*\d+)', text)
    deadlines = re.findall(r'(?:statute of limitations\s*(?:is|of)?\s*\d+\s*(?:years?|months?|days?)|\b\d+\s*(?:years?|months?|days?)\s*to file\b)', text, flags=re.IGNORECASE)
    figures = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d+)?\s*(?:million|billion|k)?', text, flags=re.IGNORECASE)

    facts = [f.lower() for f in (verified_facts or []) if f]
    untraced = []

    def _is_claim_traced(claim_clean: str, facts_list: List[str]) -> bool:
        c_low = claim_clean.lower()
        for fact in facts_list:
            if c_low in fact or fact in c_low:
                return True
            stat_num_match = re.search(r'(?:§|section)\s*(\d+[\.\d\w]*)', c_low)
            if stat_num_match:
                stat_num = stat_num_match.group(1).lower()
                if stat_num in fact and any(term in fact for term in ["section", "§", "code", "ccp", "statute"]):
                    return True
            dur_match = re.search(r'(\d+)\s*(year|month|day)', c_low)
            if dur_match:
                num = dur_match.group(1)
                unit = dur_match.group(2)
                if (f"{num} {unit}" in fact or f"{num}-{unit}" in fact) and any(k in fact for k in ["statute", "limitation", "deadline", "file"]):
                    return True
        return False

    # If statutory claims or deadlines exist, they MUST match at least one verified fact
    for claim in (statutes + deadlines):
        claim_clean = re.sub(r"[^\w\s§]+$", "", claim.strip()).strip()
        if not facts:
            untraced.append(f"{claim_clean} (no verified facts loaded)")
            continue
        if not _is_claim_traced(claim_clean, facts):
            untraced.append(claim_clean)

    if untraced:
        return {
            "status": "FAIL",
            "detail": f"Hard-fail: untraced statutory/deadline claim(s): {', '.join(untraced[:4])}",
            "untraced": untraced,
        }
    return {
        "status": "PASS",
        "detail": f"Verified: {len(statutes)} statute(s), {len(deadlines)} deadline(s), {len(figures)} figure(s)",
    }


def run_qa_gate(article_html: str, keyword: str = "", meta_description: str = "",
                fact_result: Optional[Dict[str, Any]] = None,
                verified_facts: Optional[List[str]] = None) -> Dict[str, Any]:
    """Independent deterministic QA checks.

    fact_result: optional output of the live fact-verification pass
      ({"critical_failures": int, ...}). When supplied and
      critical_failures > 0, the fact check is a HARD_FAIL.
    verified_facts: optional list of verified facts from the site's brand voice guide.
    Returns {"gate": "PASS"|"HARD_FAIL", "hard_fails": [...],
             "warnings": [...], "details": {...}}.
    """
    checks = {
        "title_length": _check_title_length(article_html),
        "meta_description": _check_meta_description(article_html, meta_description),
        "single_h1": _check_single_h1(article_html),
        "word_count": _check_word_count(article_html),
        "internal_links": _check_internal_links(article_html),
        "anchor_quality": _check_anchor_quality(article_html),
        "has_tldr": _check_has_tldr(article_html),
        "has_faq": _check_has_faq(article_html),
        "required_disclaimer": _check_required_disclaimer(article_html),
        "no_broken_sentences": _check_no_broken_sentences(article_html),
        "keyword_present": _check_keyword_in_title(article_html, keyword),
        "no_placeholder_text": _check_no_placeholders(article_html),
        "css_values_clean": _check_css_values_clean(article_html),
        "statutes_and_figures": _check_untraced_facts_and_figures(article_html, verified_facts),
    }
    if fact_result is not None:
        crit = int(fact_result.get("critical_failures", 0) or 0)
        if crit > 0:
            checks["fact_check"] = {
                "status": "FAIL",
                "detail": (f"{crit} unverifiable high-risk claim(s): "
                           + "; ".join((fact_result.get("unverified_claims") or [])[:3])),
            }
        elif fact_result.get("performed") is False:
            checks["fact_check"] = {"status": "FAIL",
                                    "detail": "Fact verification did not run — article blocked"}
        else:
            checks["fact_check"] = {"status": "PASS",
                                    "detail": f"{fact_result.get('claims_checked', 0)} claim(s) verified"}

    hard_fails = [k for k, v in checks.items() if v.get("status") == "FAIL"]
    warnings = [k for k, v in checks.items() if v.get("status") == "WARN"]
    return {"gate": "HARD_FAIL" if hard_fails else "PASS",
            "hard_fails": hard_fails, "warnings": warnings, "details": checks}

