"use client";

import { Truck } from "lucide-react";
import Header from "@/components/layout/header";

export default function VehiculosPage() {
  return (
    <div className="min-h-screen">
      <Header
        title="Vehiculos"
        breadcrumbs={[{ label: "Navegacion" }, { label: "Vehiculos" }]}
      />
      <div className="flex flex-col items-center justify-center py-32 text-gray-400">
        <Truck className="w-16 h-16 mb-4 text-gray-300" />
        <h2 className="text-xl font-semibold text-gray-600 mb-2">Vehiculos</h2>
        <p className="text-sm">Vista de flota y rentabilidad por vehiculo</p>
        <span className="mt-4 px-3 py-1 bg-gray-100 rounded-full text-xs font-medium text-gray-500">
          Proximamente
        </span>
      </div>
    </div>
  );
}
