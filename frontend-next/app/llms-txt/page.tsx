"use client";

import { useEffect, useState } from "react";
import { get } from "@/lib/api";
import { getCurrentWebsiteId } from "@/lib/website";

export default function LlmsTxtPage() {
  const [llmsData, setLlmsData] = useState<{ daysLeft: number; blogsReady: number; content: string } | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchLlmsTxtData() {
      try {
        setLoading(true);
        const websiteId = getCurrentWebsiteId();
        const data = await get(`/llms-txt/${websiteId}`);
        if (data) {
          // Calculate days left until next update
          const nextDue = new Date(data.next_due);
          const now = new Date();
          const daysLeft = Math.max(0, Math.ceil((nextDue.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)));
          
          // Calculate blogs ready from approved content in content_log
          const blogsReady = data.blogs_ready ?? 0;
          
          setLlmsData({
            daysLeft,
            blogsReady,
            content: data.content || `# LLMs.txt - RankForge SEO Agent System\n\n## Instructions for AI Crawlers\n\nThis is the LLMs.txt file for the RankForge autonomous SEO agent system.\n\n## Agents\n- writer_agent: Creates blog content\n- knowledge_agent: Gathers insights\n- backlink_agent: Builds links\n\n## Output Format\nAll blog content follows this structure:\n1. H1: Primary keyword\n2. H2: Related topics\n3. H3: Subtopics\n4. Conclusion with CTA\n\n## Resources\n- API: /api/blog/generate\n- Docs: /docs/seo-guidelines\n- Templates: /templates/blog`
          });
        } else {
          setLlmsData(null);
        }
        setError(null);
      } catch (err) {
        setError("Backend not running - run uvicorn main:app --reload in backend");
        setLlmsData(null);
      } finally {
        setLoading(false);
      }
    }

    fetchLlmsTxtData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">LLMS.TXT</h1>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">NEXT BATCH IN</div>
          <div className="flex items-center justify-center py-8">
            <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
          </div>
        </div>

        <div className="bg-paper border border-ink p-4">
          <div className="flex items-center justify-center h-96">
            <div className="w-4 h-4 border-2 border-ink border-t-transparent rounded-full animate-spin" />
          </div>
        </div>

        <div className="flex gap-2">
          <button
            className="flex items-center gap-2 px-4 py-2 bg-ink text-paper text-[11px] uppercase tracking-widest mono-font"
            disabled
          >
            <span className="w-2 h-2 bg-accent" />
            Approve
          </button>
          <button
            className="px-4 py-2 border border-ink text-[11px] uppercase tracking-widest mono-font pill"
            disabled
          >
            Preview
          </button>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">LLMS.TXT</h1>
        </div>

        <div className="bg-stone border border-ink p-4">
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">NEXT BATCH IN</div>
          <div className="text-[11px] text-ink mono-font text-center">
            {error}
          </div>
        </div>

        <div className="bg-paper border border-ink p-4">
          <div className="flex items-center justify-center h-96">
            <div className="text-[11px] text-ink mono-font">Backend offline</div>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            className="flex items-center gap-2 px-4 py-2 bg-ink text-paper text-[11px] uppercase tracking-widest mono-font"
            disabled
          >
            <span className="w-2 h-2 bg-accent" />
            Approve
          </button>
          <button
            className="px-4 py-2 border border-ink text-[11px] uppercase tracking-widest mono-font pill"
            disabled
          >
            Preview
          </button>
        </div>
      </div>
    );
  }

  if (!llmsData) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <h1 className="text-3xl font-bold dot-font">LLMS.TXT</h1>
        </div>
        <div className="bg-stone border border-ink p-4 text-center">
          <div className="text-[11px] text-ink mono-font">No data available</div>
        </div>
      </div>
    );
  }

  const { daysLeft, blogsReady, content } = llmsData;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-3xl font-bold dot-font">LLMS.TXT</h1>
      </div>

      <div className="bg-stone border border-ink p-4">
        <div className="text-xs text-muted uppercase tracking-wider mono-font mb-3">NEXT BATCH IN</div>
        <div className="text-2xl mono-font">
          <span className="text-3xl font-bold dot-font">{daysLeft}</span>
          <span className="text-muted mx-1">/</span>
          <span className="text-muted">{blogsReady} blogs</span>
        </div>
      </div>

      <div className="bg-paper border border-ink p-4">
        <pre className="text-[11px] mono-font whitespace-pre-wrap">
          <code>{content}</code>
        </pre>
      </div>

      <div className="flex gap-2">
        <button className="flex items-center gap-2 px-4 py-2 bg-ink text-paper text-[11px] uppercase tracking-widest mono-font">
          <span className="w-2 h-2 bg-accent" />
          Approve
        </button>
        <button className="px-4 py-2 border border-ink text-[11px] uppercase tracking-widest mono-font pill">
          Preview
        </button>
      </div>
    </div>
  );
}