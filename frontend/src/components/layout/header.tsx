"use client";

import { Bell, Settings, ChevronDown } from "lucide-react";
import { useState } from "react";

interface HeaderProps {
  title: string;
  subtitle?: string;
  breadcrumbs?: { label: string; href?: string }[];
}

export default function Header({ title, subtitle, breadcrumbs }: HeaderProps) {
  const [period, setPeriod] = useState("Ultima semana");

  return (
    <header className="h-16 border-b border-gray-100 bg-white flex items-center justify-between px-6">
      {/* Left: Breadcrumbs */}
      <div className="flex items-center gap-2 text-sm text-gray-400">
        {breadcrumbs?.map((crumb, i) => (
          <span key={i} className="flex items-center gap-2">
            {i > 0 && <span>/</span>}
            <span
              className={
                i === breadcrumbs.length - 1
                  ? "text-gray-700 font-medium"
                  : ""
              }
            >
              {crumb.label}
            </span>
          </span>
        ))}
      </div>

      {/* Right: Period + Notifications + Settings */}
      <div className="flex items-center gap-3">
        <button className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg text-sm text-gray-600 hover:bg-gray-100 transition-colors">
          {period}
          <ChevronDown className="w-4 h-4" />
        </button>
        <button className="relative p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded-lg transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
        </button>
        <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded-lg transition-colors">
          <Settings className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
}
