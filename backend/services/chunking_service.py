from bs4 import BeautifulSoup
import re


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
