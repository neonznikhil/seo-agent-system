"use client";

import { useState } from "react";

const data = [
  { day: "Mon", clicks: 120 },
  { day: "Tue", clicks: 150 },
  { day: "Wed", clicks: 180 },
  { day: "Thu", clicks: 140 },
  { day: "Fri", clicks: 200 },
  { day: "Sat", clicks: 170 },
  { day: "Sun", clicks: 210 },
];

export function ROILineChart() {
  const max = Math.max(...data.map((d) => d.clicks));
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const chartWidth = 400;
  const chartHeight = 150;
  const padding = 20;
  const plotWidth = chartWidth - padding * 2;
  const plotHeight = chartHeight - padding * 2;
  const yAxisMax = Math.ceil(max / 50) * 50;

  const xScale = (i: number) => padding + (i / (data.length - 1)) * plotWidth;
  const yScale = (value: number) => chartHeight - padding - (value / yAxisMax) * plotHeight;

  return (
    <div className="relative h-48 w-full">
      <svg className="w-full h-full" viewBox="0 0 400 150" preserveAspectRatio="none">
        <defs>
          <marker id="arrowHead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0 10 3.5 0 7" fill="#FF4D12" />
          </marker>
        </defs>
        
        <rect x="0" y="0" width="400" height="150" fill="none" stroke="none" />
        
        <line x1={padding} y1={chartHeight - padding} x2={chartWidth - padding} y2={chartHeight - padding} stroke="#D1CCC4" strokeWidth="1" strokeDasharray="4" />
        
        <line x1={padding} y1={padding} x2={padding} y2={chartHeight - padding} stroke="#D1CCC4" strokeWidth="1" strokeDasharray="4" />
        
        {data.map((d, i) => {
          const cx = xScale(i);
          const cy = yScale(d.clicks);
          return (
            <g key={d.day}>
              <circle
                cx={cx}
                cy={cy}
                r="4"
                fill="#FF4D12"
                className="cursor-pointer"
                onMouseEnter={() => setHoverIndex(i)}
                onMouseLeave={() => setHoverIndex(null)}
              />
              <text x={cx} y={cy - 8} textAnchor="middle" fill="#111" fontSize="10" className="mono-font">
                {d.clicks}
              </text>
            </g>
          );
        })}
        
        <polyline
          fill="none"
          stroke="#111"
          strokeWidth="2"
          points={data.map((d, i) => `${xScale(i)},${yScale(d.clicks)}`).join(" ")}
        />
        
        {hoverIndex !== null && (
          <g>
            <line x1={xScale(hoverIndex)} y1={padding} x2={xScale(hoverIndex)} y2={chartHeight - padding} stroke="#FF4D12" strokeWidth="1" strokeDasharray="4" />
            <rect x={chartWidth - padding - 80} y={padding} width="75" height="40" fill="#111" stroke="#111" />
            <text x={chartWidth - padding - 37} y={22} textAnchor="middle" fill="#fff" fontSize="10" className="mono-font">
              {data[hoverIndex].day}
            </text>
            <text x={chartWidth - padding - 37} y={38} textAnchor="middle" fill="#fff" fontSize="10" className="mono-font">
              {data[hoverIndex].clicks} clicks
            </text>
          </g>
        )}
        
        <text x={chartWidth / 2} y={chartHeight + 12} textAnchor="middle" fill="#6B6B6B" fontSize="10" className="mono-font">
          ROIs
        </text>
      </svg>
    </div>
  );
}