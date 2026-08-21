# SOLID Rules

## Rule 1: Knowledge First - Crawl 20 Pages Before Work

Before any content creation, use Crawlee to crawl 20 pages from the target website. Extract:
- Tone and style patterns
- Key facts and figures
- Topic clusters
- Content structure

Store in knowledge_base table. **Evidence: `backend/agents/crew.py:108-116`** in audit_task description.

## Rule 2: 24/7 Autonomous with Full Records

The system runs continuously with full audit trail:
- `agent_thoughts` table logs all agent reasoning
- `tasks` table tracks every action with timestamps
- `content_log` tracks content from draft to published

**Evidence: `backend/agents/crew.py:162-166`, `backend/agents/tools/think_and_log_tool.py`**

## Rule 3: llms.txt - Monthly 30 Days or 10 Blogs

LLMS.TXT file is generated once per month or when 10 new blogs are ready. Not daily regeneration.

**Evidence: `backend/agents/tools/llms_txt_tool.py` checks existing count before generation**

## Rule 4: Daily Work Limits - Max 5 Fixes, Max 2 Blogs

Per day:
- Max 5 quick fixes (single-page updates)
- Max 2 full blog posts
- Homepage cooldown: 14 days between homepage drafts

**Evidence: `backend/agents/tools/crawler.py` and `backend/agents/scheduler.py` track daily counts**

## Rule 5: Quality Gate Before User Sees

Content must pass quality check before approval:
- Spell check: >3 errors = fail
- Tone: cosine similarity >0.75
- Knowledge: no contradictions
- Factual: table + stat + 50-word direct answer + 4+ FAQ

If fail: `content_log.status = "needs_revision"` (user never sees bad content)

If pass: `content_log.status = "pending_approval"`

**Evidence: `backend/agents/tools/quality_gate_tool.py:167-184`**

## Rule 6: Everything Logged

All actions logged to Supabase:
- `tasks`: infrastructure actions
- `agent_thoughts`: agent reasoning
- `content_log`: blog content states
- `quality_checks`: quality gate results
- `agent_feedback`: human feedback + learning

**Evidence: All tools include `_log_proof()` calls**

---

## Compliance Checklist

| Rule | Status | Evidence |
|------|--------|----------|
| 1. Knowledge first | IMPLEMENTED | crew.py:108-116 |
| 2. 24/7 autonomous | IMPLEMENTED | crew.py + think_and_log_tool.py |
| 3. llms.txt monthly | IMPLEMENTED | llms_txt_tool.py |
| 4. Daily limits | IMPLEMENTED | scheduler.py |
| 5. Quality gate | IMPLEMENTED | quality_gate_tool.py:167-184 |
| 6. Everything logged | IMPLEMENTED | All tools have _log_proof()
