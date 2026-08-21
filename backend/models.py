from typing import Optional, List, Any
from pydantic import BaseModel, Field


class Website(BaseModel):
    id: str
    domain: str
    cms_url: Optional[str] = None
    cms_user: Optional[str] = None
    app_password: Optional[str] = None
    gsc_property: Optional[str] = None
    created_at: str


class Page(BaseModel):
    id: str
    website_id: str
    url: str
    title: Optional[str] = None
    content_text: Optional[str] = None
    embedding: Optional[List[float]] = None
    last_audited: Optional[str] = None
    impressions: int = 0
    ctr: float = 0.0
    created_at: str


class WebsiteKnowledge(BaseModel):
    id: str
    website_id: str
    url: str
    title: Optional[str] = None
    content_text: str
    embedding: List[float]
    content_type: Optional[str] = None
    tone_sample: Optional[str] = None
    extracted_facts: Any = None
    crawled_at: str


class ToneProfile(BaseModel):
    id: str
    website_id: str
    tone_description: str
    writing_style: str
    vocabulary: List[str] = []
    forbidden_words: List[str] = []
    sample_embeddings: List[List[float]] = []
    created_at: str
    updated_at: str


class KnowledgeBase(BaseModel):
    id: str
    website_id: str
    fact: str
    fact_type: str
    source_url: Optional[str] = None
    embedding: List[float]
    created_at: str


class ContentLog(BaseModel):
    id: str
    website_id: str
    title: str
    content: str
    status: str = "draft_planned"
    keyword: Optional[str] = None
    use_case: Optional[str] = None
    embedding: Optional[List[float]] = None
    faq_schema: Any = None
    internal_links: Any = None
    similarity_score: Optional[float] = None
    published_url: Optional[str] = None
    created_at: str


class Audit(BaseModel):
    id: str
    website_id: str
    page_url: Optional[str] = None
    issue_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    impact_score: Optional[float] = None
    status: str = "pending_approval"
    created_at: str


class QualityCheck(BaseModel):
    id: str
    content_log_id: str
    website_id: str
    spell_check_pass: bool = True
    spell_errors: Any = None
    tone_match_score: float = 0.0
    knowledge_match_pass: bool = True
    knowledge_errors: Any = None
    factual_accuracy_pass: bool = True
    overall_pass: bool = True
    checked_at: str


class AgentThought(BaseModel):
    id: str
    website_id: str
    agent_name: str
    thought: str
    decision: Optional[str] = None
    created_at: str


class AgentFeedback(BaseModel):
    id: str
    website_id: str
    agent_name: str
    rejected_type: str
    rejected_value: Optional[str] = None
    human_feedback: str
    learning: Optional[str] = None
    created_at: str


class Task(BaseModel):
    id: str
    website_id: Optional[str] = None
    agent_name: str
    action: str
    payload: Any = None
    result: Any = None
    status: str = "pending"
    real_api_called: Optional[str] = None
    created_at: str


class TechnicalAudit(BaseModel):
    id: str
    website_id: str
    url: str
    issue_type: str
    severity: str = "medium"
    details: Any = None
    status: str = "open"
    created_at: str


class Backlink(BaseModel):
    id: str
    website_id: str
    source_url: str
    target_url: str
    anchor_text: Optional[str] = None
    domain_rating: int = 0
    first_seen: str
    last_seen: str
    status: str = "active"
    created_at: str


class LlmsTxtLog(BaseModel):
    id: str
    website_id: str
    content: str
    last_updated: str
    next_due: str
