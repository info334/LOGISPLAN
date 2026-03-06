"use client";

import { useState } from "react";
import { Search, SlidersHorizontal, MoreVertical } from "lucide-react";
import { cn, formatImporte } from "@/lib/utils";
import type { MonitoringItem } from "@/lib/api";

interface MonitoringTableProps {
  data: MonitoringItem[];
}

const estadoBadge: Record<
  string,
  { label: string; className: string }
> = {
  perdidas: {
    label: "Perdidas",
    className: "bg-red-50 text-red-700 border-red-200",
  },
  bajo: {
    label: "Bajo",
    className: "bg-amber-50 text-amber-700 border-amber-200",
  },
  aceptable: {
    label: "Aceptable",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  bueno: {
    label: "Bueno",
    className: "bg-green-50 text-green-700 border-green-200",
  },
};

// Demo data
const demoData: MonitoringItem[] = [
  {
    vehiculo_id: "MTY",
    facturacion: 24500,
    resultado_neto: 3200,
    rentabilidad_pct: 13.1,
    estado: "aceptable",
    ultimo_movimiento: "2025-08-18",
    periodo: "Ene 2025 - Ago 2025",
  },
  {
    vehiculo_id: "LVX",
    facturacion: 18900,
    resultado_neto: -1200,
    rentabilidad_pct: -6.3,
    estado: "perdidas",
    ultimo_movimiento: "2025-08-19",
    periodo: "Ene 2025 - Ago 2025",
  },
  {
    vehiculo_id: "MJC",
    facturacion: 21300,
    resultado_neto: 1500,
    rentabilidad_pct: 7.0,
    estado: "bajo",
    ultimo_movimiento: "2025-08-19",
    periodo: "Ene 2025 - Ago 2025",
  },
  {
    vehiculo_id: "MLB",
    facturacion: 27800,
    resultado_neto: 6200,
    rentabilidad_pct: 22.3,
    estado: "bueno",
    ultimo_movimiento: "2025-08-20",
    periodo: "Ene 2025 - Ago 2025",
  },
];

export default function MonitoringTable({
  data = demoData,
}: MonitoringTableProps) {
  const [search, setSearch] = useState("");

  const filtered = data.filter(
    (row) =>
      !search ||
      row.vehiculo_id.toLowerCase().includes(search.toLowerCase()) ||
      row.estado.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="bg-white rounded-xl border border-gray-100">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-gray-900">
            Monitoreo de Flota
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg text-sm">
            <Search className="w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Vehiculo"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-transparent outline-none text-gray-600 placeholder:text-gray-400 w-24"
            />
          </div>
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors">
            <SlidersHorizontal className="w-3.5 h-3.5" />
            Filtrar
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-50">
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3">
                Vehiculo
              </th>
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3">
                Facturacion
              </th>
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3">
                Resultado
              </th>
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3">
                Rentabilidad
              </th>
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3">
                Estado
              </th>
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3">
                Ultimo Mov.
              </th>
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3">
                Periodo
              </th>
              <th className="w-10 px-3"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const badge = estadoBadge[row.estado] || estadoBadge.bajo;
              return (
                <tr
                  key={row.vehiculo_id}
                  className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-brand-50 rounded-full flex items-center justify-center text-brand-600 text-xs font-bold">
                        {row.vehiculo_id.slice(0, 2)}
                      </div>
                      <span className="text-sm font-medium text-gray-900">
                        {row.vehiculo_id}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-sm text-gray-600">
                    {formatImporte(row.facturacion)}
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={cn(
                        "text-sm font-medium",
                        row.resultado_neto >= 0
                          ? "text-emerald-600"
                          : "text-red-600"
                      )}
                    >
                      {formatImporte(row.resultado_neto)}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-sm text-gray-600">
                    {row.rentabilidad_pct.toFixed(1)}%
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={cn(
                        "inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-full border",
                        badge.className
                      )}
                    >
                      {badge.label}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-sm text-gray-500">
                    {row.ultimo_movimiento}
                  </td>
                  <td className="px-5 py-3.5 text-sm text-gray-500">
                    {row.periodo}
                  </td>
                  <td className="px-3 py-3.5">
                    <button className="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors">
                      <MoreVertical className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
