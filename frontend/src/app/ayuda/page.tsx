"use client";

import { HelpCircle } from "lucide-react";
import Header from "@/components/layout/header";

export default function AyudaPage() {
  return (
    <div className="min-h-screen">
      <Header
        title="Ayuda"
        breadcrumbs={[{ label: "Soporte" }, { label: "Ayuda" }]}
      />
      <div className="flex flex-col items-center justify-center py-32 text-gray-400">
        <HelpCircle className="w-16 h-16 mb-4 text-gray-300" />
        <h2 className="text-xl font-semibold text-gray-600 mb-2">Ayuda</h2>
        <p className="text-sm">Documentacion y soporte de LogisPLAN</p>
        <span className="mt-4 px-3 py-1 bg-gray-100 rounded-full text-xs font-medium text-gray-500">
          Proximamente
        </span>
      </div>
    </div>
  );
}
