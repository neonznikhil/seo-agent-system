import re
import json
from typing import Dict, List, Tuple, Optional

BANNED_PHRASES = [
    "in today's fast-paced world",
    "in today's digital landscape", 
    "in conclusion",
    "in summary",
    "delve",
    "dive into",
    "unlock",
    "unleash",
    "elevate",
    "embark on",
    "navigating",
    "the landscape",
    "the realm",
    "it's important to note",
    "it's worth noting",
    "as we all know",
    "remember that",
    "revolutionize",
    "game-changer",
    "cutting-edge",
    "leverage",
    "utilize",
    "comprehensive guide",
    "plethora",
    "myriad",
    "tapestry",
]

BANNED_CHARACTERS = ['—', '–']

AI_CONTRACTIONS = [
    "it's", "it's", "it's", "it's", "it's", "it's"
]


def humanize_content(text: str) -> str:
    result = text
    
    result = result.replace('—', ', ')
    result = result.replace('–', '-')
    result = re.sub(r'\s{2,}', ' ', result)
    result = re.sub(r"'([a-zA-Z0-9]{2,20})'", r'\1', result)
    
    for phrase in BANNED_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        result = pattern.sub('', result)
    
    result = result.replace('  ', ' ')
    result = re.sub(r'\s+([,.!?;:])', r'\1', result)
    
    return result.strip()


def detect_ai_patterns(text: str) -> Dict:
    score = 100
    issues = []
    warnings = []
    
    if '—' in text:
        score -= 20
        issues.append({
            "type": "em_dash",
            "severity": "high",
            "message": "Contains em dash — AI tell"
        })
    
    if '–' in text:
        score -= 10
        issues.append({
            "type": "en_dash", 
            "severity": "medium",
            "message": "Contains en dash"
        })
    
    quote_count = text.count("'")
    if quote_count > 15:
        score -= 10 * (quote_count // 15)
        issues.append({
            "type": "excess_quotes",
            "severity": "medium",
            "message": f"Overuse of single quotes: {quote_count} found"
        })
    
    found_banned = []
    for phrase in BANNED_PHRASES:
        if phrase.lower() in text.lower():
            found_banned.append(phrase)
            score -= 15
    
    if found_banned:
        issues.append({
            "type": "banned_phrases",
            "severity": "high",
            "message": f"Banned AI phrases found: {found_banned}"
        })
    
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    if sentences:
        lengths = [len(s.split()) for s in sentences]
        avg_len = sum(lengths) / len(lengths)
        if avg_len > 30:
            score -= 10
            issues.append({
                "type": "long_sentences",
                "severity": "medium",
                "message": f"Average sentence length {avg_len:.0f} words - too long"
            })
        elif avg_len < 10:
            score -= 5
            warnings.append({
                "type": "short_sentences",
                "severity": "low",
                "message": f"Average sentence length {avg_len:.0f} - may be too fragmented"
            })
    
    compound_words = re.findall(r'[A-Z][a-z]+-[A-Z][a-z]+', text)
    if len(compound_words) > 30:
        score -= len(compound_words) - 30
        issues.append({
            "type": "excess_compound",
            "severity": "low",
            "message": f"Many compound words ({len(compound_words)}) - check if natural"
        })
    
    return {
        "human_score": max(score, 0),
        "is_human": score >= 75,
        "issues": issues,
        "warnings": warnings,
        "recommendations": ["Rewrite with varied sentence lengths", "Remove AI phrases"] if score < 75 else []
    }


def fix_contractions(text: str) -> str:
    result = text
    
    contractions_map = {
        "do not": "don't",
        "cannot": "can't",
        "will not": "won't",
        "should not": "shouldn't",
        "would not": "wouldn't",
        "could not": "couldn't",
        "is not": "isn't",
        "are not": "aren't",
        "was not": "wasn't",
        "were not": "weren't",
        "have not": "haven't",
        "has not": "hasn't",
        "had not": "hadn't",
    }
    
    for formal, contraction in contractions_map.items():
        if len(formal.split()) == 2:
            pattern = r'\b' + formal.replace(' ', r'\s+') + r'\b'
            result = re.sub(pattern, contraction, result, flags=re.IGNORECASE)
    
    return result


def improve_burstiness(text: str) -> str:
    sentences = re.split(r'([.!?])', text)
    result = []
    
    for i, (part, sep) in enumerate(zip(sentences[::2], sentences[1:])):
        if not part:
            continue
        
        words = part.split()
        if len(words) > 25:
            mid = len(words) // 2
            new_sentence = ' '.join(words[:mid]) + '.'
            result.append(new_sentence)
            result.append(' '.join([''.join(words[mid:])] + [sep] if sep else ['']))
        else:
            if i > 0 and len(result) > 0 and len(result[-1].split()) < 5:
                result[-1] = result[-1].rstrip('.!?')
                result[-1] += ', ' + part.lstrip().lstrip(',').lstrip() + sep
            else:
                result.append(part + sep)
    
    return ''.join(result)


def calculate_tone_match(text: str, tone_profiles: dict) -> float:
    if not tone_profiles:
        return 0.8
    
    examples = tone_profiles.get("example_phrases", [])
    if not examples:
        return 0.8
    
    text_lower = text.lower()
    matches = 0
    total = min(len(examples), 5)
    
    for example in examples[:total]:
        if example.lower() in text_lower:
            matches += 1
    
    return matches / total if total > 0 else 0.5


def ensure_keyword_in_title_content(text: str, keyword: str) -> Tuple[str, bool]:
    title_pattern = r'^#+\s+(.+)$'
    h1_match = re.search(title_pattern, text, re.MULTILINE)
    h1 = h1_match.group(1) if h1_match else ""
    
    title_has_kw = keyword.lower() in h1.lower() if h1 else False
    
    intro_end = text.find('\n\n')
    intro = text[:intro_end] if intro_end > 0 else text[:500]
    intro_has_kw = keyword.lower() in intro.lower()
    
    h2_pattern = r'^##\s+(.+)$'
    h2_matches = re.findall(h2_pattern, text, re.MULTILINE)
    h2_has_kw = any(keyword.lower() in h2.lower() for h2 in h2_matches) if h2_matches else False
    
    conclusion_pattern = r'(conclusion|summary|final|takeaway)'
    conclusion_has_kw = False
    for match in re.finditer(conclusion_pattern, text, re.IGNORECASE):
        section = text[match.start():match.start()+300]
        if keyword.lower() in section.lower():
            conclusion_has_kw = True
            break
    
    return text, (title_has_kw or intro_has_kw) and (h2_has_kw or conclusion_has_kw)


def count_banned_phrases(text: str) -> List[str]:
    found = []
    for phrase in BANNED_PHRASES:
        if phrase.lower() in text.lower():
            found.append(phrase)
    return found


def optimize_for_human_readability(text: str) -> str:
    result = fix_contractions(text)
    result = improve_burstiness(result)
    result = humanize_content(result)
    
    return result


if __name__ == "__main__":
    test_text = """
    In today's fast-paced world, it's important to note that leveraging a comprehensive CRM solution can revolutionize your business—unlocking unparalleled growth. Delve into our cutting-edge strategies to elevate your operations. Remember that the landscape of technology has transformed dramatically.
    """
    
    print("Original AI text:")
    print(test_text[:200])
    print("\nDetected AI patterns:", detect_ai_patterns(test_text))
    print("\nHumanized text:")
    print(humanize_content(test_text))