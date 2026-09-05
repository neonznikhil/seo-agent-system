import json
import re
from datetime import datetime
from bs4 import BeautifulSoup


async def generate_article_schema(
    title: str,
    html_content: str,
    target_keyword: str,
    website_facts: dict,
    wp_url: str,
    published_at: str,
    faq_items: list
) -> str:
    soup = BeautifulSoup(html_content, 'html.parser')
    plain_text = soup.get_text()[:1000]
    current_date = datetime.utcnow().isoformat() + "Z"

    business_name = website_facts.get('business_name', 'Legal Services')
    location_city = website_facts.get('location_city', '')
    location_state = website_facts.get('location_state', '')
    attorney_names = website_facts.get('real_attorney_names', [])

    entities = {
        "organizations": [],
        "locations": [location_city] if location_city else [],
        "legal_concepts": [],
        "people": []
    }

    try:
        from database import call_nim_llm
        entities_response = await call_nim_llm(
            prompt=f"""
Extract named entities from this article.
Return ONLY this JSON:
{{
    "organizations": ["org1", "org2"],
    "locations": ["location1"],
    "legal_concepts": ["concept1", "concept2"],
    "people": ["name1"]
}}

Article text: {plain_text}
""",
            system="You respond only with valid JSON.",
            max_tokens=300,
            temperature=0.3,
            fail_silently=True
        )
        if entities_response:
            cleaned = entities_response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0]
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0]
            entities = json.loads(cleaned.strip())
    except Exception:
        pass

    mentions = []
    all_entities = (
        entities.get("organizations", []) +
        entities.get("legal_concepts", []) +
        entities.get("people", [])
    )

    for entity in all_entities[:10]:
        wiki_search = entity.replace(' ', '_')
        mentions.append({
            "@type": "Thing",
            "name": entity,
            "sameAs": f"https://en.wikipedia.org/wiki/{wiki_search}"
        })

    faq_schema = []
    for faq in (faq_items or []):
        if faq.get("question") and faq.get("answer_draft"):
            faq_schema.append({
                "@type": "Question",
                "name": faq["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq["answer_draft"]
                }
            })

    author_schema = {
        "@type": "Organization",
        "name": business_name,
        "url": website_facts.get("site_url", ""),
    }

    if attorney_names:
        author_schema = {
            "@type": "Person",
            "name": attorney_names[0],
            "jobTitle": "Attorney",
            "worksFor": {
                "@type": "Organization",
                "name": business_name
            }
        }

    location_schema = {}
    if location_city and location_state:
        location_schema = {
            "@type": "City",
            "name": location_city,
            "containedInPlace": {
                "@type": "State",
                "name": location_state
            }
        }

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "@id": f"{wp_url}#article",
                "headline": title,
                "description": plain_text[:160],
                "author": author_schema,
                "publisher": {
                    "@type": "Organization",
                    "name": business_name,
                    "url": website_facts.get("site_url", "")
                },
                "datePublished": published_at,
                "dateModified": current_date,
                "about": [
                    {
                        "@type": "Thing",
                        "name": target_keyword
                    }
                ],
                "mentions": mentions,
                "locationCreated": location_schema if location_schema else None,
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": wp_url
                }
            },
            {
                "@type": "FAQPage",
                "@id": f"{wp_url}#faq",
                "mainEntity": faq_schema
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": website_facts.get("site_url", "")
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": "Blog",
                        "item": f"{website_facts.get('site_url', '')}/blog"
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": title,
                        "item": wp_url
                    }
                ]
            }
        ]
    }

    def remove_none(obj):
        if isinstance(obj, dict):
            return {k: remove_none(v) for k, v in obj.items() if v is not None}
        elif isinstance(obj, list):
            return [remove_none(i) for i in obj if i is not None]
        return obj

    clean_schema = remove_none(schema_graph)

    schema_tag = (
        f'\n<script type="application/ld+json">\n'
        f'{json.dumps(clean_schema, indent=2)}\n'
        f'</script>\n'
    )

    return schema_tag
