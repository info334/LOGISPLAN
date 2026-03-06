"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Receipt,
  Truck,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Check,
  RefreshCw,
  ChevronDown,
} from "lucide-react";
import Header from "@/components/layout/header";
import { cn, formatImporte } from "@/lib/utils";
import { api } from "@/lib/api";

interface Factura {
  id: number;
  mes: string;
  vehiculo_id: string;
  importe: number;
  descripcion: string;
  created_at: string;
  vehiculo_descripcion: string | null;
}

const MESES: Record<string, string> = {
  "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
  "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
  "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
};

function formatMes(mes: string) {
  const [year, month] = mes.split("-");
  return `${MESES[month] || month} ${year}`;
}

const VEHICLE_COLORS: Record<string, string> = {
  MTY: "bg-blue-50 text-blue-700 border-blue-200",
  LVX: "bg-emerald-50 text-emerald-700 border-emerald-200",
  MJC: "bg-purple-50 text-purple-700 border-purple-200",
  MLB: "bg-amber-50 text-amber-700 border-amber-200",
  "COMÚN": "bg-gray-100 text-gray-600 border-gray-200",
};

export default function FacturacionPage() {
  const queryClient = useQueryClient();
  const [mesFilter, setMesFilter] = useState<string>("");
  const [vehiculoFilter, setVehiculoFilter] = useState<string>("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editVehiculo, setEditVehiculo] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Fetch data
  const params: Record<string, string> = {};
  if (mesFilter) params.mes = mesFilter;
  if (vehiculoFilter) params.vehiculo_id = vehiculoFilter;

  const { data: facturas = [], isLoading } = useQuery({
    queryKey: ["facturacion", mesFilter, vehiculoFilter],
    queryFn: () => api.facturacion.list(Object.keys(params).length ? params : undefined),
  });

  const { data: periodos = [] } = useQuery({
    queryKey: ["facturacion", "periodos"],
    queryFn: api.facturacion.periodos,
  });

  const { data: vehiculosData } = useQuery({
    queryKey: ["vehiculos"],
    queryFn: api.vehiculos.list,
  });

  const vehiculos = vehiculosData ?? [];

  // Group by month for summary
  const resumenPorMes = useMemo(() => {
    const grouped: Record<string, { total: number; vehiculos: Record<string, number>; sinAsignar: number }> = {};
    for (const f of facturas as Factura[]) {
      if (!grouped[f.mes]) grouped[f.mes] = { total: 0, vehiculos: {}, sinAsignar: 0 };
      grouped[f.mes].total += f.importe;
      grouped[f.mes].vehiculos[f.vehiculo_id] = (grouped[f.mes].vehiculos[f.vehiculo_id] || 0) + f.importe;
      if (f.vehiculo_id === "COMÚN") grouped[f.mes].sinAsignar += f.importe;
    }
    return grouped;
  }, [facturas]);

  // Mutation for reassigning vehicle
  const asignarMut = useMutation({
    mutationFn: ({ id, vehiculo_id }: { id: number; vehiculo_id: string }) =>
      api.facturacion.asignarVehiculo(id, vehiculo_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["facturacion"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setEditingId(null);
      setSuccessMsg("Vehiculo asignado correctamente");
      setTimeout(() => setSuccessMsg(""), 3000);
    },
  });

  function startEdit(f: Factura) {
    setEditingId(f.id);
    setEditVehiculo(f.vehiculo_id);
  }

  function saveEdit(id: number) {
    if (!editVehiculo) return;
    asignarMut.mutate({ id, vehiculo_id: editVehiculo });
  }

  // Summary cards data
  const totalFacturacion = (facturas as Factura[]).reduce((sum, f) => sum + f.importe, 0);
  const totalComun = (facturas as Factura[]).filter((f) => f.vehiculo_id === "COMÚN").reduce((sum, f) => sum + f.importe, 0);
  const mesesCount = new Set((facturas as Factura[]).map((f) => f.mes)).size;

  return (
    <div className="min-h-screen">
      <Header
        title="Facturacion"
        breadcrumbs={[{ label: "Navegacion" }, { label: "Facturacion" }]}
      />

      <div className="p-6">
        {/* Title */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Facturacion Emitida</h1>
          <p className="text-sm text-gray-500 mt-1">
            Facturas por vehiculo y mes. Las facturas en COMUN pueden reasignarse a un vehiculo.
          </p>
        </div>

        {/* Success message */}
        {successMsg && (
          <div className="mb-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2 text-sm text-emerald-700">
            <CheckCircle2 className="w-4 h-4" />
            {successMsg}
          </div>
        )}

        {/* Summary cards */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500">Total facturado</span>
              <Receipt className="w-5 h-5 text-brand-400" />
            </div>
            <p className="text-2xl font-bold text-gray-900">{formatImporte(totalFacturacion)}</p>
            <p className="text-xs text-gray-400 mt-1">{mesesCount} {mesesCount === 1 ? "mes" : "meses"}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500">Asignado a vehiculos</span>
              <Truck className="w-5 h-5 text-emerald-400" />
            </div>
            <p className="text-2xl font-bold text-emerald-600">{formatImporte(totalFacturacion - totalComun)}</p>
            <p className="text-xs text-gray-400 mt-1">
              {((totalFacturacion - totalComun) / (totalFacturacion || 1) * 100).toFixed(0)}% del total
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium text-gray-500">Sin asignar (COMUN)</span>
              <AlertTriangle className="w-5 h-5 text-amber-400" />
            </div>
            <p className={cn("text-2xl font-bold", totalComun > 0 ? "text-amber-600" : "text-gray-400")}>
              {formatImporte(totalComun)}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              {totalComun > 0
                ? `${(totalComun / (totalFacturacion || 1) * 100).toFixed(0)}% pendiente`
                : "Todo asignado"}
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-gray-400" />
            <select
              value={mesFilter}
              onChange={(e) => setMesFilter(e.target.value)}
              className="px-3 py-2 bg-white rounded-lg border border-gray-200 text-sm outline-none focus:border-brand-400"
            >
              <option value="">Todos los meses</option>
              {periodos.map((p: string) => (
                <option key={p} value={p}>{formatMes(p)}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <Truck className="w-4 h-4 text-gray-400" />
            <select
              value={vehiculoFilter}
              onChange={(e) => setVehiculoFilter(e.target.value)}
              className="px-3 py-2 bg-white rounded-lg border border-gray-200 text-sm outline-none focus:border-brand-400"
            >
              <option value="">Todos los vehiculos</option>
              {vehiculos.map((v: any) => (
                <option key={v.id} value={v.id}>{v.id} - {v.descripcion}</option>
              ))}
            </select>
          </div>

          <span className="text-sm text-gray-400">
            {(facturas as Factura[]).length} registros
          </span>

          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ["facturacion"] })}
            className="ml-auto p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
            </div>
          ) : (facturas as Factura[]).length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <Receipt className="w-10 h-10 mb-3 text-gray-300" />
              <p className="text-sm font-medium text-gray-600">No hay facturas para los filtros seleccionados</p>
            </div>
          ) : (
            <>
              {/* Group by month */}
              {Object.keys(resumenPorMes)
                .sort((a, b) => b.localeCompare(a))
                .map((mes) => {
                  const mesFacturas = (facturas as Factura[])
                    .filter((f) => f.mes === mes)
                    .sort((a, b) => {
                      if (a.vehiculo_id === "COMÚN") return 1;
                      if (b.vehiculo_id === "COMÚN") return -1;
                      return a.vehiculo_id.localeCompare(b.vehiculo_id);
                    });
                  const resumen = resumenPorMes[mes];

                  return (
                    <div key={mes}>
                      {/* Month header */}
                      <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Calendar className="w-4 h-4 text-gray-400" />
                          <span className="text-sm font-semibold text-gray-700">{formatMes(mes)}</span>
                        </div>
                        <div className="flex items-center gap-4">
                          {Object.entries(resumen.vehiculos)
                            .filter(([v]) => v !== "COMÚN")
                            .sort(([a], [b]) => a.localeCompare(b))
                            .map(([v, importe]) => (
                              <span key={v} className="text-xs text-gray-500">
                                <span className={cn("inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border mr-1", VEHICLE_COLORS[v] || VEHICLE_COLORS["COMÚN"])}>
                                  {v}
                                </span>
                                {formatImporte(importe)}
                              </span>
                            ))}
                          {resumen.sinAsignar > 0 && (
                            <span className="text-xs text-amber-600">
                              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border bg-amber-50 text-amber-600 border-amber-200 mr-1">
                                COMUN
                              </span>
                              {formatImporte(resumen.sinAsignar)}
                            </span>
                          )}
                          <span className="text-sm font-semibold text-gray-900 ml-2">
                            {formatImporte(resumen.total)}
                          </span>
                        </div>
                      </div>

                      {/* Rows for this month */}
                      <table className="w-full">
                        <tbody>
                          {mesFacturas.map((f) => {
                            const isEditing = editingId === f.id;
                            const isComun = f.vehiculo_id === "COMÚN";

                            return (
                              <tr
                                key={f.id}
                                className={cn(
                                  "border-b border-gray-50 transition-colors",
                                  isEditing && "bg-amber-50/50",
                                  isComun && !isEditing && "bg-amber-50/30",
                                  !isComun && !isEditing && "hover:bg-gray-50/50"
                                )}
                              >
                                {/* Vehiculo */}
                                <td className="px-5 py-3 w-40">
                                  {isEditing ? (
                                    <select
                                      value={editVehiculo}
                                      onChange={(e) => setEditVehiculo(e.target.value)}
                                      className="w-full px-2 py-1.5 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                                    >
                                      {vehiculos.map((v: any) => (
                                        <option key={v.id} value={v.id}>{v.id} - {v.descripcion}</option>
                                      ))}
                                    </select>
                                  ) : (
                                    <span className={cn(
                                      "inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-md border",
                                      VEHICLE_COLORS[f.vehiculo_id] || VEHICLE_COLORS["COMÚN"]
                                    )}>
                                      <Truck className="w-3 h-3 mr-1.5" />
                                      {f.vehiculo_id}
                                    </span>
                                  )}
                                </td>

                                {/* Descripcion */}
                                <td className="px-4 py-3">
                                  <div className="flex items-center gap-2">
                                    {isComun && !isEditing && (
                                      <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                                    )}
                                    <span className="text-sm text-gray-600 truncate max-w-[400px]">
                                      {f.descripcion}
                                    </span>
                                  </div>
                                </td>

                                {/* Importe */}
                                <td className="px-4 py-3 text-right">
                                  <span className="text-sm font-semibold text-gray-900">
                                    {formatImporte(f.importe)}
                                  </span>
                                </td>

                                {/* Actions */}
                                <td className="px-4 py-3 w-36 text-right">
                                  {isEditing ? (
                                    <div className="flex items-center justify-end gap-1">
                                      <button
                                        onClick={() => saveEdit(f.id)}
                                        disabled={asignarMut.isPending}
                                        className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
                                        title="Guardar"
                                      >
                                        {asignarMut.isPending ? (
                                          <Loader2 className="w-4 h-4 animate-spin" />
                                        ) : (
                                          <Check className="w-4 h-4" />
                                        )}
                                      </button>
                                      <button
                                        onClick={() => setEditingId(null)}
                                        className="p-1.5 text-gray-400 hover:bg-gray-100 rounded transition-colors text-xs"
                                      >
                                        Cancelar
                                      </button>
                                    </div>
                                  ) : (
                                    <button
                                      onClick={() => startEdit(f)}
                                      className={cn(
                                        "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                                        isComun
                                          ? "text-amber-700 bg-amber-100 hover:bg-amber-200"
                                          : "text-brand-600 hover:bg-brand-50"
                                      )}
                                    >
                                      {isComun ? "Asignar" : "Cambiar"}
                                    </button>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  );
                })}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
