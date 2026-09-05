import os
import re
import logging
from datetime import datetime

logger = logging.getLogger("backend.services.reddit_service")


class RedditService:
    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = os.getenv("REDDIT_USER_AGENT", "RankForge/1.0")

    async def search_relevant_threads(self, keywords: list, subreddits: list = None) -> list:
        from services.serper_service import serper_search_safe

        all_threads = []
        for keyword in keywords[:5]:
            query = f"site:reddit.com {keyword}"
            results = await serper_search_safe(query, num_results=5)

            for result in (results or []):
                if 'reddit.com' in result.get('link', ''):
                    all_threads.append({
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "snippet": result.get("snippet", ""),
                        "keyword": keyword,
                        "subreddit": self._extract_subreddit(result.get("link", ""))
                    })

        return all_threads

    def _extract_subreddit(self, url: str) -> str:
        match = re.search(r'reddit\.com/r/([^/]+)', url)
        return match.group(1) if match else "unknown"

    async def identify_opportunity_threads(self, threads: list, website_domain: str) -> list:
        opportunities = []
        for thread in threads:
            title = thread.get("title", "").lower()
            question_indicators = [
                "?", "how to", "how do", "what is", "can i",
                "should i", "advice", "help", "recommend",
                "looking for", "need help", "anyone know"
            ]

            is_question = any(ind in title for ind in question_indicators)

            if is_question:
                if website_domain not in thread.get("snippet", ""):
                    opportunities.append({
                        **thread,
                        "opportunity_type": "unanswered_question",
                        "suggested_action": "provide helpful answer with link"
                    })

        return opportunities

    async def generate_reddit_comment(
        self,
        thread_title: str,
        thread_snippet: str,
        website_facts: dict,
        relevant_article_url: str
    ) -> str:
        current_year = datetime.utcnow().year

        business_name = website_facts.get('business_name', '')
        location = (
            f"{website_facts.get('location_city', '')}, "
            f"{website_facts.get('location_state', '')}"
        ).strip(', ')

        try:
            from database import call_nim_llm
            comment = await call_nim_llm(
                prompt=f"""
Reddit thread: "{thread_title}"
Context: {thread_snippet}

Write a helpful comment that answers their question.
If a link is appropriate, add at the end:
"More detail here if helpful: {relevant_article_url}"

Location context (use if relevant): {location}
Year: {current_year}
""",
                system="""
You write helpful Reddit comments that provide real value.
Rules:
- Start with the actual answer, not a promotion
- Be conversational and human
- Use Reddit tone (casual, direct, no corporate speak)
- Only include a link at the very end if it adds value
- Never say "I work at" or "our company"
- Maximum 150 words
- No bullet points — plain paragraph style
""",
                max_tokens=200,
                temperature=0.7,
                fail_silently=True
            )
            return comment.strip()
        except Exception as e:
            logger.warning(f"[RedditService] Comment generation failed: {e}")
            return ""
