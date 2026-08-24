-- =========================================================
-- RankForge Phase 3: Self-Evolving Autonomous Organism Tables
-- =========================================================

-- 1. Backlink Opportunities Table (Zero Outreach, Pure Technical Acquisition)
CREATE TABLE IF NOT EXISTS public.backlink_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    url TEXT NOT NULL,
    domain_rating INTEGER DEFAULT 40,
    opportunity_type TEXT DEFAULT 'resource_page', -- resource_page, statistics_citation, competitor_gap, unlinked_mention, link_page
    topic_relevance_score FLOAT DEFAULT 0.8,
    our_best_matching_asset_url TEXT,
    placement_context TEXT,
    acquisition_difficulty TEXT DEFAULT 'medium', -- low, medium, high
    priority_score FLOAT DEFAULT 50.0,
    status TEXT DEFAULT 'discovered', -- discovered, asset_briefed, asset_published, link_acquired, monitoring, competitor_preferred
    acquired_date TIMESTAMPTZ,
    acquired_anchor_text TEXT,
    acquired_page_dr INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Broken Link Opportunities
CREATE TABLE IF NOT EXISTS public.broken_link_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    source_url TEXT NOT NULL,
    broken_target_url TEXT NOT NULL,
    anchor_text TEXT,
    domain_rating INTEGER DEFAULT 40,
    page_traffic_estimate INTEGER DEFAULT 500,
    topic_relevance_score FLOAT DEFAULT 0.85,
    reclamation_difficulty TEXT DEFAULT 'medium',
    our_replacement_url TEXT,
    status TEXT DEFAULT 'new', -- new, content_created, published, acquired, failed
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Unlinked Brand Mentions
CREATE TABLE IF NOT EXISTS public.unlinked_mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    source_url TEXT NOT NULL,
    mention_context TEXT,
    domain_rating INTEGER DEFAULT 45,
    page_topic TEXT,
    discovered_date TIMESTAMPTZ DEFAULT now(),
    status TEXT DEFAULT 'unlinked', -- unlinked, linked, monitoring
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Competitor Backlink Gap Domains
CREATE TABLE IF NOT EXISTS public.backlink_gap_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    linking_domain TEXT NOT NULL,
    domain_rating INTEGER DEFAULT 50,
    links_to_competitors JSONB DEFAULT '[]'::jsonb,
    their_anchor_texts JSONB DEFAULT '[]'::jsonb,
    page_that_links TEXT,
    topic_of_linking_page TEXT,
    gap_priority_score FLOAT DEFAULT 50.0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Niche Ranking Signals (500-URL Sunday Harvest)
CREATE TABLE IF NOT EXISTS public.niche_ranking_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    keyword TEXT NOT NULL,
    url TEXT NOT NULL,
    position INTEGER NOT NULL,
    word_count INTEGER DEFAULT 1800,
    h1_text TEXT,
    h2_texts JSONB DEFAULT '[]'::jsonb,
    h3_texts JSONB DEFAULT '[]'::jsonb,
    faq_questions JSONB DEFAULT '[]'::jsonb,
    schema_types JSONB DEFAULT '[]'::jsonb,
    internal_links_count INTEGER DEFAULT 12,
    external_links_count INTEGER DEFAULT 6,
    image_count INTEGER DEFAULT 4,
    table_count INTEGER DEFAULT 1,
    reading_level FLOAT DEFAULT 8.5,
    content_freshness TEXT,
    load_speed_ms INTEGER DEFAULT 450,
    harvested_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Semantic Maps (Topic Ownership Graph)
CREATE TABLE IF NOT EXISTS public.semantic_maps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    pillar_keyword TEXT NOT NULL,
    node_type TEXT NOT NULL, -- question, entity, comparison, howto, local, temporal
    node_text TEXT NOT NULL,
    estimated_search_volume INTEGER DEFAULT 1000,
    currently_covered BOOLEAN DEFAULT FALSE,
    competitor_coverage_count INTEGER DEFAULT 0,
    priority_score FLOAT DEFAULT 50.0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 7. Entity Audit Logs
CREATE TABLE IF NOT EXISTS public.entity_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    entity_name TEXT NOT NULL,
    sitelinks_found BOOLEAN DEFAULT FALSE,
    knowledge_panel_found BOOLEAN DEFAULT FALSE,
    directory_citations JSONB DEFAULT '[]'::jsonb,
    publication_mentions JSONB DEFAULT '[]'::jsonb,
    schema_valid BOOLEAN DEFAULT TRUE,
    audit_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 8. Entity Citation Opportunities
CREATE TABLE IF NOT EXISTS public.entity_citation_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    citation_type TEXT DEFAULT 'directory', -- directory, crunchbase, wiki_gap, industry_index
    authority_score INTEGER DEFAULT 60,
    notes TEXT,
    status TEXT DEFAULT 'recommended', -- recommended, submitted, verified
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 9. SERP Snapshots (6h Algorithm & Volatility Detection)
CREATE TABLE IF NOT EXISTS public.serp_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    keyword TEXT NOT NULL,
    position INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    date_captured TIMESTAMPTZ DEFAULT now()
);

-- 10. Content Portfolio Snapshots (BCG Matrix Intelligence)
CREATE TABLE IF NOT EXISTS public.content_portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    content_id TEXT,
    title TEXT NOT NULL,
    url TEXT,
    target_keyword TEXT,
    position FLOAT DEFAULT 15.0,
    gsc_impressions_28d INTEGER DEFAULT 500,
    gsc_clicks_28d INTEGER DEFAULT 45,
    ga4_sessions INTEGER DEFAULT 120,
    ga4_avg_time_sec INTEGER DEFAULT 145,
    ga4_bounce_rate FLOAT DEFAULT 0.42,
    days_since_update INTEGER DEFAULT 30,
    internal_links_inbound INTEGER DEFAULT 4,
    backlinks_count INTEGER DEFAULT 2,
    word_count INTEGER DEFAULT 2200,
    portfolio_state TEXT DEFAULT 'Cash Cow', -- Star, Cash Cow, Question Mark, Dog, Ghost, Leaky Star, Hidden Gem
    conversion_data JSONB DEFAULT '{"goal_completions": 4, "conversion_rate": 0.033}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 11. Internal Link Graph
CREATE TABLE IF NOT EXISTS public.internal_link_graph (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    anchor_text TEXT NOT NULL,
    link_position TEXT DEFAULT 'body', -- header, body, footer, sidebar
    link_context TEXT,
    semantic_relevance_score FLOAT DEFAULT 0.85,
    pagerank_estimate FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 12. Agent Prompts (Self-Training Loop Module 1)
CREATE TABLE IF NOT EXISTS public.agent_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    created_date TIMESTAMPTZ DEFAULT now(),
    avg_quality_gate_score FLOAT DEFAULT 82.0,
    avg_expert_review_score FLOAT DEFAULT 80.0,
    avg_rank_improvement_30_days FLOAT DEFAULT 4.2,
    human_approval_rate FLOAT DEFAULT 0.92,
    status TEXT DEFAULT 'active' -- active, candidate, deprecated
);

-- 13. Agent Parameters (Self-Training Loop Module 3)
CREATE TABLE IF NOT EXISTS public.agent_parameters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    current_value TEXT NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT now(),
    performance_baseline JSONB DEFAULT '{}'::jsonb,
    notes TEXT
);

-- 14. Slack Message Log
CREATE TABLE IF NOT EXISTS public.slack_message_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    report_type TEXT NOT NULL, -- morning_brief, evening_summary, backlink_report, weekly_report, crisis_alert, new_learning
    channel TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT now(),
    message_summary TEXT,
    delivery_status TEXT DEFAULT 'sent', -- sent, failed
    payload JSONB DEFAULT '{}'::jsonb
);

-- 15. Pending Knowledge Updates (Living Knowledge Evolution)
CREATE TABLE IF NOT EXISTS public.pending_knowledge_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id TEXT NOT NULL DEFAULT 'default',
    chunk_id TEXT,
    title TEXT NOT NULL,
    original_content TEXT,
    contradicting_source_url TEXT,
    contradicting_content TEXT,
    severity TEXT DEFAULT 'medium', -- critical, high, medium, low
    status TEXT DEFAULT 'pending', -- pending, regenerated, dismissed
    created_at TIMESTAMPTZ DEFAULT now()
);
