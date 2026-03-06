"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Link2,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Key,
  Receipt,
  Wallet,
  Building2,
  Loader2,
  AlertTriangle,
  ArrowDownCircle,
  RotateCcw,
  Sparkles,
  Truck,
  Info,
} from "lucide-react";
import Header from "@/components/layout/header";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { HoldedStatus, SyncResult } from "@/lib/api";

export default function IntegracionesPage() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  const [resultType, setResultType] = useState<string>("");

  // Estado de conexion
  const { data: status, isLoading: loadingStatus } = useQuery<HoldedStatus>({
    queryKey: ["holded", "status"],
    queryFn: api.holded.status,
  });

  // Mutation: configurar API Key
  const configureMutation = useMutation({
    mutationFn: (key: string) => api.holded.configure(key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["holded", "status"] });
      setShowKeyInput(false);
      setApiKey("");
    },
  });

  // Mutation: sync completo
  const syncTodoMutation = useMutation({
    mutationFn: () => api.holded.syncTodo(),
    onSuccess: (data) => {
      setSyncResult(data);
      setResultType("todo");
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  // Mutation: sync solo facturas
  const syncFacturasMutation = useMutation({
    mutationFn: () => api.holded.syncFacturas(),
    onSuccess: (data) => {
      setSyncResult(data);
      setResultType("facturas");
    },
  });

  // Mutation: sync solo gastos
  const syncGastosMutation = useMutation({
    mutationFn: () => api.holded.syncGastos(),
    onSuccess: (data) => {
      setSyncResult(data);
      setResultType("gastos");
    },
  });

  // Mutation: re-aplicar reglas
  const reaplicarMutation = useMutation({
    mutationFn: () => api.holded.reaplicarReglas(),
    onSuccess: (data) => {
      setSyncResult(data);
      setResultType("reglas");
      queryClient.invalidateQueries({ queryKey: ["movimientos"] });
    },
  });

  // Mutation: resync completo (borrar + reimportar)
  const resyncMutation = useMutation({
    mutationFn: () => api.holded.resync(),
    onSuccess: (data) => {
      setSyncResult(data);
      setResultType("resync");
      queryClient.invalidateQueries({ queryKey: ["movimientos"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const isConnected = status?.connected === true;
  const isSyncing =
    syncTodoMutation.isPending ||
    syncFacturasMutation.isPending ||
    syncGastosMutation.isPending ||
    reaplicarMutation.isPending ||
    resyncMutation.isPending;

  return (
    <div className="min-h-screen">
      <Header
        title="Integraciones"
        breadcrumbs={[
          { label: "Configuracion" },
          { label: "Integraciones" },
        ]}
      />

      <div className="p-6 max-w-4xl space-y-6">
        {/* Holded Card */}
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          {/* Card Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-100">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center">
                <Link2 className="w-6 h-6 text-indigo-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Holded</h2>
                <p className="text-sm text-gray-500">
                  Sincroniza facturas, gastos y tesoreria desde tu cuenta de Holded
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {loadingStatus ? (
                <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />
              ) : isConnected ? (
                <span className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 text-emerald-700 text-sm font-medium rounded-full">
                  <CheckCircle2 className="w-4 h-4" />
                  Conectado
                </span>
              ) : (
                <span className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-700 text-sm font-medium rounded-full">
                  <XCircle className="w-4 h-4" />
                  Desconectado
                </span>
              )}
            </div>
          </div>

          {/* API Key Config */}
          <div className="p-6 border-b border-gray-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Key className="w-5 h-5 text-gray-400" />
                <div>
                  <p className="text-sm font-medium text-gray-700">API Key</p>
                  <p className="text-xs text-gray-400">
                    {isConnected
                      ? "Clave configurada correctamente"
                      : "Configura tu API Key de Holded para empezar"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setShowKeyInput(!showKeyInput)}
                className="text-sm text-brand-500 hover:text-brand-600 font-medium"
              >
                {isConnected ? "Cambiar clave" : "Configurar"}
              </button>
            </div>

            {showKeyInput && (
              <div className="mt-4 flex gap-3">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Pega tu API Key de Holded aqui..."
                  className="flex-1 px-4 py-2.5 bg-gray-50 rounded-lg border border-gray-200 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 transition-all"
                />
                <button
                  onClick={() => configureMutation.mutate(apiKey)}
                  disabled={!apiKey || configureMutation.isPending}
                  className={cn(
                    "px-5 py-2.5 rounded-lg text-sm font-medium transition-colors",
                    apiKey
                      ? "bg-brand-500 text-white hover:bg-brand-600"
                      : "bg-gray-100 text-gray-400 cursor-not-allowed"
                  )}
                >
                  {configureMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "Guardar"
                  )}
                </button>
              </div>
            )}

            {configureMutation.isError && (
              <p className="mt-2 text-sm text-red-600 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                {configureMutation.error.message}
              </p>
            )}

            {configureMutation.isSuccess && (
              <p className="mt-2 text-sm text-emerald-600 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4" />
                API Key configurada y verificada correctamente
              </p>
            )}
          </div>

          {/* Sync Actions */}
          {isConnected && (
            <div className="p-6">
              <h3 className="text-sm font-semibold text-gray-900 mb-4">
                Sincronizar datos
              </h3>

              <div className="grid grid-cols-1 gap-3 mb-4">
                {/* Sync Todo */}
                <button
                  onClick={() => syncTodoMutation.mutate()}
                  disabled={isSyncing}
                  className="flex items-center gap-4 p-4 rounded-xl border-2 border-brand-200 bg-brand-50 hover:bg-brand-100 transition-colors text-left disabled:opacity-50"
                >
                  <div className="w-10 h-10 bg-brand-500 rounded-lg flex items-center justify-center">
                    {syncTodoMutation.isPending ? (
                      <Loader2 className="w-5 h-5 text-white animate-spin" />
                    ) : (
                      <RefreshCw className="w-5 h-5 text-white" />
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-brand-700">
                      Sincronizacion completa
                    </p>
                    <p className="text-xs text-brand-500">
                      Importa facturas emitidas, gastos y tesoreria de una vez
                    </p>
                  </div>
                </button>

                {/* Sync Individual */}
                <div className="grid grid-cols-3 gap-3">
                  <button
                    onClick={() => syncFacturasMutation.mutate()}
                    disabled={isSyncing}
                    className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left disabled:opacity-50"
                  >
                    <div className="w-8 h-8 bg-emerald-50 rounded-lg flex items-center justify-center">
                      {syncFacturasMutation.isPending ? (
                        <Loader2 className="w-4 h-4 text-emerald-600 animate-spin" />
                      ) : (
                        <Receipt className="w-4 h-4 text-emerald-600" />
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-700">Facturas</p>
                      <p className="text-xs text-gray-400">Ventas</p>
                    </div>
                  </button>

                  <button
                    onClick={() => syncGastosMutation.mutate()}
                    disabled={isSyncing}
                    className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left disabled:opacity-50"
                  >
                    <div className="w-8 h-8 bg-amber-50 rounded-lg flex items-center justify-center">
                      {syncGastosMutation.isPending ? (
                        <Loader2 className="w-4 h-4 text-amber-600 animate-spin" />
                      ) : (
                        <Wallet className="w-4 h-4 text-amber-600" />
                      )}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-700">Gastos</p>
                      <p className="text-xs text-gray-400">Compras</p>
                    </div>
                  </button>

                  <button
                    onClick={() => {}}
                    disabled={isSyncing}
                    className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left disabled:opacity-50"
                  >
                    <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
                      <Building2 className="w-4 h-4 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-700">Tesoreria</p>
                      <p className="text-xs text-gray-400">Bancos</p>
                    </div>
                  </button>
                </div>
              </div>

              {/* Herramientas avanzadas */}
              <h3 className="text-sm font-semibold text-gray-900 mb-3 mt-6">
                Herramientas avanzadas
              </h3>

              <div className="grid grid-cols-2 gap-3 mb-4">
                {/* Re-aplicar reglas */}
                <button
                  onClick={() => reaplicarMutation.mutate()}
                  disabled={isSyncing}
                  className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-left disabled:opacity-50"
                >
                  <div className="w-8 h-8 bg-violet-50 rounded-lg flex items-center justify-center">
                    {reaplicarMutation.isPending ? (
                      <Loader2 className="w-4 h-4 text-violet-600 animate-spin" />
                    ) : (
                      <Sparkles className="w-4 h-4 text-violet-600" />
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700">Re-aplicar reglas</p>
                    <p className="text-xs text-gray-400">
                      Actualiza categorias y vehiculos segun reglas actuales
                    </p>
                  </div>
                </button>

                {/* Re-sync completo */}
                <button
                  onClick={() => {
                    if (window.confirm("Esto eliminara todos los gastos de Holded y los re-importara. Continuar?")) {
                      resyncMutation.mutate();
                    }
                  }}
                  disabled={isSyncing}
                  className="flex items-center gap-3 p-3 rounded-lg border border-orange-200 hover:bg-orange-50 transition-colors text-left disabled:opacity-50"
                >
                  <div className="w-8 h-8 bg-orange-50 rounded-lg flex items-center justify-center">
                    {resyncMutation.isPending ? (
                      <Loader2 className="w-4 h-4 text-orange-600 animate-spin" />
                    ) : (
                      <RotateCcw className="w-4 h-4 text-orange-600" />
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700">Re-sincronizar</p>
                    <p className="text-xs text-gray-400">
                      Borra datos Holded previos y reimporta con reglas nuevas
                    </p>
                  </div>
                </button>
              </div>

              {/* Last sync info */}
              {status?.last_sync && (
                <p className="text-xs text-gray-400 mb-4">
                  Ultima sincronizacion: {new Date(status.last_sync).toLocaleString("es-ES")}
                </p>
              )}

              {/* Sync Results */}
              {syncResult && (
                <div className="mt-4 p-4 bg-gray-50 rounded-xl">
                  <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <ArrowDownCircle className="w-4 h-4 text-brand-500" />
                    Resultado {resultType === "reglas" ? "de re-aplicar reglas" : resultType === "resync" ? "de re-sincronizacion" : "de sincronizacion"}
                  </h4>

                  {/* Resultado de reglas */}
                  {resultType === "reglas" && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 bg-white rounded-lg border border-gray-100">
                        <p className="text-xs text-gray-400 mb-1">Revisados</p>
                        <p className="text-lg font-bold text-gray-900">{syncResult.total_revisados}</p>
                        <p className="text-xs text-gray-500">movimientos analizados</p>
                      </div>
                      <div className="p-3 bg-white rounded-lg border border-gray-100">
                        <p className="text-xs text-gray-400 mb-1">Actualizados</p>
                        <p className="text-lg font-bold text-emerald-600">{syncResult.actualizados}</p>
                        <p className="text-xs text-gray-500">con nueva categoria/vehiculo</p>
                      </div>
                    </div>
                  )}

                  {/* Resultado de facturas */}
                  {resultType === "facturas" && (
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-3 bg-white rounded-lg border border-gray-100">
                        <p className="text-xs text-gray-400 mb-1">Procesadas</p>
                        <p className="text-lg font-bold text-gray-900">
                          {syncResult.facturas_procesadas ?? syncResult.importadas}
                        </p>
                        <p className="text-xs text-gray-500">facturas de Holded</p>
                      </div>
                      <div className="p-3 bg-white rounded-lg border border-gray-100">
                        <p className="text-xs text-gray-400 mb-1">Importadas</p>
                        <p className="text-lg font-bold text-emerald-600">{syncResult.importadas}</p>
                        <p className="text-xs text-gray-500">registros facturacion</p>
                      </div>
                    </div>
                  )}

                  {/* Resultado de gastos / resync */}
                  {(resultType === "gastos" || resultType === "resync") && (
                    <div className="space-y-3">
                      {syncResult.eliminados_previos !== undefined && (
                        <p className="text-sm text-orange-600">
                          Se eliminaron {syncResult.eliminados_previos} registros previos antes de reimportar
                        </p>
                      )}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="p-3 bg-white rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-400 mb-1">Descargados</p>
                          <p className="text-lg font-bold text-gray-900">{syncResult.total_descargados}</p>
                        </div>
                        <div className="p-3 bg-white rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-400 mb-1">Insertados</p>
                          <p className="text-lg font-bold text-emerald-600">{syncResult.insertados}</p>
                        </div>
                        <div className="p-3 bg-white rounded-lg border border-gray-100">
                          <p className="text-xs text-gray-400 mb-1">Duplicados</p>
                          <p className="text-lg font-bold text-gray-400">{syncResult.duplicados_ref ?? syncResult.duplicados ?? 0}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Resultado de sync todo */}
                  {resultType === "todo" && (
                    <>
                      {syncResult.errores_globales?.length > 0 && (
                        <div className="mb-3 p-3 bg-red-50 rounded-lg">
                          {syncResult.errores_globales.map((err: string, i: number) => (
                            <p key={i} className="text-sm text-red-700 flex items-center gap-1.5">
                              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                              {err}
                            </p>
                          ))}
                        </div>
                      )}
                      <div className="grid grid-cols-3 gap-4">
                        {syncResult.facturas && (
                          <div className="p-3 bg-white rounded-lg border border-gray-100">
                            <p className="text-xs text-gray-400 mb-1">Facturas</p>
                            <p className="text-lg font-bold text-gray-900">
                              {syncResult.facturas.importadas}
                            </p>
                            <p className="text-xs text-gray-500">importadas</p>
                          </div>
                        )}
                        {syncResult.gastos && (
                          <div className="p-3 bg-white rounded-lg border border-gray-100">
                            <p className="text-xs text-gray-400 mb-1">Gastos</p>
                            <p className="text-lg font-bold text-gray-900">
                              {syncResult.gastos.insertados}
                            </p>
                            <p className="text-xs text-gray-500">
                              nuevos ({syncResult.gastos.duplicados_ref ?? syncResult.gastos.duplicados ?? 0} dup.)
                            </p>
                          </div>
                        )}
                        {syncResult.tesoreria && (
                          <div className="p-3 bg-white rounded-lg border border-gray-100">
                            <p className="text-xs text-gray-400 mb-1">Tesoreria</p>
                            <p className="text-lg font-bold text-gray-900">
                              {syncResult.tesoreria.cuentas?.length ?? 0}
                            </p>
                            <p className="text-xs text-gray-500">cuentas</p>
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  {/* Detalle de facturas con vehiculos */}
                  {syncResult.detalle && syncResult.detalle.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500 mb-2">Detalle de asignaciones:</p>
                      <div className="max-h-60 overflow-y-auto space-y-1">
                        {syncResult.detalle.slice(0, 20).map((d: any, i: number) => (
                          <div key={i} className="flex items-center gap-2 text-xs py-1 px-2 bg-white rounded">
                            <Truck className="w-3 h-3 text-gray-400 flex-shrink-0" />
                            <span className="text-gray-600 truncate flex-1">
                              {d.doc} - {d.contacto}
                            </span>
                            {d.vehiculo && (
                              <span className={cn(
                                "px-1.5 py-0.5 rounded text-xs font-medium",
                                d.tipo === "parcial"
                                  ? "bg-amber-50 text-amber-700"
                                  : d.vehiculo === "COMUN" || d.vehiculo === "COMUN"
                                  ? "bg-gray-100 text-gray-600"
                                  : "bg-blue-50 text-blue-700"
                              )}>
                                {d.vehiculo}
                              </span>
                            )}
                            {d.categoria && (
                              <span className="px-1.5 py-0.5 bg-violet-50 text-violet-700 rounded text-xs">
                                {d.categoria}
                              </span>
                            )}
                            {d.fuente === "sin_asignar" && (
                              <span className="px-1.5 py-0.5 bg-red-50 text-red-600 rounded text-xs">
                                sin asignar
                              </span>
                            )}
                          </div>
                        ))}
                        {syncResult.detalle.length > 20 && (
                          <p className="text-xs text-gray-400 py-1 text-center">
                            ...y {syncResult.detalle.length - 20} mas
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Sync error */}
              {(syncTodoMutation.isError || resyncMutation.isError || reaplicarMutation.isError) && (
                <div className="mt-4 p-3 bg-red-50 rounded-lg">
                  <p className="text-sm text-red-700 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4" />
                    {(syncTodoMutation.error || resyncMutation.error || reaplicarMutation.error)?.message}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Info card about vehicle assignment */}
        <div className="bg-blue-50 rounded-xl border border-blue-100 p-5">
          <div className="flex gap-3">
            <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-blue-900">
                Sobre la asignacion de vehiculos
              </h3>
              <div className="text-xs text-blue-700 space-y-1.5">
                <p>
                  <strong>Facturas emitidas:</strong> Se detecta el vehiculo automaticamente
                  por la descripcion de cada linea (ej: &ldquo;JOSE MANUEL-LVX&rdquo;, &ldquo;CARLOS-MJC&rdquo;).
                  Cada linea se asigna al vehiculo correspondiente.
                </p>
                <p>
                  <strong>Gastos categorizables:</strong> Las reglas auto-asignan categoria y vehiculo
                  (ej: TELEFONICA → TEL/COMUN, WARBURTON → INGRESO/MLB).
                </p>
                <p>
                  <strong>Combustible (SOLRED, STAROIL):</strong> Holded solo tiene 1 linea generica
                  sin desglose por vehiculo. El desglose por matricula esta en las facturas PDF
                  que se importan desde la pagina de Importar.
                </p>
                <p>
                  Los gastos sin vehiculo pueden asignarse manualmente desde la pagina de{" "}
                  <a href="/importar" className="underline font-medium">Importar</a>.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
