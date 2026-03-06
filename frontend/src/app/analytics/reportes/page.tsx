"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, Truck, TrendingUp, TrendingDown, RefreshCw, Gauge, Package, Building2 } from "lucide-react";
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

const VEHICLE_COLORS: Record<string, { bg: string; text: string }> = {
  MTY: { bg: "bg-blue-50", text: "text-blue-700" },
  LVX: { bg: "bg-emerald-50", text: "text-emerald-700" },
  MJC: { bg: "bg-purple-50", text: "text-purple-700" },
  MLB: { bg: "bg-amber-50", text: "text-amber-700" },
};

const CAMIONES = ["LVX", "MJC", "MTY"];

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

function MargenBadge({ value }: { value: number }) {
  const isPositive = value >= 0;
  return (
    <span className={cn(
      "inline-flex items-center gap-0.5 text-xs font-bold px-1.5 py-0.5 rounded",
      isPositive ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
    )}>
      {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {value > 0 ? "+" : ""}{value.toFixed(1)}%
    </span>
  );
}

function sumVehiculos(vehiculos: VehiculoRow[], ids: string[], meses: string[]) {
  const byMes: Record<string, MesData> = {};
  let totIng = 0, totGas = 0, totKm = 0;

  for (const mes of meses) {
    let ingresos = 0, gastos = 0, gasoil = 0, salario = 0, otros = 0, km = 0;
    for (const veh of vehiculos) {
      if (!ids.includes(veh.vehiculo_id)) continue;
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
    byMes[mes] = {
      ingresos: Math.round(ingresos * 100) / 100,
      gastos: Math.round(gastos * 100) / 100,
      gasoil: Math.round(gasoil * 100) / 100,
      salario: Math.round(salario * 100) / 100,
      otros: Math.round(otros * 100) / 100,
      neto: Math.round(neto * 100) / 100,
      margen_pct: Math.round(margen * 10) / 10,
      km,
      coste_km: coste_km !== null ? Math.round(coste_km * 100) / 100 : null,
    };
    totIng += ingresos;
    totGas += gastos;
    totKm += km;
  }

  const totNeto = totIng - totGas;
  const totMargen = totIng > 0 ? (totNeto / totIng) * 100 : 0;
  const totCosteKm = totKm > 0 ? totGas / totKm : null;
  const ytd: MesData = {
    ingresos: Math.round(totIng * 100) / 100,
    gastos: Math.round(totGas * 100) / 100,
    gasoil: 0, salario: 0, otros: 0,
    neto: Math.round(totNeto * 100) / 100,
    margen_pct: Math.round(totMargen * 10) / 10,
    km: totKm,
    coste_km: totCosteKm !== null ? Math.round(totCosteKm * 100) / 100 : null,
  };

  return { byMes, ytd };
}

/* ─── Coste/km Table ─── */
function CosteKmSection({ vehiculos, meses }: { vehiculos: VehiculoRow[]; meses: string[] }) {
  const allIds = vehiculos.map((v) => v.vehiculo_id);
  const totals = sumVehiculos(vehiculos, allIds, meses);

  return (
    <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-orange-50 flex items-center justify-center">
          <Gauge className="w-4 h-4 text-orange-600" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-gray-900">Coste por Kilometro</h3>
          <p className="text-xs text-gray-400">Gastos totales / km recorridos por vehiculo y mes</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-2.5 uppercase tracking-wider w-28">Vehiculo</th>
              {meses.map((mes) => (
                <th key={mes} className="text-center text-xs font-medium text-gray-400 px-3 py-2.5 uppercase tracking-wider">{formatMesCorto(mes)}</th>
              ))}
              <th className="text-center text-xs font-medium text-gray-400 px-4 py-2.5 uppercase tracking-wider bg-gray-100/50">YTD</th>
            </tr>
          </thead>
          <tbody>
            {vehiculos.map((veh) => {
              const colors = VEHICLE_COLORS[veh.vehiculo_id] || VEHICLE_COLORS.MTY;
              const vehTot = sumVehiculos(vehiculos, [veh.vehiculo_id], meses);
              return (
                <tr key={veh.vehiculo_id} className="border-b border-gray-50 hover:bg-gray-50/30">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className={cn("w-6 h-6 rounded-md flex items-center justify-center", colors.bg)}>
                        <Truck className={cn("w-3 h-3", colors.text)} />
                      </div>
                      <span className="text-sm font-bold text-gray-900">{veh.vehiculo_id}</span>
                    </div>
                  </td>
                  {meses.map((mes) => {
                    const d = veh.meses[mes];
                    return (
                      <td key={mes} className="px-3 py-3 text-center">
                        {d && d.coste_km !== null ? (
                          <div>
                            <span className="text-sm font-bold text-gray-900">{d.coste_km.toFixed(2)}</span>
                            <span className="text-[10px] text-gray-400 ml-0.5">EUR/km</span>
                            <p className="text-[10px] text-gray-400">{d.km.toLocaleString("es-ES")} km</p>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-300">-</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-4 py-3 text-center bg-gray-50/30">
                    {vehTot.ytd.coste_km !== null ? (
                      <div>
                        <span className="text-sm font-bold text-gray-900">{vehTot.ytd.coste_km.toFixed(2)}</span>
                        <span className="text-[10px] text-gray-400 ml-0.5">EUR/km</span>
                        <p className="text-[10px] text-gray-400">{vehTot.ytd.km.toLocaleString("es-ES")} km</p>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-300">-</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {/* Total row */}
            <tr className="bg-gray-50 border-t-2 border-gray-200">
              <td className="px-5 py-3"><span className="text-sm font-bold text-gray-700">TOTAL</span></td>
              {meses.map((mes) => {
                const d = totals.byMes[mes];
                return (
                  <td key={mes} className="px-3 py-3 text-center">
                    {d && d.coste_km !== null ? (
                      <div>
                        <span className="text-sm font-bold text-gray-700">{d.coste_km.toFixed(2)}</span>
                        <span className="text-[10px] text-gray-400 ml-0.5">EUR/km</span>
                        <p className="text-[10px] text-gray-400">{d.km.toLocaleString("es-ES")} km</p>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-300">-</span>
                    )}
                  </td>
                );
              })}
              <td className="px-4 py-3 text-center bg-gray-100/50">
                {totals.ytd.coste_km !== null ? (
                  <div>
                    <span className="text-sm font-bold text-gray-700">{totals.ytd.coste_km.toFixed(2)}</span>
                    <span className="text-[10px] text-gray-400 ml-0.5">EUR/km</span>
                    <p className="text-[10px] text-gray-400">{totals.ytd.km.toLocaleString("es-ES")} km</p>
                  </div>
                ) : (
                  <span className="text-xs text-gray-300">-</span>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── Beneficios Table ─── */
function BeneficiosSection({
  title, subtitle, icon, iconBg, iconColor, vehiculos, ids, meses,
}: {
  title: string; subtitle: string;
  icon: React.ReactNode;
  iconBg: string; iconColor: string;
  vehiculos: VehiculoRow[]; ids: string[]; meses: string[];
}) {
  const filtered = vehiculos.filter((v) => ids.includes(v.vehiculo_id));
  const totals = sumVehiculos(vehiculos, ids, meses);

  return (
    <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
        <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", iconBg)}>
          {icon}
        </div>
        <div>
          <h3 className="text-sm font-bold text-gray-900">{title}</h3>
          <p className="text-xs text-gray-400">{subtitle}</p>
        </div>
        {/* YTD summary badge */}
        <div className="ml-auto flex items-center gap-3">
          <span className="text-lg font-bold text-gray-900">{formatImporte(totals.ytd.neto)}</span>
          <MargenBadge value={totals.ytd.margen_pct} />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-2.5 uppercase tracking-wider w-28">Vehiculo</th>
              {meses.map((mes) => (
                <th key={mes} className="text-center text-xs font-medium text-gray-400 px-3 py-2.5 uppercase tracking-wider">{formatMesCorto(mes)}</th>
              ))}
              <th className="text-center text-xs font-medium text-gray-400 px-4 py-2.5 uppercase tracking-wider bg-gray-100/50">YTD</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((veh) => {
              const colors = VEHICLE_COLORS[veh.vehiculo_id] || VEHICLE_COLORS.MTY;
              const vehTot = sumVehiculos(vehiculos, [veh.vehiculo_id], meses);
              return (
                <tr key={veh.vehiculo_id} className="border-b border-gray-50 hover:bg-gray-50/30">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className={cn("w-6 h-6 rounded-md flex items-center justify-center", colors.bg)}>
                        <Truck className={cn("w-3 h-3", colors.text)} />
                      </div>
                      <span className="text-sm font-bold text-gray-900">{veh.vehiculo_id}</span>
                    </div>
                  </td>
                  {meses.map((mes) => {
                    const d = veh.meses[mes];
                    if (!d || (d.ingresos === 0 && d.gastos === 0)) {
                      return <td key={mes} className="px-3 py-3 text-center"><span className="text-xs text-gray-300">-</span></td>;
                    }
                    return (
                      <td key={mes} className="px-3 py-3 text-center">
                        <div className="space-y-0.5">
                          <p className={cn("text-sm font-bold", d.neto >= 0 ? "text-gray-900" : "text-red-600")}>{formatImporte(d.neto)}</p>
                          <MargenBadge value={d.margen_pct} />
                          <div className="text-[10px] text-gray-400 space-y-0">
                            <p>Ing: {formatImporte(d.ingresos)}</p>
                            <p>Gas: {formatImporte(d.gastos)}</p>
                          </div>
                        </div>
                      </td>
                    );
                  })}
                  <td className="px-4 py-3 text-center bg-gray-50/30">
                    <div className="space-y-0.5">
                      <p className={cn("text-sm font-bold", vehTot.ytd.neto >= 0 ? "text-gray-900" : "text-red-600")}>{formatImporte(vehTot.ytd.neto)}</p>
                      <MargenBadge value={vehTot.ytd.margen_pct} />
                      <div className="text-[10px] text-gray-400">
                        <p>Ing: {formatImporte(vehTot.ytd.ingresos)}</p>
                        <p>Gas: {formatImporte(vehTot.ytd.gastos)}</p>
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
            {/* Total row (only if multiple vehicles) */}
            {filtered.length > 1 && (
              <tr className="bg-gray-50 border-t-2 border-gray-200">
                <td className="px-5 py-3"><span className="text-sm font-bold text-gray-700">TOTAL</span></td>
                {meses.map((mes) => {
                  const d = totals.byMes[mes];
                  if (!d || (d.ingresos === 0 && d.gastos === 0)) {
                    return <td key={mes} className="px-3 py-3 text-center"><span className="text-xs text-gray-300">-</span></td>;
                  }
                  return (
                    <td key={mes} className="px-3 py-3 text-center">
                      <div className="space-y-0.5">
                        <p className={cn("text-sm font-bold", d.neto >= 0 ? "text-gray-700" : "text-red-600")}>{formatImporte(d.neto)}</p>
                        <MargenBadge value={d.margen_pct} />
                      </div>
                    </td>
                  );
                })}
                <td className="px-4 py-3 text-center bg-gray-100/50">
                  <div className="space-y-0.5">
                    <p className={cn("text-sm font-bold", totals.ytd.neto >= 0 ? "text-gray-700" : "text-red-600")}>{formatImporte(totals.ytd.neto)}</p>
                    <MargenBadge value={totals.ytd.margen_pct} />
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ReportesPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["costes-matriz"],
    queryFn: api.dashboard.costesMatriz,
  });

  const vehiculos: VehiculoRow[] = data?.vehiculos ?? [];
  const meses: string[] = data?.meses ?? [];
  const allIds = vehiculos.map((v) => v.vehiculo_id);

  return (
    <div className="min-h-screen">
      <Header
        title="Reportes"
        breadcrumbs={[{ label: "Analisis" }, { label: "Reportes" }]}
      />

      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Reportes</h1>
            <p className="text-sm text-gray-500 mt-1">
              Coste por kilometro, beneficios por segmento y totales
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        ) : meses.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-100 flex flex-col items-center justify-center py-20 text-gray-400">
            <Truck className="w-10 h-10 mb-3 text-gray-300" />
            <p className="text-sm font-medium text-gray-600">No hay datos disponibles</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* 1. Coste por kilómetro */}
            <CosteKmSection vehiculos={vehiculos} meses={meses} />

            {/* 2. Beneficios Camiones (LVX + MJC + MTY) */}
            <BeneficiosSection
              title="Beneficios Camiones"
              subtitle="LVX + MJC + MTY — Transporte de mercancias"
              icon={<Package className="w-4 h-4 text-blue-600" />}
              iconBg="bg-blue-50"
              iconColor="text-blue-600"
              vehiculos={vehiculos}
              ids={CAMIONES}
              meses={meses}
            />

            {/* 3. Beneficios MLB */}
            <BeneficiosSection
              title="Beneficios MLB"
              subtitle="MLB — Warburton / USC"
              icon={<Building2 className="w-4 h-4 text-amber-600" />}
              iconBg="bg-amber-50"
              iconColor="text-amber-600"
              vehiculos={vehiculos}
              ids={["MLB"]}
              meses={meses}
            />

            {/* 4. Beneficios Totales */}
            <BeneficiosSection
              title="Beneficios Totales"
              subtitle="Todos los vehiculos — Flota completa"
              icon={<TrendingUp className="w-4 h-4 text-emerald-600" />}
              iconBg="bg-emerald-50"
              iconColor="text-emerald-600"
              vehiculos={vehiculos}
              ids={allIds}
              meses={meses}
            />
          </div>
        )}
      </div>
    </div>
  );
}
