import re
from datetime import datetime
from bs4 import BeautifulSoup


async def inject_citations(html_content: str, target_keyword: str, website_id: str) -> str:
    soup = BeautifulSoup(html_content, 'html.parser')
    current_year = datetime.utcnow().year

    citation_triggers = [
        r'\d+\s*%',
        r'\$[\d,]+',
        r'\d+\s*(million|billion)',
        r'studies show',
        r'research shows',
        r'according to',
        r'data shows',
        r'statistics show',
        r'experts say',
        r'reports indicate',
    ]

    paragraphs_to_cite = []
    for p in soup.find_all('p'):
        text = p.get_text()
        for pattern in citation_triggers:
            if re.search(pattern, text, re.IGNORECASE):
                if not p.find('a'):
                    paragraphs_to_cite.append(p)
                break

    for p in paragraphs_to_cite[:5]:
        text = p.get_text()
        claim_search = f"{target_keyword} statistics data {current_year}"

        try:
            from services.serper_service import serper_search_safe
            results = await serper_search_safe(claim_search, num_results=5)
        except Exception:
            results = []

        authority_domains = [
            'gov', 'edu', 'nih.gov', 'cdc.gov', 'who.int',
            'nhtsa.gov', 'bls.gov', 'census.gov', 'statista.com',
            'pewresearch.org', 'rand.org', 'brookings.edu',
            'reuters.com', 'apnews.com', 'npr.org'
        ]

        authority_results = []
        for result in (results or []):
            link = result.get('link', '')
            if any(domain in link for domain in authority_domains):
                authority_results.append(result)

        if not authority_results:
            authority_results = results[:1] if results else []

        if authority_results:
            source = authority_results[0]
            source_url = source.get('link', '')
            source_title = source.get('title', 'Source')

            p_str = str(p)
            citation_html = (
                f' <a href="{source_url}" '
                f'target="_blank" '
                f'rel="noopener noreferrer nofollow" '
                f'title="{source_title}">'
                f'[source]</a>'
            )
            new_p = p_str.replace('</p>', f'{citation_html}</p>')
            p.replace_with(BeautifulSoup(new_p, 'html.parser'))

    return str(soup)


def inject_term_definitions(html_content: str, industry: str = "legal") -> str:
    legal_terms = {
        "statute of limitations": "the legal deadline by which a lawsuit must be filed",
        "comparative negligence": "a legal rule that reduces your compensation by your percentage of fault",
        "contingency fee": "a payment structure where the attorney only gets paid if you win",
        "subrogation": "the right of an insurer to pursue a third party that caused an insurance loss",
        "discovery rule": "a legal exception that starts the filing clock when the injury is discovered",
        "stowers demand": "a formal demand requiring an insurer to settle within policy limits",
        "eggshell plaintiff": "a legal doctrine that makes a defendant fully liable even if the victim had pre-existing conditions",
        "spoliation": "the destruction or alteration of evidence relevant to a legal case",
        "diminished value": "the reduction in a vehicle's market value after an accident even after repairs",
        "loss of consortium": "a legal claim by a spouse for loss of companionship due to an injury",
        "sovereign immunity": "a doctrine that protects government entities from certain lawsuits",
        "bad faith": "when an insurer intentionally denies, delays, or underpays a valid claim",
        "mediation": "a voluntary negotiation process where a neutral third party helps resolve disputes",
        "deposition": "formal out-of-court testimony given under oath and recorded for legal proceedings",
        "indemnification": "a contractual obligation to compensate another party for losses or damages",
    }

    medical_terms = {
        "herniated disc": "a spinal injury where disc material pushes out and presses on nearby nerves",
        "traumatic brain injury": "damage to the brain caused by an external physical force or violent jolt",
        "whiplash": "a neck injury caused by rapid back-and-forth movement of the neck",
        "edr": "an Event Data Recorder, the vehicle's black box that captures crash data",
        "ptsd": "Post-Traumatic Stress Disorder, a mental health condition triggered by trauma",
        "emg": "Electromyography, a diagnostic test that measures nerve and muscle electrical activity",
    }

    all_terms = {**legal_terms, **medical_terms}
    soup = BeautifulSoup(html_content, 'html.parser')
    defined_terms = set()

    for p in soup.find_all('p'):
        p_text = p.get_text().lower()
        p_str = str(p)

        for term, definition in all_terms.items():
            if term in p_text and term not in defined_terms:
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                match = pattern.search(p_str)

                if match:
                    original_term = p_str[match.start():match.end()]
                    wrapped = (
                        f'<abbr title="{definition}" '
                        f'style="text-decoration: underline dotted; cursor: help;">'
                        f'{original_term}</abbr>'
                    )
                    new_p = p_str.replace(original_term, wrapped, 1)
                    p.replace_with(BeautifulSoup(new_p, 'html.parser'))
                    defined_terms.add(term)
                    break

    return str(soup)


def build_quick_facts_table(outline: dict, website_facts: dict, target_keyword: str) -> str:
    from datetime import datetime
    current_year = datetime.utcnow().year

    rows = []

    if website_facts.get('location_city') and website_facts.get('location_state'):
        rows.append((
            "Coverage Area",
            f"{website_facts['location_city']}, {website_facts['location_state']}"
        ))

    if website_facts.get('years_experience'):
        rows.append((
            "Years of Experience",
            f"{website_facts['years_experience']} years"
        ))

    search_intent = outline.get('point_3_search_intent', {})
    if search_intent.get('what_reader_wants'):
        rows.append((
            "This Article Covers",
            search_intent['what_reader_wants']
        ))

    faq_count = len(outline.get('point_14_faqs', []))
    if faq_count > 0:
        rows.append(("FAQs Answered", str(faq_count)))

    rows.append(("Last Updated", datetime.utcnow().strftime("%B %Y")))
    rows.append(("Content Type", "Legal Guide"))

    if not rows:
        return ""

    table_html = """<table class="rf-quick-facts" style="width:100%; border-collapse:collapse; margin:16px 0; font-size:14px;">
<thead>
<tr style="background:#f3f4f6;">
<th style="padding:10px 14px; text-align:left; border:1px solid #e5e7eb; color:#374151;">Topic</th>
<th style="padding:10px 14px; text-align:left; border:1px solid #e5e7eb; color:#374151;">Details</th>
</tr>
</thead>
<tbody>
"""

    for label, value in rows:
        table_html += f"""<tr>
<td style="padding:10px 14px; border:1px solid #e5e7eb; font-weight:600; color:#374151;">{label}</td>
<td style="padding:10px 14px; border:1px solid #e5e7eb; color:#4b5563;">{value}</td>
</tr>
"""

    table_html += "</tbody></table>"
    return table_html


def inject_quick_facts_table(html_content: str, table_html: str) -> str:
    if not table_html:
        return html_content

    soup = BeautifulSoup(html_content, 'html.parser')
    tldr = soup.find(class_='tldr-block')

    if tldr:
        table_soup = BeautifulSoup(table_html, 'html.parser')
        tldr.insert_after(table_soup)

    return str(soup)


def validate_chunk_lengths(html_content: str) -> dict:
    soup = BeautifulSoup(html_content, 'html.parser')
    issues = []

    for i, p in enumerate(soup.find_all('p')):
        text = p.get_text().strip()
        word_count = len(text.split())

        if word_count < 50 and word_count > 10:
            issues.append({
                "paragraph_index": i,
                "word_count": word_count,
                "issue": "too_short",
                "text_preview": text[:80]
            })
        elif word_count > 180:
            issues.append({
                "paragraph_index": i,
                "word_count": word_count,
                "issue": "too_long",
                "text_preview": text[:80]
            })

    return {
        "total_paragraphs": len(soup.find_all('p')),
        "issues": issues,
        "issue_count": len(issues),
        "geo_ready": len(issues) == 0
    }


async def auto_fix_chunk_lengths(html_content: str) -> str:
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(html_content, 'html.parser')
    paragraphs = soup.find_all('p')

    for p in paragraphs:
        text = p.get_text().strip()
        words = text.split()
        word_count = len(words)

        if word_count > 180:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            mid = len(sentences) // 2
            part1 = ' '.join(sentences[:mid])
            part2 = ' '.join(sentences[mid:])

            if len(part1.split()) >= 30 and len(part2.split()) >= 30:
                new_html = f"<p>{part1}</p><p>{part2}</p>"
                p.replace_with(BeautifulSoup(new_html, 'html.parser'))

    return str(soup)
