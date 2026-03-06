"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Settings,
  Gauge,
  Users,
  Truck,
  Plus,
  Trash2,
  CheckCircle2,
  Loader2,
  Save,
  Upload,
  FileText,
  AlertCircle,
  MapPin,
} from "lucide-react";
import Header from "@/components/layout/header";
import { cn, formatImporte } from "@/lib/utils";
import { api } from "@/lib/api";

const VEHICULOS_OP = ["MTY", "LVX", "MJC", "MLB"];

const MESES_LABEL: Record<string, string> = {
  "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
  "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
  "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre",
};

function formatMes(mes: string) {
  const [year, month] = mes.split("-");
  return `${MESES_LABEL[month] || month} ${year}`;
}

function generarMesesDisponibles(): string[] {
  const meses: string[] = [];
  const now = new Date();
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    meses.push(d.toISOString().slice(0, 7));
  }
  return meses;
}

// =========================================================
//  Tab: Kilometros
// =========================================================
function KilometrosTab() {
  const queryClient = useQueryClient();
  const [selectedMes, setSelectedMes] = useState(new Date().toISOString().slice(0, 7));
  const [kmValues, setKmValues] = useState<Record<string, string>>({});
  const [successMsg, setSuccessMsg] = useState("");

  const mesesDisp = generarMesesDisponibles();

  const { data: kmData = [], isLoading } = useQuery({
    queryKey: ["km", selectedMes],
    queryFn: () => api.configuracion.km.list({ mes: selectedMes }),
  });

  const saveMut = useMutation({
    mutationFn: () => {
      const datos = VEHICULOS_OP
        .filter((v) => kmValues[v] && parseFloat(kmValues[v]) > 0)
        .map((v) => ({ mes: selectedMes, vehiculo_id: v, km: parseFloat(kmValues[v]) }));
      return api.configuracion.km.saveBatch(datos);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["km"] });
      setKmValues({});
      setSuccessMsg(`${data.guardados} registros guardados`);
      setTimeout(() => setSuccessMsg(""), 3000);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.configuracion.km.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["km"] });
    },
  });

  // Pre-fill from existing data
  const existingKm: Record<string, { id: number; km: number }> = {};
  for (const row of kmData) {
    existingKm[row.vehiculo_id] = { id: row.id, km: row.km };
  }

  function handleKmChange(veh: string, val: string) {
    setKmValues((prev) => ({ ...prev, [veh]: val }));
  }

  const hasChanges = VEHICULOS_OP.some((v) => kmValues[v] && parseFloat(kmValues[v]) > 0);

  return (
    <div>
      {successMsg && (
        <div className="mb-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2 text-sm text-emerald-700">
          <CheckCircle2 className="w-4 h-4" />
          {successMsg}
        </div>
      )}

      {/* Mes selector */}
      <div className="flex items-center gap-3 mb-5">
        <span className="text-sm font-medium text-gray-500">Mes:</span>
        <select
          value={selectedMes}
          onChange={(e) => { setSelectedMes(e.target.value); setKmValues({}); }}
          className="px-3 py-2 bg-white rounded-lg border border-gray-200 text-sm outline-none focus:border-brand-400"
        >
          {mesesDisp.map((m) => (
            <option key={m} value={m}>{formatMes(m)}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50/50">
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3 uppercase tracking-wider">Vehiculo</th>
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3 uppercase tracking-wider">Km actuales</th>
              <th className="text-left text-xs font-medium text-gray-400 px-5 py-3 uppercase tracking-wider">Nuevos km</th>
              <th className="w-20 px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {VEHICULOS_OP.map((veh) => {
              const existing = existingKm[veh];
              return (
                <tr key={veh} className="border-b border-gray-50 hover:bg-gray-50/30">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <Truck className="w-4 h-4 text-brand-400" />
                      <span className="text-sm font-bold text-gray-900">{veh}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    {existing ? (
                      <span className="text-sm font-medium text-gray-700">
                        {existing.km.toLocaleString("es-ES")} km
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400 italic">Sin datos</span>
                    )}
                  </td>
                  <td className="px-5 py-3">
                    <input
                      type="number"
                      placeholder={existing ? String(existing.km) : "0"}
                      value={kmValues[veh] || ""}
                      onChange={(e) => handleKmChange(veh, e.target.value)}
                      className="w-32 px-3 py-1.5 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                    />
                  </td>
                  <td className="px-4 py-3">
                    {existing && (
                      <button
                        onClick={() => deleteMut.mutate(existing.id)}
                        className="p-1.5 text-red-400 hover:bg-red-50 rounded transition-colors"
                        title="Eliminar"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Save button */}
      <div className="mt-4 flex justify-end">
        <button
          onClick={() => saveMut.mutate()}
          disabled={!hasChanges || saveMut.isPending}
          className={cn(
            "px-5 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2",
            hasChanges
              ? "bg-brand-500 text-white hover:bg-brand-600"
              : "bg-gray-200 text-gray-400 cursor-not-allowed"
          )}
        >
          {saveMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Guardar km
        </button>
      </div>
    </div>
  );
}


// =========================================================
//  Tab: Costes laborales
// =========================================================
function CostesLaboralesTab() {
  const queryClient = useQueryClient();
  const [selectedMes, setSelectedMes] = useState(new Date().toISOString().slice(0, 7));
  const [showForm, setShowForm] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");

  // Form state
  const [form, setForm] = useState({
    trabajador_id: "",
    nombre: "",
    vehiculo_id: "",
    bruto: "",
    ss_trabajador: "",
    irpf: "",
    liquido: "",
    ss_empresa: "",
  });

  const mesesDisp = generarMesesDisponibles();

  const { data: costes = [], isLoading } = useQuery({
    queryKey: ["costes-laborales", selectedMes],
    queryFn: () => api.configuracion.costesLaborales.list({ mes: selectedMes }),
  });

  const saveMut = useMutation({
    mutationFn: () => {
      const bruto = parseFloat(form.bruto) || 0;
      const ss_t = parseFloat(form.ss_trabajador) || 0;
      const irpf = parseFloat(form.irpf) || 0;
      const liquido = parseFloat(form.liquido) || 0;
      const ss_e = parseFloat(form.ss_empresa) || 0;
      const coste_total = bruto + ss_e;
      return api.configuracion.costesLaborales.save({
        mes: selectedMes,
        trabajador_id: parseInt(form.trabajador_id) || Date.now(),
        nombre: form.nombre,
        vehiculo_id: form.vehiculo_id || null,
        bruto, ss_trabajador: ss_t, irpf, liquido, ss_empresa: ss_e, coste_total,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["costes-laborales"] });
      setForm({ trabajador_id: "", nombre: "", vehiculo_id: "", bruto: "", ss_trabajador: "", irpf: "", liquido: "", ss_empresa: "" });
      setShowForm(false);
      setSuccessMsg("Coste laboral guardado");
      setTimeout(() => setSuccessMsg(""), 3000);
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.configuracion.costesLaborales.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["costes-laborales"] }),
  });

  const totalCoste = costes.reduce((s: number, c: any) => s + (c.coste_total || 0), 0);

  return (
    <div>
      {successMsg && (
        <div className="mb-4 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2 text-sm text-emerald-700">
          <CheckCircle2 className="w-4 h-4" />
          {successMsg}
        </div>
      )}

      {/* Mes selector + add button */}
      <div className="flex items-center gap-3 mb-5">
        <span className="text-sm font-medium text-gray-500">Mes:</span>
        <select
          value={selectedMes}
          onChange={(e) => setSelectedMes(e.target.value)}
          className="px-3 py-2 bg-white rounded-lg border border-gray-200 text-sm outline-none focus:border-brand-400"
        >
          {mesesDisp.map((m) => (
            <option key={m} value={m}>{formatMes(m)}</option>
          ))}
        </select>

        <button
          onClick={() => setShowForm(!showForm)}
          className="ml-auto px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Anadir trabajador
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="mb-5 p-5 bg-gray-50 rounded-xl border border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Nuevo coste laboral — {formatMes(selectedMes)}</h3>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">ID Trabajador</label>
              <input
                type="number"
                value={form.trabajador_id}
                onChange={(e) => setForm({ ...form, trabajador_id: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                placeholder="1, 2, 3..."
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Nombre</label>
              <input
                type="text"
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                placeholder="Nombre trabajador"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Vehiculo</label>
              <select
                value={form.vehiculo_id}
                onChange={(e) => setForm({ ...form, vehiculo_id: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
              >
                <option value="">-- Sin asignar --</option>
                {VEHICULOS_OP.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
                <option value="COMÚN">COMUN</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Bruto</label>
              <input
                type="number"
                step="0.01"
                value={form.bruto}
                onChange={(e) => setForm({ ...form, bruto: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                placeholder="0.00"
              />
            </div>
          </div>
          <div className="grid grid-cols-5 gap-3 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">SS Trabajador</label>
              <input
                type="number"
                step="0.01"
                value={form.ss_trabajador}
                onChange={(e) => setForm({ ...form, ss_trabajador: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">IRPF</label>
              <input
                type="number"
                step="0.01"
                value={form.irpf}
                onChange={(e) => setForm({ ...form, irpf: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Liquido</label>
              <input
                type="number"
                step="0.01"
                value={form.liquido}
                onChange={(e) => setForm({ ...form, liquido: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">SS Empresa</label>
              <input
                type="number"
                step="0.01"
                value={form.ss_empresa}
                onChange={(e) => setForm({ ...form, ss_empresa: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-white rounded border border-gray-200 outline-none focus:border-brand-400"
                placeholder="0.00"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={() => saveMut.mutate()}
                disabled={!form.nombre || saveMut.isPending}
                className={cn(
                  "w-full px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2",
                  form.nombre
                    ? "bg-brand-500 text-white hover:bg-brand-600"
                    : "bg-gray-200 text-gray-400 cursor-not-allowed"
                )}
              >
                {saveMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Guardar
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-400">Coste total = Bruto + SS Empresa (se calcula automaticamente)</p>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        ) : costes.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <Users className="w-10 h-10 mb-3 text-gray-300" />
            <p className="text-sm font-medium text-gray-600">No hay costes laborales para {formatMes(selectedMes)}</p>
            <p className="text-xs text-gray-400 mt-1">Usa el boton Anadir trabajador para introducir datos</p>
          </div>
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="text-left text-xs font-medium text-gray-400 px-5 py-3 uppercase tracking-wider">ID</th>
                  <th className="text-left text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">Nombre</th>
                  <th className="text-left text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">Vehiculo</th>
                  <th className="text-right text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">Bruto</th>
                  <th className="text-right text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">SS Emp.</th>
                  <th className="text-right text-xs font-medium text-gray-400 px-4 py-3 uppercase tracking-wider">Coste Total</th>
                  <th className="w-16 px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {costes.map((c: any) => (
                  <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50/30">
                    <td className="px-5 py-3 text-sm text-gray-500">{c.trabajador_id}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{c.nombre}</td>
                    <td className="px-4 py-3">
                      {c.vehiculo_id ? (
                        <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-md bg-brand-50 text-brand-700 border border-brand-100">
                          <Truck className="w-3 h-3 mr-1" />
                          {c.vehiculo_id}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-gray-700">{formatImporte(c.bruto)}</td>
                    <td className="px-4 py-3 text-right text-sm text-gray-700">{formatImporte(c.ss_empresa)}</td>
                    <td className="px-4 py-3 text-right text-sm font-semibold text-gray-900">{formatImporte(c.coste_total)}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => deleteMut.mutate(c.id)}
                        className="p-1.5 text-red-400 hover:bg-red-50 rounded transition-colors"
                        title="Eliminar"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-gray-50 border-t border-gray-200">
                  <td colSpan={5} className="px-5 py-3 text-sm font-semibold text-gray-700 text-right">
                    Total {formatMes(selectedMes)}
                  </td>
                  <td className="px-4 py-3 text-right text-sm font-bold text-gray-900">
                    {formatImporte(totalCoste)}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          </>
        )}
      </div>
    </div>
  );
}


// =========================================================
//  Tab: Importar informes
// =========================================================
function ImportarTab() {
  const queryClient = useQueryClient();
  const [resultCostes, setResultCostes] = useState<any>(null);
  const [resultRecorridos, setResultRecorridos] = useState<any>(null);
  const [resultGasoil, setResultGasoil] = useState<any>(null);
  const [errorCostes, setErrorCostes] = useState("");
  const [errorRecorridos, setErrorRecorridos] = useState("");
  const [errorGasoil, setErrorGasoil] = useState("");

  const costesMut = useMutation({
    mutationFn: (file: File) => api.configuracion.importar.costesPdf(file),
    onSuccess: (data) => {
      setResultCostes(data);
      setErrorCostes("");
      queryClient.invalidateQueries({ queryKey: ["costes-laborales"] });
    },
    onError: (err: any) => {
      setErrorCostes(err.message || "Error al procesar PDF");
      setResultCostes(null);
    },
  });

  const recorridosMut = useMutation({
    mutationFn: (file: File) => api.configuracion.importar.recorridosPdf(file),
    onSuccess: (data) => {
      setResultRecorridos(data);
      setErrorRecorridos("");
      queryClient.invalidateQueries({ queryKey: ["km"] });
    },
    onError: (err: any) => {
      setErrorRecorridos(err.message || "Error al procesar PDF");
      setResultRecorridos(null);
    },
  });

  const gasoilMut = useMutation({
    mutationFn: (file: File) => api.configuracion.importar.gasoilPdf(file),
    onSuccess: (data) => {
      setResultGasoil(data);
      setErrorGasoil("");
      queryClient.invalidateQueries({ queryKey: ["costes-matriz"] });
    },
    onError: (err: any) => {
      setErrorGasoil(err.message || "Error al procesar PDF");
      setResultGasoil(null);
    },
  });

  function handleFileChange(
    e: React.ChangeEvent<HTMLInputElement>,
    type: "costes" | "recorridos" | "gasoil"
  ) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (type === "costes") costesMut.mutate(file);
    else if (type === "recorridos") recorridosMut.mutate(file);
    else gasoilMut.mutate(file);
    e.target.value = "";
  }

  return (
    <div className="space-y-6">
      {/* Costes Laborales PDF */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
            <Users className="w-4 h-4 text-indigo-600" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900">Costes Laborales (PDF nominas)</h3>
            <p className="text-xs text-gray-400">Sube el PDF de costes SS/IRPF generado por la gestoria. Formato: COST - YYYYMM - Emp XX.pdf</p>
          </div>
        </div>
        <div className="p-5">
          <label className={cn(
            "flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-xl cursor-pointer transition-colors",
            costesMut.isPending
              ? "border-indigo-300 bg-indigo-50"
              : "border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/30"
          )}>
            {costesMut.isPending ? (
              <div className="flex items-center gap-2 text-indigo-600">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-sm font-medium">Procesando PDF...</span>
              </div>
            ) : (
              <>
                <Upload className="w-6 h-6 text-gray-400 mb-2" />
                <span className="text-sm text-gray-500">Arrastra o haz click para seleccionar PDF de costes</span>
                <span className="text-xs text-gray-400 mt-1">PDF de nominas / costes seguridad social</span>
              </>
            )}
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleFileChange(e, "costes")}
              disabled={costesMut.isPending}
            />
          </label>

          {errorCostes && (
            <div className="mt-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-700">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {errorCostes}
            </div>
          )}

          {resultCostes && (
            <div className="mt-3 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg">
              <div className="flex items-center gap-2 text-sm text-emerald-700 font-medium mb-2">
                <CheckCircle2 className="w-4 h-4" />
                Importados {resultCostes.trabajadores} trabajadores — {resultCostes.mes}
              </div>
              <div className="space-y-1">
                {resultCostes.detalle?.map((t: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 text-xs text-gray-600">
                    <span className="font-medium w-40">{t.nombre}</span>
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] font-medium",
                      t.vehiculo_id === "COMÚN" ? "bg-gray-100 text-gray-600" : "bg-brand-50 text-brand-700"
                    )}>
                      {t.vehiculo_id}
                    </span>
                    <span>Coste: {t.coste_total.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Recorridos PDF */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-orange-50 flex items-center justify-center">
            <MapPin className="w-4 h-4 text-orange-600" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900">Recorridos / Kilometros (PDF Localiza)</h3>
            <p className="text-xs text-gray-400">Sube el PDF de recorridos exportado de Localiza.io. Se extrae vehiculo, mes, km totales y dias trabajados.</p>
          </div>
        </div>
        <div className="p-5">
          <label className={cn(
            "flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-xl cursor-pointer transition-colors",
            recorridosMut.isPending
              ? "border-orange-300 bg-orange-50"
              : "border-gray-200 hover:border-orange-300 hover:bg-orange-50/30"
          )}>
            {recorridosMut.isPending ? (
              <div className="flex items-center gap-2 text-orange-600">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-sm font-medium">Procesando PDF...</span>
              </div>
            ) : (
              <>
                <Upload className="w-6 h-6 text-gray-400 mb-2" />
                <span className="text-sm text-gray-500">Arrastra o haz click para seleccionar PDF de recorridos</span>
                <span className="text-xs text-gray-400 mt-1">PDF exportado de Localiza.io</span>
              </>
            )}
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleFileChange(e, "recorridos")}
              disabled={recorridosMut.isPending}
            />
          </label>

          {errorRecorridos && (
            <div className="mt-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-700">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {errorRecorridos}
            </div>
          )}

          {resultRecorridos && (
            <div className="mt-3 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg">
              <div className="flex items-center gap-2 text-sm text-emerald-700 font-medium">
                <CheckCircle2 className="w-4 h-4" />
                Importado: {resultRecorridos.vehiculo_id} — {resultRecorridos.mes}
              </div>
              <div className="flex items-center gap-4 mt-1 text-xs text-gray-600">
                <span>{resultRecorridos.km_total.toLocaleString("es-ES")} km</span>
                <span>{resultRecorridos.dias_trabajados} dias trabajados</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Gasoil SOLRED PDF */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
            <Truck className="w-4 h-4 text-amber-600" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900">Gasoil SOLRED (PDF factura)</h3>
            <p className="text-xs text-gray-400">Sube el PDF de factura SOLRED. Se extrae el desglose por vehiculo (tarjeta/matricula) y se asigna automaticamente.</p>
          </div>
        </div>
        <div className="p-5">
          <label className={cn(
            "flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-xl cursor-pointer transition-colors",
            gasoilMut.isPending
              ? "border-amber-300 bg-amber-50"
              : "border-gray-200 hover:border-amber-300 hover:bg-amber-50/30"
          )}>
            {gasoilMut.isPending ? (
              <div className="flex items-center gap-2 text-amber-600">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-sm font-medium">Procesando PDF...</span>
              </div>
            ) : (
              <>
                <Upload className="w-6 h-6 text-gray-400 mb-2" />
                <span className="text-sm text-gray-500">Arrastra o haz click para seleccionar PDF de SOLRED</span>
                <span className="text-xs text-gray-400 mt-1">Factura con desglose por tarjeta/matricula</span>
              </>
            )}
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleFileChange(e, "gasoil")}
              disabled={gasoilMut.isPending}
            />
          </label>

          {errorGasoil && (
            <div className="mt-3 px-4 py-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-700">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {errorGasoil}
            </div>
          )}

          {resultGasoil && (
            <div className="mt-3 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-lg">
              <div className="flex items-center gap-2 text-sm text-emerald-700 font-medium mb-2">
                <CheckCircle2 className="w-4 h-4" />
                Factura {resultGasoil.factura} — {resultGasoil.mes} — Total: {resultGasoil.total.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}
              </div>
              <div className="space-y-1">
                {Object.entries(resultGasoil.vehiculos || {}).map(([veh, importe]: [string, any]) => (
                  <div key={veh} className="flex items-center gap-3 text-xs text-gray-600">
                    <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-md bg-brand-50 text-brand-700 border border-brand-100">
                      <Truck className="w-3 h-3 mr-1" />
                      {veh}
                    </span>
                    <span className="font-medium">{importe.toLocaleString("es-ES", { style: "currency", currency: "EUR" })}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


// =========================================================
//  Main page with tabs
// =========================================================
export default function ConfiguracionPage() {
  const [tab, setTab] = useState<"km" | "costes" | "importar">("km");

  return (
    <div className="min-h-screen">
      <Header
        title="Configuracion"
        breadcrumbs={[{ label: "Soporte" }, { label: "Configuracion" }]}
      />

      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Datos Operativos</h1>
          <p className="text-sm text-gray-500 mt-1">
            Introduce kilometros mensuales y costes laborales por vehiculo.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-gray-100 rounded-lg w-fit mb-6">
          <button
            onClick={() => setTab("km")}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-colors",
              tab === "km"
                ? "bg-white text-gray-900 shadow-sm font-medium"
                : "text-gray-500 hover:text-gray-700"
            )}
          >
            <Gauge className="w-4 h-4" />
            Kilometros
          </button>
          <button
            onClick={() => setTab("costes")}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-colors",
              tab === "costes"
                ? "bg-white text-gray-900 shadow-sm font-medium"
                : "text-gray-500 hover:text-gray-700"
            )}
          >
            <Users className="w-4 h-4" />
            Costes Laborales
          </button>
          <button
            onClick={() => setTab("importar")}
            className={cn(
              "flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-colors",
              tab === "importar"
                ? "bg-white text-gray-900 shadow-sm font-medium"
                : "text-gray-500 hover:text-gray-700"
            )}
          >
            <Upload className="w-4 h-4" />
            Importar Informes
          </button>
        </div>

        {/* Tab content */}
        {tab === "km" ? <KilometrosTab /> : tab === "costes" ? <CostesLaboralesTab /> : <ImportarTab />}
      </div>
    </div>
  );
}
