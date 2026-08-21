import logging
import re
from typing import Dict, Any, List

logger = logging.getLogger("backend.agents.elementor_agent")


FORBIDDEN_PATTERNS = [
    r"```",
    r"\*\*[^*]+\*\*",
    r"\[wp:",
    r"<!-- wp:",
    r"\[/",
]


class ElementorAgent:
    """
    ElementorAgent - cleans HTML to only Elementor-compatible tags.
    Allowed: h1 h2 h3 h4 p ul ol li strong em a blockquote
    Strips markdown, code fences, shortcodes, wp: blocks.
    """

    ALLOWED_TAGS = {"h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "em", "a", "blockquote", "br", "hr", "b", "i"}

    def __init__(self, website_id: str):
        self.website_id = website_id

    async def run(self, seo_html: str) -> Dict[str, Any]:
        cleaned = self._clean(seo_html)
        violations = self._check_violations(seo_html)
        stats = self._compute_stats(cleaned)

        return {
            "clean_html": cleaned,
            "violations": violations,
            "stats": stats,
            "status": "passed" if not violations else "failed",
        }

    def _clean(self, html: str) -> str:
        text = html

        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"\[wp:[^\]]*\]", "", text)
        text = re.sub(r"<!-- wp:.*?-->", "", text, flags=re.DOTALL)
        text = re.sub(r"\[/?[^\]]*\]", "", text)

        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)

        lines = text.splitlines()
        safe_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                safe_lines.append("")
                continue
            tag_match = re.match(r"^<([a-zA-Z0-9]+)[^>]*>", stripped)
            if tag_match:
                tag = tag_match.group(1).lower()
                if tag in self.ALLOWED_TAGS:
                    safe_lines.append(line)
                    continue
            safe_lines.append(f"<p>{line}</p>")

        text = "\n".join(safe_lines)
        text = re.sub(r"<p>\s*</p>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _check_violations(self, html: str) -> List[str]:
        violations = []
        for pattern in FORBIDDEN_PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                violations.append(f"Forbidden pattern found: {pattern}")
        return violations

    def _compute_stats(self, html: str) -> Dict[str, int]:
        return {
            "h1": len(re.findall(r"<h1\b", html, re.IGNORECASE)),
            "h2": len(re.findall(r"<h2\b", html, re.IGNORECASE)),
            "h3": len(re.findall(r"<h3\b", html, re.IGNORECASE)),
            "p": len(re.findall(r"<p\b", html, re.IGNORECASE)),
            "a": len(re.findall(r"<a\b", html, re.IGNORECASE)),
            "li": len(re.findall(r"<li\b", html, re.IGNORECASE)),
            "total_chars": len(html),
            "total_words": len(re.sub(r"<[^>]+>", " ", html).split()),
        }


def create_elementor_agent(website_id: str) -> ElementorAgent:
    return ElementorAgent(website_id)
