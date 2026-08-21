"use client";

import { useState } from "react";

interface StatusPieChartProps {
  data?: { label: string; value: number; color: string }[];
}

const defaultData = [
  { label: "Pass", value: 60, color: "#FF4D12" },
  { label: "Fail", value: 25, color: "#111" },
  { label: "Pending", value: 15, color: "#6B6B6B" },
];

export function StatusPieChart({ data = defaultData }: StatusPieChartProps) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  
  let cumulative = 0;
  const radius = 15;
  const cx = 18;
  const cy = 18;
  const largeArcFlag = (radians: number) => (radians > Math.PI ? 1 : 0);
  
  const toRadians = (degrees: number) => (degrees * Math.PI) / 180;

  return (
    <div className="relative w-32 h-32">
      <svg viewBox="0 0 36 36" className="w-full h-full">
        {data.map((d, i) => {
          const startAngle = toRadians((cumulative / total) * 360);
          cumulative += d.value;
          const endAngle = toRadians((cumulative / total) * 360);
          
          const x1 = cx + radius * Math.cos(startAngle);
          const y1 = cy + radius * Math.sin(startAngle);
          const x2 = cx + radius * Math.cos(endAngle);
          const y2 = cy + radius * Math.sin(endAngle);
          
          const largeArc = largeArcFlag(endAngle - startAngle);
          
          const path = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;
          
          return (
            <g key={d.label}>
              <path
                d={path}
                fill={d.color}
                className="cursor-pointer"
                onMouseEnter={() => setHoverIndex(i)}
                onMouseLeave={() => setHoverIndex(null)}
              />
              {hoverIndex === i && (
                <rect x={20} y={4} width="60" height="50" fill="#111" stroke="#111">
                  <text x="30" y="18" fill="#fff" fontSize="10" className="mono-font">
                    {d.label}
                  </text>
                  <text x="30" y="32" fill="#fff" fontSize="10" className="mono-font">
                    {d.value}%
                  </text>
                </rect>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}