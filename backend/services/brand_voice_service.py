"""Brand voice guides: versioned per-site writing contract.

load_brand_voice() returns the latest guide row for a site, or
DEFAULT_BRAND_VOICE when none exists (explicitly flagged as default so
callers can prompt the user to configure one instead of pretending).
build_brand_voice_block() renders the prompt section injected into every
writer brief: tone, rules, banned/required phrases, verified facts, and
approved/rejected examples.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger("backend.services.brand_voice")

try:
    from database import get_supabase
except (ImportError, ValueError):
    from backend.database import get_supabase

DEFAULT_BRAND_VOICE: Dict[str, Any] = {
    "is_default": True,
    "tone": "Authoritative, deeply informative, human-written, and transparent.",
    "structure_rules": ["Answer-first: lead each section with the direct answer.",
                        "One idea per section; short paragraphs."],
    "formatting_rules": ["Clean HTML headings (single H1).", "No markdown, no placeholders."],
    "banned_phrases": ["leverage", "game-changing", "in conclusion", "delve"],
    "required_phrases": [],
    "good_examples": [],
    "bad_examples": [],
    "verified_facts": [],
}


async def load_brand_voice(website_id: str) -> Dict[str, Any]:
    """Latest brand_voice_guides row for the site, else DEFAULT_BRAND_VOICE."""
    try:
        rows = get_supabase().table("brand_voice_guides").select("*").eq(
            "website_id", website_id).order("version", desc=True).limit(1).execute().data or []
    except Exception as e:
        logger.debug(f"[BrandVoice] load note: {e}")
        rows = []
    if not rows:
        try:
            from services.local_store import get_local_brand_voice
            local_g = get_local_brand_voice(website_id)
            if local_g:
                local_g["is_default"] = False
                return local_g
        except Exception:
            pass
        return dict(DEFAULT_BRAND_VOICE)
    guide = dict(rows[0])
    guide["is_default"] = False
    return guide


def build_brand_voice_block(guide: Dict[str, Any]) -> str:
    """Render the BRAND VOICE GUIDE prompt block for writer briefs."""
    def _lines(items, limit=6):
        items = items or []
        return "\n".join(f"- {str(i)[:240]}" for i in items[:limit]) or "- (none configured)"

    return f"""BRAND VOICE GUIDE FOR THIS WEBSITE:
Tone: {guide.get('tone') or DEFAULT_BRAND_VOICE['tone']}
Structure rules:
{_lines(guide.get('structure_rules'), 8)}
Banned phrases (never use): {', '.join(guide.get('banned_phrases') or []) or '(none configured)'}
Required phrases: {', '.join(guide.get('required_phrases') or []) or '(none configured)'}
Verified facts you MUST use (do not contradict these):
{_lines(guide.get('verified_facts'), 10)}

APPROVED EXAMPLES (write like these):
{_lines(guide.get('good_examples'), 2)}

REJECTED EXAMPLES (never write like these):
{_lines(guide.get('bad_examples'), 2)}"""


async def save_brand_voice(website_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Save a new versioned guide row (version auto-increments)."""
    supabase = get_supabase()
    try:
        latest = supabase.table("brand_voice_guides").select("version").eq(
            "website_id", website_id).order("version", desc=True).limit(1).execute().data or []
        version = int((latest[0].get("version") or 0)) + 1 if latest else 1
    except Exception:
        version = 1
    row = {"website_id": website_id, "version": version}
    for key in ("tone", "structure_rules", "formatting_rules", "banned_phrases",
                "required_phrases", "good_examples", "bad_examples", "verified_facts",
                "approved_articles", "rejected_articles"):
        if payload.get(key) is not None:
            row[key] = payload[key]
    try:
        res = supabase.table("brand_voice_guides").insert(row).execute()
        saved = (res.data or [row])[0]
    except Exception as e:
        logger.debug(f"[BrandVoice] persist note: {e}")
        saved = row
    try:
        from services.local_store import save_local_brand_voice
        save_local_brand_voice(website_id, saved)
    except Exception:
        pass
    return saved


async def record_article_example(website_id: str, article_html: str, approved: bool,
                                 reason: str = "") -> None:
    """Append an approved/rejected example to the latest guide (creates one
    from defaults when none exists) so prompts improve over time."""
    guide = await load_brand_voice(website_id)
    key = "good_examples" if approved else "bad_examples"
    entry = (article_html[:2000] + (f"\n[Reviewer note: {reason}]" if reason else ""))
    if guide.get("is_default"):
        await save_brand_voice(website_id, {key: [entry]})
        return
    try:
        items = list(guide.get(key) or [])
        items.append(entry)
        get_supabase().table("brand_voice_guides").update(
            {key: items[-10:]}).eq("id", guide["id"]).execute()
    except Exception as e:
        logger.debug(f"[BrandVoice] record example note: {e}")
