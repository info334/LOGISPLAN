"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Truck,
  Tag,
  CheckCircle2,
  AlertTriangle,
  Filter,
  Check,
  ChevronDown,
  Loader2,
  ArrowUpDown,
  RefreshCw,
} from "lucide-react";
import Header from "@/components/layout/header";
import { cn, formatImporte, formatFecha } from "@/lib/utils";
import { api } from "@/lib/api";

interface Movimiento {
  id: number;
  fecha: string;
  descripcion: string;
  importe: number;
  categoria_id: string | null;
  categoria_nombre: string | null;
  vehiculo_id: string | null;
  vehiculo_descripcion: string | null;
}

export default function ImportarPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<"todos" | "sin_asignar" | "asignados">("sin_asignar");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchVehiculo, setBatchVehiculo] = useState("");
  const [batchCategoria, setBatchCategoria] = useState("");
  const [editingRow, setEditingRow] = useState<number | null>(null);
  const [editVehiculo, setEditVehiculo] = useState("");
  const [editCategoria, setEditCategoria] = useState("");
  const [page, setPage] = useState(1);
  const [successMsg, setSuccessMsg] = useState("");

  // Fetch movimientos
  const params: Record<string, string> = { page: String(page), page_size: "30" };
  if (filter === "sin_asignar") params.sin_asignar = "true";

  const { data: movData, isLoading } = useQuery({
    queryKey: ["movimientos", filter, page],
    queryFn: () => api.movimientos.list(params),
  });

  // Fetch opciones (vehiculos + categorias)
  const { data: opciones } = useQuery({
    queryKey: ["movimientos", "opciones"],
    queryFn: api.movimientos.opciones,
  });

  const movimientos: Movimiento[] = movData?.data ?? [];
  const totalPages = movData?.total_pages ?? 1;
  const total = movData?.total ?? 0;
  const vehiculos = opciones?.vehiculos ?? [];
  const categorias = opciones?.categorias ?? [];

  // Asignar individual
  const asignarMut = useMutation({
    mutationFn: ({ id, vehiculo_id, categoria_id }: { id: number; vehiculo_id: string; categoria_id: string }) =>
      api.movimientos.asignar(id, { vehiculo_id, categoria_id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["movimientos"] });
      setEditingRow(null);
      flashSuccess("Movimiento asignado");
    },
  });

  // Asignar batch
  const batchMut = useMutation({
    mutationFn: () =>
      api.movimientos.asignarBatch(
        Array.from(selectedIds),
        batchVehiculo || undefined,
        batchCategoria || undefined
      ),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["movimientos"] });
      setSelectedIds(new Set());
      setBatchVehiculo("");
      setBatchCategoria("");
      flashSuccess(`${data.actualizados} movimientos asignados`);
    },
  });

  function flashSuccess(msg: string) {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(""), 3000);
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selectedIds.size === movimientos.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(movimientos.map((m) => m.id)));
    }
  }

  function startEdit(mov: Movimiento) {
    setEditingRow(mov.id);
    setEditVehiculo(mov.vehiculo_id || "");
    setEditCategoria(mov.categoria_id || "");
  }

  function saveEdit(id: number) {
    asignarMut.mutate({ id, vehiculo_id: editVehiculo, categoria_id: editCategoria });
  }

  const allSelected = movimientos.length > 0 && selectedIds.size === movimientos.length;

  return (
    <div className="min-h-screen">
      <Header
        title="Asignar Gastos"
        breadcrumbs={[{ label: "Importar" }, { label: "Asignar Gastos" }]}
      />

      <div className="p-6">
        {/* Title */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Asignacion de Gastos por Matricula
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Asigna vehiculo y categoria a cada movimiento. Puedes hacerlo uno a uno o seleccionar varios a la vez.
          </p>
        </div>

        {/* Success message */}
        {successMsg && (
          <div className="mb-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2 text-sm text-emerald-700">
            <CheckCircle2 className="w-4 h-4" />
            {successMsg}
          </div>
        )}

        {/* Batch assign bar */}
        {selectedIds.size > 0 && (
          <div className="mb-4 p-4 bg-brand-50 border-2 border-brand-200 rounded-xl flex items-center gap-4">
            <span className="text-sm font-semibold text-brand-700">
              {selectedIds.size} seleccionados
            </span>

            <select
              value={batchVehiculo}
              onChange={(e) => setBatchVehiculo(e.target.value)}
              className="px-3 py-2 bg-white rounded-lg border border-brand-200 text-sm outline-none focus:border-brand-400"
            >
              <option value="">-- Vehiculo --</option>
              <option value="COMUN">COMUN</option>
              {vehiculos.filter((v: any) => v.id !== "COMUN").map((v: any) => (
                <option key={v.id} value={v.id}>
                  {v.id} - {v.descripcion}
                </option>
              ))}
            </select>

            <select
              value={batchCategoria}
              onChange={(e) => setBatchCategoria(e.target.value)}
              className="px-3 py-2 bg-white rounded-lg border border-brand-200 text-sm outline-none focus:border-brand-400"
            >
              <option value="">-- Categoria --</option>
              {categorias.map((c: any) => (
                <option key={c.id} value={c.id}>
                  {c.nombre || c.id}
                </option>
              ))}
            </select>

            <button
              onClick={() => batchMut.mutate()}
              disabled={(!batchVehiculo && !batchCategoria) || batchMut.isPending}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2",
                batchVehiculo || batchCategoria
                  ? "bg-brand-500 text-white hover:bg-brand-600"
                  : "bg-gray-200 text-gray-400 cursor-not-allowed"
              )}
            >
              {batchMut.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              Asignar a todos
            </button>

            <button
              onClick={() => setSelectedIds(new Set())}
              className="ml-auto text-sm text-gray-500 hover:text-gray-700"
            >
              Cancelar
            </button>
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3 mb-4">
          <div className="flex gap-1 p-1 bg-gray-100 rounded-lg">
            {[
              { key: "sin_asignar" as const, label: "Sin asignar", icon: AlertTriangle },
              { key: "todos" as const, label: "Todos", icon: ArrowUpDown },
              { key: "asignados" as const, label: "Asignados", icon: CheckCircle2 },
            ].map((f) => (
              <button
                key={f.key}
                onClick={() => { setFilter(f.key); setPage(1); setSelectedIds(new Set()); }}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md transition-colors",
                  filter === f.key
                    ? "bg-white text-gray-900 shadow-sm font-medium"
                    : "text-gray-500 hover:text-gray-700"
                )}
              >
                <f.icon className="w-3.5 h-3.5" />
                {f.label}
              </button>
            ))}
          </div>

          <span className="text-sm text-gray-400">
            {total} movimientos
          </span>

          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ["movimientos"] })}
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
          ) : movimientos.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <CheckCircle2 className="w-10 h-10 mb-3 text-emerald-400" />
              <p className="text-sm font-medium text-gray-600">
                {filter === "sin_asignar"
                  ? "Todos los movimientos estan asignados"
                  : "No hay movimientos"}
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                    />
                  </th>
                  <th className="text-left text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">
                    Fecha
                  </th>
                  <th className="text-left text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">
                    Descripcion
                  </th>
                  <th className="text-right text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">
                    Importe
                  </th>
                  <th className="text-left text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">
                    <div className="flex items-center gap-1">
                      <Truck className="w-3.5 h-3.5" />
                      Vehiculo
                    </div>
                  </th>
                  <th className="text-left text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">
                    <div className="flex items-center gap-1">
                      <Tag className="w-3.5 h-3.5" />
                      Categoria
                    </div>
                  </th>
                  <th className="w-20 px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {movimientos.map((mov) => {
                  const isEditing = editingRow === mov.id;
                  const isSelected = selectedIds.has(mov.id);
                  const sinVehiculo = !mov.vehiculo_id;

                  return (
                    <tr
                      key={mov.id}
                      className={cn(
                        "border-b border-gray-50 transition-colors",
                        isSelected && "bg-brand-50/50",
                        isEditing && "bg-amber-50/50",
                        !isSelected && !isEditing && "hover:bg-gray-50/50"
                      )}
                    >
                      {/* Checkbox */}
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(mov.id)}
                          className="w-4 h-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                        />
                      </td>

                      {/* Fecha */}
                      <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                        {formatFecha(mov.fecha)}
                      </td>

                      {/* Descripcion */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {sinVehiculo && (
                            <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                          )}
                          <span className="text-sm text-gray-900 truncate max-w-[300px]">
                            {mov.descripcion}
                          </span>
                        </div>
                      </td>

                      {/* Importe */}
                      <td className="px-4 py-3 text-right">
                        <span
                          className={cn(
                            "text-sm font-medium",
                            mov.importe >= 0 ? "text-emerald-600" : "text-red-600"
                          )}
                        >
                          {formatImporte(mov.importe)}
                        </span>
                      </td>

                      {/* Vehiculo */}
                      <td className="px-4 py-3">
                        {isEditing ? (
                          <select
                            value={editVehiculo}
                            onChange={(e) => setEditVehiculo(e.target.value)}
                            className="w-full px-2 py-1.5 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                          >
                            <option value="">-- Sin asignar --</option>
                            <option value="COMUN">COMUN</option>
                            {vehiculos
                              .filter((v: any) => v.id !== "COMUN")
                              .map((v: any) => (
                                <option key={v.id} value={v.id}>
                                  {v.id}
                                </option>
                              ))}
                          </select>
                        ) : mov.vehiculo_id ? (
                          <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-brand-50 text-brand-700 border border-brand-100">
                            <Truck className="w-3 h-3 mr-1" />
                            {mov.vehiculo_id}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400 italic">
                            Sin asignar
                          </span>
                        )}
                      </td>

                      {/* Categoria */}
                      <td className="px-4 py-3">
                        {isEditing ? (
                          <select
                            value={editCategoria}
                            onChange={(e) => setEditCategoria(e.target.value)}
                            className="w-full px-2 py-1.5 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                          >
                            <option value="">-- Sin categoria --</option>
                            {categorias.map((c: any) => (
                              <option key={c.id} value={c.id}>
                                {c.nombre || c.id}
                              </option>
                            ))}
                          </select>
                        ) : mov.categoria_nombre ? (
                          <span className="text-xs text-gray-600">
                            {mov.categoria_nombre}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400 italic">
                            Sin categoria
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3">
                        {isEditing ? (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => saveEdit(mov.id)}
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
                              onClick={() => setEditingRow(null)}
                              className="p-1.5 text-gray-400 hover:bg-gray-100 rounded transition-colors text-xs"
                            >
                              Cancelar
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => startEdit(mov)}
                            className="px-3 py-1.5 text-xs font-medium text-brand-600 hover:bg-brand-50 rounded-md transition-colors"
                          >
                            Editar
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100">
              <span className="text-sm text-gray-500">
                Pagina {page} de {totalPages} ({total} movimientos)
              </span>
              <div className="flex gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-sm rounded-md bg-gray-50 text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Anterior
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 text-sm rounded-md bg-gray-50 text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Siguiente
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
