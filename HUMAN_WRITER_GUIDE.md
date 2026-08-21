# Human-Only SEO Content Generation System

## Overview

This system ensures content is written like a 10+ year experienced human SEO expert, NOT like AI-generated text.

## Core Tools

### 1. humanizer.py - Anti-AI Content Quality

**Function: `humanize_content(text)`**
- Removes em dash `—` (replaces with comma/period)
- Removes banned AI phrases
- Fixes excessive single quotes
- Normalizes spacing

**Function: `detect_ai_patterns(text)`**
Returns:
- `human_score`: 0-100 (75+ is human)
- `is_human`: True/False
- `issues`: List of problems found
- `recommendations`: How to fix

**Function: `optimize_for_human_readability(text)`**
- Applies contractions naturally
- Improves sentence burstiness
- Applies all humanization rules

## Banned AI Patterns

### Characters
- Never use em dash `—` 
- Never overuse en dash `–`

### Phrases
- "In today's fast-paced world"
- "In today's digital landscape"
- "In conclusion", "In summary"
- "Delve", "Dive into"
- "Unlock", "Unleash"
- "Elevate", "Embark"
- "It's important to note", "It's worth noting"
- "As we all know"
- "Leverage", "Utilize"
- "Comprehensive guide"
- "Plethora", "Myriad"
- "Cutting-edge", "Game-changer"

## Human Writing Patterns

### Sentence Structure
- Vary length: short, medium, long, short
- Use contractions naturally: don't, can't, it's, you're
- Start sentences with: "And", "But", "So"
- Use active voice

### Content Requirements
- Primary keyword in title + first 100 words + 1 H2
- Include 2+ facts from knowledge base verbatim
- Match brand tone from tone profiles
- Add 2-3 internal links with keyword anchor text
- Include table comparing options
- Add FAQ section (4 questions)
- Add actionable checklist

## Usage in Writer Agent

```python
# In generate_blog() function:

# 1. Get website context
knowledge = get_website_knowledge(website_id)
tone = get_tone_profiles(website_id)
facts = get_knowledge_base_facts(website_id)
keywords = get_active_keywords(website_id)

# 2. Build system prompt with all context
system_prompt = f"""
You are senior SEO content writer with 8 years experience.

BUSINESS: {business_name}
KEYWORD: {primary_keyword}
TONE: {tone['tone_description']}
EXAMPLE PHRASES: {tone['example_phrases']}
"""

# 3. Generate content with higher temperature
response = nime_llm.generate(prompt, temperature=0.85, top_p=0.92)

# 4. Humanize immediately
humanized = optimize_for_human_readability(response.content)

# 5. Check for AI patterns
result = detect_ai_patterns(humanized)
if result["human_score"] < 75:
    # Regenerate with instruction
    response = nime_llm.generate_with_instruction(
        prompt,
        f"Rewrite avoiding: {result['issues']}",
        temperature=0.9
    )
    humanized = optimize_for_human_readability(response.content)
    result = detect_ai_patterns(humanized)

# 6. Validate requirements
has_keyword = ensure_keyword_in_title_content(humanized, primary_keyword)
tone_match = calculate_tone_match(humanized, tone)
business_match = check_facts_in_content(humanized, facts)

# 7. Quality gates
if result["is_human"] and tone_match > 0.75 and business_match:
    # Save as pending_approval
    save_content(humanized, "pending_approval")
else:
    # Save as needs_revision with reason
    save_content(humanized, "needs_revision", result["issues"])
```

## API Endpoints for Testing

```
POST /api/generate-content
{
  "topic": "SEO content marketing",
  "target_keyword": "best SEO strategy",
  "content_length": 1500
}
```

## Testing

Run tests:
```bash
pytest backend/tests/test_writer_human_standalone.py -v
```

Pass criteria:
- `is_human` must be True
- `human_score` >= 75
- No em dashes
- No banned phrases
- Keyword in title, intro, and H2
- Tone matches brand profile



## Writer Agent Update

Update `backend/agents/writer_agent.py` to:

1. Import humanizer tool
2. Fetch website knowledge, tone, facts, keywords
3. Inject context into system prompt
4. Regenerate if AI patterns detected
5. Validate before saving as pending_approval

See `backend/agents/tools/humanizer.py` for implementation details.