"use client";

interface KeywordBadgeProps {
  query: string;
  impressions: number;
  ctr: number;
  active?: boolean;
}

export function KeywordBadge({ query, impressions, ctr, active = false }: KeywordBadgeProps) {
  return (
    <div className={`pill border border-ink px-3 py-1 inline-flex items-center gap-2 ${
      active ? "bg-ink text-paper" : "bg-stone"
    }`}>
      {active && <span className="w-2 h-2 bg-accent rounded-full" />}
      <span className="text-xs uppercase mono-font">{query}</span>
      <span className="text-[10px] text-muted mono-font">{impressions.toLocaleString()} IMP</span>
      <span className="text-[10px] text-muted mono-font"> / </span>
      <span className="text-[10px] text-muted mono-font">{(ctr * 100).toFixed(1)}% CTR</span>
    </div>
  );
}