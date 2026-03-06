"use client";

import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Loader2, Truck, RefreshCw } from "lucide-react";
import Header from "@/components/layout/header";
import { cn, formatImporte } from "@/lib/utils";
import { api } from "@/lib/api";

const MESES: Record<string, string> = {
  "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr",
  "05": "May", "06": "Jun", "07": "Jul", "08": "Ago",
  "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic",
};

function formatMesCorto(mes: string) {
  const [year, month] = mes.split("-");
  return `${MESES[month] || month} ${year.slice(2)}`;
}

const VEHICLE_COLORS: Record<string, { bg: string; bar: string; text: string }> = {
  MTY: { bg: "bg-blue-50", bar: "bg-blue-500", text: "text-blue-700" },
  LVX: { bg: "bg-emerald-50", bar: "bg-emerald-500", text: "text-emerald-700" },
  MJC: { bg: "bg-purple-50", bar: "bg-purple-500", text: "text-purple-700" },
  MLB: { bg: "bg-amber-50", bar: "bg-amber-500", text: "text-amber-700" },
};

interface MesData {
  ingresos: number;
  gastos: number;
  neto: number;
  margen_pct: number;
}

interface VehiculoRow {
  vehiculo_id: string;
  meses: Record<string, MesData>;
}

function ProgressBar({ value, max, neto, margen, color }: {
  value: number;
  max: number;
  neto: number;
  margen: number;
  color: { bg: string; bar: string; text: string };
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const isPositive = neto >= 0;

  return (
    <div className="space-y-1">
      {/* Progress bar with amount inside */}
      <div className="relative h-8 bg-gray-100 rounded-lg overflow-hidden">
        <div
          className={cn("absolute inset-y-0 left-0 rounded-lg transition-all duration-500", color.bar)}
          style={{ width: `${Math.max(pct, 8)}%`, opacity: 0.85 }}
        />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xs font-bold text-white drop-shadow-sm">
            {formatImporte(value)}
          </span>
        </div>
      </div>
      {/* Margin percentage */}
      <div className="flex items-center justify-center gap-1">
        {isPositive ? (
          <TrendingUp className="w-3 h-3 text-emerald-500" />
        ) : (
          <TrendingDown className="w-3 h-3 text-red-500" />
        )}
        <span className={cn(
          "text-xs font-semibold",
          isPositive ? "text-emerald-600" : "text-red-600"
        )}>
          {margen > 0 ? "+" : ""}{margen.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export default function RentabilidadPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["rentabilidad-matriz"],
    queryFn: api.dashboard.rentabilidadMatriz,
  });

  const vehiculos: VehiculoRow[] = data?.vehiculos ?? [];
  const meses: string[] = data?.meses ?? [];

  // Calculate max ingresos for scaling bars
  let maxIngresos = 0;
  for (const veh of vehiculos) {
    for (const mes of meses) {
      const d = veh.meses[mes];
      if (d && d.ingresos > maxIngresos) maxIngresos = d.ingresos;
    }
  }

  // Summary totals per vehicle
  const totales = vehiculos.map((veh) => {
    let ingresos = 0, gastos = 0;
    for (const mes of meses) {
      const d = veh.meses[mes];
      if (d) { ingresos += d.ingresos; gastos += d.gastos; }
    }
    const neto = ingresos - gastos;
    const margen = ingresos > 0 ? (neto / ingresos) * 100 : 0;
    return { vehiculo_id: veh.vehiculo_id, ingresos, gastos, neto, margen };
  });

  // Grand total
  const grandTotal = totales.reduce(
    (acc, t) => ({
      ingresos: acc.ingresos + t.ingresos,
      gastos: acc.gastos + t.gastos,
      neto: acc.neto + t.neto,
    }),
    { ingresos: 0, gastos: 0, neto: 0 }
  );
  const grandMargen = grandTotal.ingresos > 0 ? (grandTotal.neto / grandTotal.ingresos) * 100 : 0;

  return (
    <div className="min-h-screen">
      <Header
        title="Rentabilidad"
        breadcrumbs={[{ label: "Analisis" }, { label: "Rentabilidad" }]}
      />

      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Rentabilidad por Vehiculo</h1>
            <p className="text-sm text-gray-500 mt-1">
              Ingresos vs gastos por vehiculo y mes. La barra muestra ingresos, el porcentaje es el margen neto.
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          {totales.map((t) => {
            const colors = VEHICLE_COLORS[t.vehiculo_id] || VEHICLE_COLORS.MTY;
            return (
              <div key={t.vehiculo_id} className={cn("rounded-xl border p-4", colors.bg, "border-gray-100")}>
                <div className="flex items-center gap-2 mb-3">
                  <Truck className={cn("w-5 h-5", colors.text)} />
                  <span className={cn("text-sm font-bold", colors.text)}>{t.vehiculo_id}</span>
                </div>
                <p className="text-xl font-bold text-gray-900">{formatImporte(t.neto)}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-gray-500">Ingresos: {formatImporte(t.ingresos)}</span>
                </div>
                <div className="flex items-center gap-1 mt-1">
                  {t.margen >= 0 ? (
                    <TrendingUp className="w-3 h-3 text-emerald-500" />
                  ) : (
                    <TrendingDown className="w-3 h-3 text-red-500" />
                  )}
                  <span className={cn("text-sm font-semibold", t.margen >= 0 ? "text-emerald-600" : "text-red-600")}>
                    {t.margen > 0 ? "+" : ""}{t.margen.toFixed(1)}% margen
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Grand total bar */}
        <div className="bg-white rounded-xl border border-gray-100 p-4 mb-6 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium text-gray-500">Total flota</span>
            <span className="text-lg font-bold text-gray-900">{formatImporte(grandTotal.ingresos)}</span>
            <span className="text-sm text-gray-400">ingresos</span>
            <span className="text-lg font-bold text-gray-600">{formatImporte(grandTotal.gastos)}</span>
            <span className="text-sm text-gray-400">gastos</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-gray-900">{formatImporte(grandTotal.neto)}</span>
            <span className={cn(
              "px-2 py-1 rounded-md text-sm font-bold",
              grandMargen >= 0 ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
            )}>
              {grandMargen > 0 ? "+" : ""}{grandMargen.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Matrix table */}
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
            </div>
          ) : meses.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <TrendingUp className="w-10 h-10 mb-3 text-gray-300" />
              <p className="text-sm font-medium text-gray-600">No hay datos de facturacion</p>
              <p className="text-xs text-gray-400 mt-1">Sincroniza facturas desde Integraciones</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/50">
                    <th className="text-left text-xs font-medium text-gray-400 px-5 py-3 uppercase tracking-wider w-32">
                      Vehiculo
                    </th>
                    {meses.map((mes) => (
                      <th key={mes} className="text-center text-xs font-medium text-gray-400 px-3 py-3 uppercase tracking-wider min-w-[140px]">
                        {formatMesCorto(mes)}
                      </th>
                    ))}
                    <th className="text-center text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider min-w-[140px] bg-gray-100/50">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {vehiculos.map((veh) => {
                    const colors = VEHICLE_COLORS[veh.vehiculo_id] || VEHICLE_COLORS.MTY;
                    const total = totales.find((t) => t.vehiculo_id === veh.vehiculo_id)!;

                    return (
                      <tr key={veh.vehiculo_id} className="border-b border-gray-50 hover:bg-gray-50/30">
                        {/* Vehicle label */}
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-2">
                            <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", colors.bg)}>
                              <Truck className={cn("w-4 h-4", colors.text)} />
                            </div>
                            <span className="text-sm font-bold text-gray-900">{veh.vehiculo_id}</span>
                          </div>
                        </td>

                        {/* Month cells */}
                        {meses.map((mes) => {
                          const d = veh.meses[mes];
                          if (!d || d.ingresos === 0) {
                            return (
                              <td key={mes} className="px-3 py-4 text-center">
                                <span className="text-xs text-gray-300">-</span>
                              </td>
                            );
                          }
                          return (
                            <td key={mes} className="px-3 py-4">
                              <ProgressBar
                                value={d.ingresos}
                                max={maxIngresos}
                                neto={d.neto}
                                margen={d.margen_pct}
                                color={colors}
                              />
                            </td>
                          );
                        })}

                        {/* Total column */}
                        <td className="px-4 py-4 bg-gray-50/30">
                          <div className="text-center space-y-1">
                            <p className="text-sm font-bold text-gray-900">{formatImporte(total.ingresos)}</p>
                            <div className="flex items-center justify-center gap-1">
                              {total.margen >= 0 ? (
                                <TrendingUp className="w-3 h-3 text-emerald-500" />
                              ) : (
                                <TrendingDown className="w-3 h-3 text-red-500" />
                              )}
                              <span className={cn(
                                "text-xs font-bold",
                                total.margen >= 0 ? "text-emerald-600" : "text-red-600"
                              )}>
                                {total.margen > 0 ? "+" : ""}{total.margen.toFixed(1)}%
                              </span>
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  })}

                  {/* Totals row */}
                  <tr className="bg-gray-50 border-t-2 border-gray-200">
                    <td className="px-5 py-4">
                      <span className="text-sm font-bold text-gray-700">TOTAL</span>
                    </td>
                    {meses.map((mes) => {
                      let ingMes = 0, gasMes = 0;
                      for (const veh of vehiculos) {
                        const d = veh.meses[mes];
                        if (d) { ingMes += d.ingresos; gasMes += d.gastos; }
                      }
                      const netoMes = ingMes - gasMes;
                      const margenMes = ingMes > 0 ? (netoMes / ingMes) * 100 : 0;

                      return (
                        <td key={mes} className="px-3 py-4 text-center">
                          {ingMes > 0 ? (
                            <div className="space-y-1">
                              <p className="text-xs font-bold text-gray-700">{formatImporte(ingMes)}</p>
                              <span className={cn(
                                "text-xs font-semibold",
                                margenMes >= 0 ? "text-emerald-600" : "text-red-600"
                              )}>
                                {margenMes > 0 ? "+" : ""}{margenMes.toFixed(1)}%
                              </span>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-300">-</span>
                          )}
                        </td>
                      );
                    })}
                    <td className="px-4 py-4 bg-gray-100/50 text-center">
                      <p className="text-sm font-bold text-gray-900">{formatImporte(grandTotal.ingresos)}</p>
                      <span className={cn(
                        "text-xs font-bold",
                        grandMargen >= 0 ? "text-emerald-600" : "text-red-600"
                      )}>
                        {grandMargen > 0 ? "+" : ""}{grandMargen.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="mt-4 flex items-center gap-6 text-xs text-gray-400">
          <span>Barra = ingresos (facturacion con IVA)</span>
          <span>% = margen neto (ingresos - gastos) / ingresos</span>
          <span>Gastos = directos + COMUN prorrateado entre 4 vehiculos</span>
        </div>
      </div>
    </div>
  );
}
