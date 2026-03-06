"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Settings2, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TrendItem } from "@/lib/api";

interface TrendChartProps {
  data: TrendItem[];
  onPeriodChange?: (period: string) => void;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload) return null;

  return (
    <div className="bg-gray-900 text-white rounded-lg px-3 py-2 text-xs shadow-lg">
      <p className="font-medium mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <p key={i} className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          {entry.name}: {entry.value.toLocaleString("es-ES")}EUR
        </p>
      ))}
    </div>
  );
}

// Demo data
const demoData: TrendItem[] = [
  { periodo: "Dom", ingresos: 320, gastos: 280, balance: 40 },
  { periodo: "Lun", ingresos: 450, gastos: 380, balance: 70 },
  { periodo: "Mar", ingresos: 584, gastos: 420, balance: 164 },
  { periodo: "Mie", ingresos: 390, gastos: 350, balance: 40 },
  { periodo: "Jue", ingresos: 480, gastos: 410, balance: 70 },
  { periodo: "Vie", ingresos: 520, gastos: 460, balance: 60 },
  { periodo: "Sab", ingresos: 280, gastos: 230, balance: 50 },
];

export default function TrendChart({
  data = demoData,
  onPeriodChange,
}: TrendChartProps) {
  const [period, setPeriod] = useState("Ultima semana");

  const total = data.reduce((sum, d) => sum + d.gastos, 0);
  const prevTotal = total * 0.92; // Simulated previous period
  const changePct = ((total - prevTotal) / prevTotal) * 100;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-gray-50 rounded-lg">
            <Settings2 className="w-4 h-4 text-gray-500" />
          </div>
          <h3 className="text-sm font-semibold text-gray-900">
            Tendencia de Gastos
          </h3>
        </div>
        <button className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors">
          {period}
          <ChevronDown className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Total */}
      <div className="mb-5">
        <div className="flex items-baseline gap-3">
          <span className="text-3xl font-bold text-gray-900">
            {total.toLocaleString("es-ES")}
          </span>
          <span
            className={cn(
              "text-sm font-medium",
              changePct >= 0 ? "text-red-500" : "text-emerald-500"
            )}
          >
            {changePct >= 0 ? "+" : ""}
            {changePct.toFixed(0)}% vs semana anterior
          </span>
        </div>
      </div>

      {/* Chart */}
      <div className="h-[280px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 5, right: 5, left: -20, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="#f0f0f0"
            />
            <XAxis
              dataKey="periodo"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 12, fill: "#9ca3af" }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 12, fill: "#9ca3af" }}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={total / data.length}
              stroke="#1F4E79"
              strokeDasharray="6 4"
              strokeWidth={1.5}
            />
            <Bar
              dataKey="gastos"
              name="Gastos"
              fill="#e5e7eb"
              radius={[4, 4, 0, 0]}
              activeBar={{ fill: "#1F4E79" }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
