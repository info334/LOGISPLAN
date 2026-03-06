"use client";

import { useQuery } from "@tanstack/react-query";
import { Truck, Wallet, TrendingUp, FileWarning } from "lucide-react";
import Header from "@/components/layout/header";
import KpiCard from "@/components/dashboard/kpi-card";
import TrendChart from "@/components/dashboard/trend-chart";
import MonitoringTable from "@/components/dashboard/monitoring-table";
import { api } from "@/lib/api";
import { formatImporte } from "@/lib/utils";

export default function DashboardPage() {
  const { data: kpis } = useQuery({
    queryKey: ["dashboard", "kpis"],
    queryFn: api.dashboard.kpis,
  });

  const { data: trend } = useQuery({
    queryKey: ["dashboard", "trend"],
    queryFn: () => api.dashboard.trend("month"),
  });

  const { data: monitoring } = useQuery({
    queryKey: ["dashboard", "monitoring"],
    queryFn: api.dashboard.monitoring,
  });

  return (
    <div className="min-h-screen">
      <Header
        title="Dashboard"
        breadcrumbs={[
          { label: "Resumen" },
          { label: "Dashboard" },
        ]}
      />

      <div className="p-6">
        {/* Welcome */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Hola, Severino Logistica
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Aqui tienes los ultimos datos de tu flota de transporte.
          </p>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <KpiCard
            title="Vehiculos Activos"
            value={String(kpis?.vehiculos_activos ?? 4)}
            icon={Truck}
            iconColor="text-blue-500"
            sparklineData={[3, 4, 4, 4, 4, 4, 4]}
          />
          <KpiCard
            title="Gastos del Mes"
            value={formatImporte(kpis?.gastos_mes ?? 0)}
            change={kpis?.gastos_cambio_pct ?? 0}
            changeLabel="vs mes anterior"
            icon={Wallet}
            iconColor="text-amber-500"
            sparklineData={[420, 380, 450, 510, 480, 520, 490]}
          />
          <KpiCard
            title="Rentabilidad"
            value={`${(kpis?.rentabilidad_pct ?? 0).toFixed(1)}%`}
            icon={TrendingUp}
            iconColor="text-emerald-500"
            sparklineData={[8, 12, 10, 14, 11, 13, 15]}
          />
          <KpiCard
            title="Facturas Pendientes"
            value={String(kpis?.facturas_pendientes ?? 0)}
            icon={FileWarning}
            iconColor="text-red-500"
          />
        </div>

        {/* Trend Chart */}
        <div className="mb-6">
          <TrendChart data={trend ?? []} />
        </div>

        {/* Monitoring Table */}
        <MonitoringTable data={monitoring ?? []} />
      </div>
    </div>
  );
}
