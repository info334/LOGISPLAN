"use client";

import { useState } from "react";
import {
  FileDown,
  AlertTriangle,
  Truck,
  Receipt,
  BookOpen,
  MessageSquare,
  Search,
  LayoutList,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ActivityItem {
  tipo: string;
  descripcion: string;
  detalle: string;
  timestamp: string;
}

const iconMap: Record<string, React.ElementType> = {
  movimiento: FileDown,
  alerta: AlertTriangle,
  vehiculo: Truck,
  factura: Receipt,
  knowledge: BookOpen,
  feedback: MessageSquare,
};

const colorMap: Record<string, string> = {
  movimiento: "bg-blue-50 text-blue-600",
  alerta: "bg-red-50 text-red-600",
  vehiculo: "bg-emerald-50 text-emerald-600",
  factura: "bg-amber-50 text-amber-600",
  knowledge: "bg-purple-50 text-purple-600",
  feedback: "bg-yellow-50 text-yellow-600",
};

function formatTime(timestamp: string): string {
  if (!timestamp) return "";
  const d = new Date(timestamp);
  return d.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Demo data for initial render before API loads
const demoActivities: ActivityItem[] = [
  {
    tipo: "movimiento",
    descripcion: "Importacion CSV",
    detalle: "12 movimientos importados",
    timestamp: new Date().toISOString(),
  },
  {
    tipo: "alerta",
    descripcion: "SLA Rentabilidad",
    detalle: "Vehiculo MJC bajo 5%",
    timestamp: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    tipo: "factura",
    descripcion: "Factura procesada",
    detalle: "StarOil - MTY",
    timestamp: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    tipo: "vehiculo",
    descripcion: "Nuevo movimiento",
    detalle: "Peaje LVX - 45.20EUR",
    timestamp: new Date(Date.now() - 10800000).toISOString(),
  },
];

interface ActivityPanelProps {
  activities?: ActivityItem[];
}

export default function ActivityPanel({
  activities = demoActivities,
}: ActivityPanelProps) {
  const [filter, setFilter] = useState<"today" | "yesterday" | "week">(
    "today"
  );
  const [search, setSearch] = useState("");

  const filters = [
    { key: "today" as const, label: "Hoy" },
    { key: "yesterday" as const, label: "Ayer" },
    { key: "week" as const, label: "Esta semana" },
  ];

  const filtered = activities.filter((a) =>
    search
      ? a.descripcion.toLowerCase().includes(search.toLowerCase()) ||
        a.detalle.toLowerCase().includes(search.toLowerCase())
      : true
  );

  return (
    <aside className="fixed right-0 top-0 bottom-0 w-[320px] bg-white border-l border-gray-200 flex flex-col z-20">
      {/* Header */}
      <div className="flex items-center justify-between px-5 h-16 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-900">
          Ultimas Actualizaciones
        </h2>
        <button className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded transition-colors">
          <LayoutList className="w-4 h-4" />
        </button>
      </div>

      {/* Filters */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex gap-1 p-1 bg-gray-50 rounded-lg">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                "flex-1 py-1.5 text-xs font-medium rounded-md transition-colors",
                filter === f.key
                  ? "bg-brand-500 text-white shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Search */}
      <div className="px-4 pb-3">
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg text-sm">
          <Search className="w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar actividades"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 bg-transparent outline-none text-gray-600 placeholder:text-gray-400"
          />
        </div>
      </div>

      {/* Count */}
      <div className="px-5 pb-2">
        <p className="text-sm text-gray-500">
          <span className="font-semibold text-gray-900">{filtered.length}</span>{" "}
          actividades
        </p>
      </div>

      {/* Activity List */}
      <div className="flex-1 overflow-y-auto px-4 space-y-1">
        {filtered.map((item, i) => {
          const Icon = iconMap[item.tipo] || FileDown;
          const colors = colorMap[item.tipo] || "bg-gray-50 text-gray-600";

          return (
            <div
              key={i}
              className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer"
            >
              <div
                className={cn(
                  "w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0",
                  colors
                )}
              >
                <Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900">
                  {item.descripcion}
                </p>
                <p className="text-xs text-gray-500 truncate">{item.detalle}</p>
              </div>
              <span className="text-[11px] text-gray-400 flex-shrink-0">
                {formatTime(item.timestamp)}
              </span>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
