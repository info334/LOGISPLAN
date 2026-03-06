"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, Truck, RefreshCw, TrendingUp, TrendingDown, Fuel, Users, MoreHorizontal } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
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

const VEHICLE_COLORS: Record<string, { bg: string; text: string; ring: string }> = {
  MTY: { bg: "bg-blue-50", text: "text-blue-700", ring: "ring-blue-200" },
  LVX: { bg: "bg-emerald-50", text: "text-emerald-700", ring: "ring-emerald-200" },
  MJC: { bg: "bg-purple-50", text: "text-purple-700", ring: "ring-purple-200" },
  MLB: { bg: "bg-amber-50", text: "text-amber-700", ring: "ring-amber-200" },
};

const DONUT_COLORS = {
  gasoil: "#f59e0b",
  salario: "#6366f1",
  otros: "#94a3b8",
};

interface MesData {
  ingresos: number;
  gastos: number;
  gasoil: number;
  salario: number;
  otros: number;
  neto: number;
  margen_pct: number;
  km: number;
  coste_km: number | null;
}

interface VehiculoRow {
  vehiculo_id: string;
  meses: Record<string, MesData>;
}

function MiniDonut({ gasoil, salario, otros }: { gasoil: number; salario: number; otros: number }) {
  const total = gasoil + salario + otros;
  if (total === 0) return <span className="text-xs text-gray-300">-</span>;

  const data = [
    { name: "Gasoil", value: gasoil, color: DONUT_COLORS.gasoil },
    { name: "Salario", value: salario, color: DONUT_COLORS.salario },
    { name: "Otros", value: otros, color: DONUT_COLORS.otros },
  ].filter((d) => d.value > 0);

  return (
    <div className="w-12 h-12 mx-auto">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={12}
            outerRadius={22}
            dataKey="value"
            strokeWidth={0}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function CostCell({ d }: { d: MesData }) {
  const gastos = d.gastos;
  if (gastos === 0 && d.ingresos === 0) {
    return (
      <td className="px-2 py-3 text-center">
        <span className="text-xs text-gray-300">-</span>
      </td>
    );
  }

  const isPositive = d.neto >= 0;

  return (
    <td className="px-2 py-3">
      <div className="space-y-1.5">
        {/* Margen bruto */}
        <div className="text-center">
          <p className="text-xs font-bold text-gray-900">{formatImporte(d.neto)}</p>
          <div className="flex items-center justify-center gap-0.5">
            {isPositive ? (
              <TrendingUp className="w-2.5 h-2.5 text-emerald-500" />
            ) : (
              <TrendingDown className="w-2.5 h-2.5 text-red-500" />
            )}
            <span className={cn("text-[10px] font-semibold", isPositive ? "text-emerald-600" : "text-red-600")}>
              {d.margen_pct > 0 ? "+" : ""}{d.margen_pct.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Coste/km */}
        <div className="text-center">
          {d.coste_km !== null ? (
            <span className="text-[10px] font-medium text-gray-500">
              {d.coste_km.toFixed(2)} EUR/km
            </span>
          ) : (
            <span className="text-[10px] text-gray-300">sin km</span>
          )}
        </div>

        {/* Mini donut */}
        <MiniDonut gasoil={d.gasoil} salario={d.salario} otros={d.otros} />

        {/* Percentages below donut */}
        {gastos > 0 && (
          <div className="flex justify-center gap-1.5 text-[9px]">
            {d.gasoil > 0 && (
              <span className="text-amber-600 font-medium">{Math.round((d.gasoil / gastos) * 100)}%</span>
            )}
            {d.salario > 0 && (
              <span className="text-indigo-600 font-medium">{Math.round((d.salario / gastos) * 100)}%</span>
            )}
            {d.otros > 0 && (
              <span className="text-slate-500 font-medium">{Math.round((d.otros / gastos) * 100)}%</span>
            )}
          </div>
        )}
      </div>
    </td>
  );
}

function calcYtd(veh: VehiculoRow, meses: string[]): MesData {
  let ingresos = 0, gastos = 0, gasoil = 0, salario = 0, otros = 0, km = 0;
  for (const mes of meses) {
    const d = veh.meses[mes];
    if (d) {
      ingresos += d.ingresos;
      gastos += d.gastos;
      gasoil += d.gasoil;
      salario += d.salario;
      otros += d.otros;
      km += d.km;
    }
  }
  const neto = ingresos - gastos;
  const margen = ingresos > 0 ? (neto / ingresos) * 100 : 0;
  const coste_km = km > 0 ? gastos / km : null;
  return { ingresos, gastos, gasoil, salario, otros, neto, margen_pct: Math.round(margen * 10) / 10, km, coste_km: coste_km !== null ? Math.round(coste_km * 100) / 100 : null };
}

export default function CostesPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["costes-matriz"],
    queryFn: api.dashboard.costesMatriz,
  });

  const vehiculos: VehiculoRow[] = data?.vehiculos ?? [];
  const meses: string[] = data?.meses ?? [];

  // Grand totals
  const grandYtd = vehiculos.length > 0
    ? (() => {
        let ingresos = 0, gastos = 0, gasoil = 0, salario = 0, otros = 0, km = 0;
        for (const veh of vehiculos) {
          const ytd = calcYtd(veh, meses);
          ingresos += ytd.ingresos;
          gastos += ytd.gastos;
          gasoil += ytd.gasoil;
          salario += ytd.salario;
          otros += ytd.otros;
          km += ytd.km;
        }
        const neto = ingresos - gastos;
        const margen = ingresos > 0 ? (neto / ingresos) * 100 : 0;
        const coste_km = km > 0 ? gastos / km : null;
        return { ingresos, gastos, gasoil, salario, otros, neto, margen_pct: Math.round(margen * 10) / 10, km, coste_km };
      })()
    : { ingresos: 0, gastos: 0, gasoil: 0, salario: 0, otros: 0, neto: 0, margen_pct: 0, km: 0, coste_km: null };

  return (
    <div className="min-h-screen">
      <Header
        title="Costes"
        breadcrumbs={[{ label: "Analisis" }, { label: "Costes" }]}
      />

      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Analisis de Costes</h1>
            <p className="text-sm text-gray-500 mt-1">
              Margen bruto, coste/km y desglose por categoria (gasoil, salario, otros) por vehiculo y mes.
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Summary KPIs */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Margen Bruto</p>
            <p className="text-2xl font-bold text-gray-900">{formatImporte(grandYtd.neto)}</p>
            <div className="flex items-center gap-1 mt-1">
              {grandYtd.margen_pct >= 0 ? (
                <TrendingUp className="w-3 h-3 text-emerald-500" />
              ) : (
                <TrendingDown className="w-3 h-3 text-red-500" />
              )}
              <span className={cn("text-sm font-semibold", grandYtd.margen_pct >= 0 ? "text-emerald-600" : "text-red-600")}>
                {grandYtd.margen_pct > 0 ? "+" : ""}{grandYtd.margen_pct.toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Coste/km medio</p>
            <p className="text-2xl font-bold text-gray-900">
              {grandYtd.coste_km !== null ? `${grandYtd.coste_km.toFixed(2)} EUR` : "N/A"}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              {grandYtd.km > 0 ? `${grandYtd.km.toLocaleString("es-ES")} km totales` : "Sin datos de km"}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Gastos Totales</p>
            <p className="text-2xl font-bold text-gray-900">{formatImporte(grandYtd.gastos)}</p>
            <p className="text-xs text-gray-400 mt-1">vs {formatImporte(grandYtd.ingresos)} ingresos</p>
          </div>

          <div className="bg-white rounded-xl border border-gray-100 p-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Desglose</p>
            <div className="flex items-center gap-3 mt-1">
              <MiniDonut gasoil={grandYtd.gasoil} salario={grandYtd.salario} otros={grandYtd.otros} />
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-amber-500" />
                  <span className="text-xs text-gray-600">
                    Gasoil {grandYtd.gastos > 0 ? `${Math.round((grandYtd.gasoil / grandYtd.gastos) * 100)}%` : "-"}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-indigo-500" />
                  <span className="text-xs text-gray-600">
                    Salario {grandYtd.gastos > 0 ? `${Math.round((grandYtd.salario / grandYtd.gastos) * 100)}%` : "-"}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-slate-400" />
                  <span className="text-xs text-gray-600">
                    Otros {grandYtd.gastos > 0 ? `${Math.round((grandYtd.otros / grandYtd.gastos) * 100)}%` : "-"}
                  </span>
                </div>
              </div>
            </div>
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
              <Fuel className="w-10 h-10 mb-3 text-gray-300" />
              <p className="text-sm font-medium text-gray-600">No hay datos de costes</p>
              <p className="text-xs text-gray-400 mt-1">Sincroniza gastos y configura km y costes laborales</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/50">
                    <th className="text-left text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider w-28">
                      Vehiculo
                    </th>
                    {meses.map((mes) => (
                      <th key={mes} className="text-center text-xs font-medium text-gray-400 px-2 py-3 uppercase tracking-wider min-w-[120px]">
                        {formatMesCorto(mes)}
                      </th>
                    ))}
                    <th className="text-center text-xs font-medium text-gray-400 px-3 py-3 uppercase tracking-wider min-w-[120px] bg-gray-100/50">
                      YTD
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {vehiculos.map((veh) => {
                    const colors = VEHICLE_COLORS[veh.vehiculo_id] || VEHICLE_COLORS.MTY;
                    const ytd = calcYtd(veh, meses);

                    return (
                      <tr key={veh.vehiculo_id} className="border-b border-gray-50 hover:bg-gray-50/30">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className={cn("w-7 h-7 rounded-lg flex items-center justify-center", colors.bg)}>
                              <Truck className={cn("w-3.5 h-3.5", colors.text)} />
                            </div>
                            <span className="text-sm font-bold text-gray-900">{veh.vehiculo_id}</span>
                          </div>
                        </td>

                        {meses.map((mes) => {
                          const d = veh.meses[mes];
                          if (!d) {
                            return (
                              <td key={mes} className="px-2 py-3 text-center">
                                <span className="text-xs text-gray-300">-</span>
                              </td>
                            );
                          }
                          return <CostCell key={mes} d={d} />;
                        })}

                        {/* YTD column */}
                        <td className="px-3 py-3 bg-gray-50/30">
                          <CostCell d={ytd} />
                        </td>
                      </tr>
                    );
                  })}

                  {/* Totals row */}
                  <tr className="bg-gray-50 border-t-2 border-gray-200">
                    <td className="px-4 py-3">
                      <span className="text-sm font-bold text-gray-700">TOTAL</span>
                    </td>
                    {meses.map((mes) => {
                      let ingresos = 0, gastos = 0, gasoil = 0, salario = 0, otros = 0, km = 0;
                      for (const veh of vehiculos) {
                        const d = veh.meses[mes];
                        if (d) {
                          ingresos += d.ingresos;
                          gastos += d.gastos;
                          gasoil += d.gasoil;
                          salario += d.salario;
                          otros += d.otros;
                          km += d.km;
                        }
                      }
                      const neto = ingresos - gastos;
                      const margen = ingresos > 0 ? (neto / ingresos) * 100 : 0;
                      const coste_km = km > 0 ? gastos / km : null;
                      const totMes: MesData = { ingresos, gastos, gasoil, salario, otros, neto, margen_pct: Math.round(margen * 10) / 10, km, coste_km: coste_km !== null ? Math.round(coste_km * 100) / 100 : null };

                      return <CostCell key={mes} d={totMes} />;
                    })}
                    <td className="px-3 py-3 bg-gray-100/50">
                      <CostCell d={{
                        ingresos: grandYtd.ingresos,
                        gastos: grandYtd.gastos,
                        gasoil: grandYtd.gasoil,
                        salario: grandYtd.salario,
                        otros: grandYtd.otros,
                        neto: grandYtd.neto,
                        margen_pct: grandYtd.margen_pct,
                        km: grandYtd.km,
                        coste_km: grandYtd.coste_km !== null ? Math.round(grandYtd.coste_km * 100) / 100 : null,
                      }} />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap items-center gap-5 text-xs text-gray-400">
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
            <span>Gasoil (combustible)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
            <span>Salario (costes laborales)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-slate-400" />
            <span>Otros (seguros, peajes, leasing...)</span>
          </div>
          <span className="text-gray-300">|</span>
          <span>Gastos COMUN prorrateados entre 4 vehiculos</span>
        </div>
      </div>
    </div>
  );
}
