"use client";

import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, LucideIcon } from "lucide-react";

interface KpiCardProps {
  title: string;
  value: string;
  change?: number;
  changeLabel?: string;
  icon: LucideIcon;
  iconColor?: string;
  sparklineData?: number[];
}

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length < 2) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const width = 80;
  const height = 32;
  const padding = 2;

  const points = data
    .map((v, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2);
      const y =
        height - padding - ((v - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="flex-shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function KpiCard({
  title,
  value,
  change,
  changeLabel,
  icon: Icon,
  iconColor = "text-brand-500",
  sparklineData,
}: KpiCardProps) {
  const isPositive = change !== undefined && change >= 0;
  const sparkColor = isPositive ? "#10b981" : "#ef4444";

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <div
          className={cn(
            "p-1.5 rounded-lg bg-gray-50",
            iconColor
          )}
        >
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="flex items-end justify-between">
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {change !== undefined && (
            <div className="flex items-center gap-1 mt-1.5">
              {isPositive ? (
                <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5 text-red-500" />
              )}
              <span
                className={cn(
                  "text-xs font-medium",
                  isPositive ? "text-emerald-600" : "text-red-600"
                )}
              >
                {isPositive ? "+" : ""}
                {change.toFixed(1)}%
              </span>
              {changeLabel && (
                <span className="text-xs text-gray-400 ml-1">
                  {changeLabel}
                </span>
              )}
            </div>
          )}
        </div>

        {sparklineData && (
          <MiniSparkline data={sparklineData} color={sparkColor} />
        )}
      </div>
    </div>
  );
}
