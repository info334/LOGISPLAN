const API_BASE = "/api";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export interface DashboardKpis {
  vehiculos_activos: number;
  gastos_mes: number;
  gastos_cambio_pct: number;
  rentabilidad_pct: number;
  facturas_pendientes: number;
}

export interface TrendItem {
  periodo: string;
  ingresos: number;
  gastos: number;
  balance: number;
}

export interface ActivityItem {
  tipo: string;
  descripcion: string;
  detalle: string;
  timestamp: string;
}

export interface MonitoringItem {
  vehiculo_id: string;
  facturacion: number;
  resultado_neto: number;
  rentabilidad_pct: number;
  estado: "perdidas" | "bajo" | "aceptable" | "bueno";
  ultimo_movimiento: string;
  periodo: string;
}

export interface HoldedStatus {
  connected: boolean;
  error?: string;
  last_sync?: string;
  treasury_accounts?: number;
}

export interface SyncResult {
  facturas?: { importadas: number; errores: number; detalle: any[] };
  gastos?: { insertados: number; duplicados: number; total_descargados: number; errores: number; detalle: any[] };
  tesoreria?: { cuentas: any[] };
  timestamp: string;
  errores_globales: string[];
}

async function uploadPdf(path: string, file: File): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export const api = {
  dashboard: {
    kpis: () => fetchApi<DashboardKpis>("/dashboard/kpis"),
    trend: (period = "month") =>
      fetchApi<TrendItem[]>(`/dashboard/trend?period=${period}`),
    activity: (limit = 10) =>
      fetchApi<ActivityItem[]>(`/dashboard/activity?limit=${limit}`),
    monitoring: () => fetchApi<MonitoringItem[]>("/dashboard/monitoring"),
    rentabilidadMatriz: () => fetchApi<any>("/dashboard/rentabilidad-matriz"),
    costesMatriz: () => fetchApi<any>("/dashboard/costes-matriz"),
  },
  vehiculos: {
    list: () => fetchApi<any[]>("/vehiculos"),
    operativos: () => fetchApi<any[]>("/vehiculos/operativos"),
    rentabilidad: (id: string) =>
      fetchApi<any>(`/vehiculos/${id}/rentabilidad`),
  },
  movimientos: {
    list: (params?: Record<string, string>) => {
      const qs = params
        ? "?" + new URLSearchParams(params).toString()
        : "";
      return fetchApi<any>(`/movimientos${qs}`);
    },
    opciones: () => fetchApi<{ vehiculos: any[]; categorias: any[] }>("/movimientos/opciones"),
    asignar: (id: number, data: { vehiculo_id?: string; categoria_id?: string }) =>
      fetchApi<any>(`/movimientos/${id}/asignar`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    asignarBatch: (ids: number[], vehiculo_id?: string, categoria_id?: string) =>
      fetchApi<any>("/movimientos/asignar-batch", {
        method: "PUT",
        body: JSON.stringify({ ids, vehiculo_id, categoria_id }),
      }),
  },
  facturacion: {
    list: (params?: Record<string, string>) => {
      const qs = params
        ? "?" + new URLSearchParams(params).toString()
        : "";
      return fetchApi<any[]>(`/facturacion${qs}`);
    },
    resumen: () => fetchApi<any[]>("/facturacion/resumen"),
    periodos: () => fetchApi<string[]>("/facturacion/periodos"),
    asignarVehiculo: (id: number, vehiculo_id: string) =>
      fetchApi<any>(`/facturacion/${id}/asignar`, {
        method: "PUT",
        body: JSON.stringify({ vehiculo_id }),
      }),
  },
  configuracion: {
    categorias: () => fetchApi<any[]>("/configuracion/categorias"),
    reglas: () => fetchApi<any[]>("/configuracion/reglas"),
    km: {
      list: (params?: Record<string, string>) => {
        const qs = params ? "?" + new URLSearchParams(params).toString() : "";
        return fetchApi<any[]>(`/configuracion/km${qs}`);
      },
      save: (data: { mes: string; vehiculo_id: string; km: number }) =>
        fetchApi<any>("/configuracion/km", { method: "POST", body: JSON.stringify(data) }),
      saveBatch: (datos: { mes: string; vehiculo_id: string; km: number }[]) =>
        fetchApi<any>("/configuracion/km/batch", { method: "POST", body: JSON.stringify(datos) }),
      delete: (id: number) =>
        fetchApi<any>(`/configuracion/km/${id}`, { method: "DELETE" }),
    },
    costesLaborales: {
      list: (params?: Record<string, string>) => {
        const qs = params ? "?" + new URLSearchParams(params).toString() : "";
        return fetchApi<any[]>(`/configuracion/costes-laborales${qs}`);
      },
      save: (data: any) =>
        fetchApi<any>("/configuracion/costes-laborales", { method: "POST", body: JSON.stringify(data) }),
      delete: (id: number) =>
        fetchApi<any>(`/configuracion/costes-laborales/${id}`, { method: "DELETE" }),
    },
    importar: {
      costesPdf: (file: File) => uploadPdf("/configuracion/importar/costes-pdf", file),
      gasoilPdf: (file: File) => uploadPdf("/configuracion/importar/gasoil-pdf", file),
      recorridosPdf: (file: File) => uploadPdf("/configuracion/importar/recorridos-pdf", file),
    },
  },
  holded: {
    status: () => fetchApi<HoldedStatus>("/holded/status"),
    configure: (apiKey: string) =>
      fetchApi<any>("/holded/configure", {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey }),
      }),
    syncFacturas: (mesDesde?: string, mesHasta?: string) => {
      const params = new URLSearchParams();
      if (mesDesde) params.set("mes_desde", mesDesde);
      if (mesHasta) params.set("mes_hasta", mesHasta);
      const qs = params.toString() ? `?${params.toString()}` : "";
      return fetchApi<any>(`/holded/sync/facturas${qs}`, { method: "POST" });
    },
    syncGastos: (mesDesde?: string, mesHasta?: string) => {
      const params = new URLSearchParams();
      if (mesDesde) params.set("mes_desde", mesDesde);
      if (mesHasta) params.set("mes_hasta", mesHasta);
      const qs = params.toString() ? `?${params.toString()}` : "";
      return fetchApi<any>(`/holded/sync/gastos${qs}`, { method: "POST" });
    },
    syncTodo: (mesDesde?: string, mesHasta?: string) => {
      const params = new URLSearchParams();
      if (mesDesde) params.set("mes_desde", mesDesde);
      if (mesHasta) params.set("mes_hasta", mesHasta);
      const qs = params.toString() ? `?${params.toString()}` : "";
      return fetchApi<SyncResult>(`/holded/sync/todo${qs}`, { method: "POST" });
    },
    tesoreria: () => fetchApi<any>("/holded/tesoreria"),
    reaplicarReglas: () =>
      fetchApi<{ total_revisados: number; actualizados: number }>(
        "/holded/reaplicar-reglas",
        { method: "POST" }
      ),
    resync: (mesDesde?: string, mesHasta?: string) => {
      const params = new URLSearchParams();
      if (mesDesde) params.set("mes_desde", mesDesde);
      if (mesHasta) params.set("mes_hasta", mesHasta);
      const qs = params.toString() ? `?${params.toString()}` : "";
      return fetchApi<any>(`/holded/resync${qs}`, { method: "POST" });
    },
  },
};
