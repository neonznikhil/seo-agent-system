"use client";

import { useState } from "react";

interface BlogPreviewProps {
  title: string;
  content: string;
  faq?: { q: string; a: string }[];
  links?: { text: string; href: string }[];
  quality?: number;
}

export function BlogPreview({ title, content, faq = [], links = [], quality }: BlogPreviewProps) {
  const [openAccordion, setOpenAccordion] = useState<number | null>(null);

  return (
    <div className="bg-paper border border-ink">
      <div className="p-4">
        <div className="flex items-start gap-3 mb-4">
          {quality && (
            <span className="text-xl">✅</span>
          )}
          {title && (
            <h3 className="text-[20px] font-bold uppercase dot-font leading-tight">
              {title}
            </h3>
          )}
        </div>
        
        {!title && (
          <div className="text-xs text-muted uppercase tracking-wider mono-font mb-2">Blog Preview</div>
        )}
        
        {content && (
          <div className="text-sm leading-relaxed whitespace-pre-wrap mb-4">
            {content.slice(0, 400)}...
          </div>
        )}
        
        <div className="flex gap-2 mb-4 flex-wrap">
          <span className="pill border border-ink bg-stone text-[10px] mono-font">AEO</span>
          <span className="pill border border-ink bg-stone text-[10px] mono-font">Draft</span>
        </div>
      </div>
      
      {links && links.length > 0 && (
        <div className="border-t border-ink">
          <div className="px-4 pb-2">
            <div className="text-[10px] text-muted uppercase mono-font mb-2">INTERNAL LINKS</div>
          </div>
          <ul className="px-4 pb-3 space-y-2">
            {links.map((link, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="w-2 h-2 bg-accent rounded-full flex-shrink-0" />
                <span className="text-[11px] mono-font">{link.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {faq && faq.length > 0 && (
        <div className="border-t border-line">
          {faq.map((item, i) => (
            <div key={i}>
              <button
                onClick={() => setOpenAccordion(i)}
                className="w-full px-4 py-2 text-left text-sm font-bold border-b border-line flex justify-between items-center"
              >
                {item.q}
                <span className="text-[10px] text-muted mono-font">▼</span>
              </button>
              {openAccordion === i && (
                <div className="px-4 pb-3 text-sm text-muted mono-font">
                  {item.a}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      
      {!faq.length && !links.length && content && (
        <div className="border-t border-line">
          <div className="px-4 pb-2">
            <div className="text-[10px] text-muted uppercase mono-font mb-2">FAQ</div>
          </div>
          <div className="px-4 pb-3 text-sm text-muted mono-font">
            No FAQ items for this blog
          </div>
        </div>
      )}
    </div>
  );
}