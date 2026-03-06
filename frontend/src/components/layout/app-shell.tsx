"use client";

import { useState } from "react";
import Sidebar from "./sidebar";
import ActivityPanel from "./activity-panel";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { cn } from "@/lib/utils";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [panelOpen, setPanelOpen] = useState(true);

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main
        className={cn(
          "flex-1 ml-[260px] transition-[margin] duration-300 ease-in-out",
          panelOpen ? "mr-[320px]" : "mr-0"
        )}
      >
        {/* Toggle button */}
        <button
          onClick={() => setPanelOpen(!panelOpen)}
          className="fixed top-[18px] z-40 p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-all duration-300"
          style={{ right: panelOpen ? "332px" : "12px" }}
          title={panelOpen ? "Ocultar panel" : "Mostrar panel"}
        >
          {panelOpen ? (
            <PanelRightClose className="w-5 h-5" />
          ) : (
            <PanelRightOpen className="w-5 h-5" />
          )}
        </button>

        {children}
      </main>

      {/* Activity Panel con animación */}
      <div
        className={cn(
          "fixed right-0 top-0 bottom-0 w-[320px] transition-transform duration-300 ease-in-out z-20",
          panelOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        <ActivityPanel />
      </div>
    </div>
  );
}
