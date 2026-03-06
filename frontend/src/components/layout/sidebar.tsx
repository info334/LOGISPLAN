"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Truck,
  FileDown,
  Receipt,
  TrendingUp,
  PieChart,
  FileText,
  Settings,
  Link2,
  HelpCircle,
  ChevronDown,
  Search,
  Command,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  children?: { label: string; href: string }[];
}

const mainNav: NavItem[] = [
  { label: "Resumen", href: "/dashboard", icon: LayoutDashboard },
  {
    label: "Vehiculos",
    href: "/vehiculos",
    icon: Truck,
    children: [
      { label: "Todos", href: "/vehiculos" },
      { label: "Rentabilidad", href: "/vehiculos/rentabilidad" },
    ],
  },
  { label: "Importar", href: "/importar", icon: FileDown },
  { label: "Facturacion", href: "/facturacion", icon: Receipt },
];

const analyticsNav: NavItem[] = [
  { label: "Rentabilidad", href: "/analytics/rentabilidad", icon: TrendingUp },
  { label: "Costes", href: "/analytics/costes", icon: PieChart },
  { label: "Reportes", href: "/analytics/reportes", icon: FileText },
];

const supportNav: NavItem[] = [
  { label: "Integraciones", href: "/integraciones", icon: Link2 },
  { label: "Configuracion", href: "/configuracion", icon: Settings },
  { label: "Ayuda", href: "/ayuda", icon: HelpCircle },
];

function NavSection({
  title,
  items,
  pathname,
}: {
  title: string;
  items: NavItem[];
  pathname: string;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <div className="mb-6">
      <p className="px-4 mb-2 text-[11px] font-semibold tracking-wider text-gray-400 uppercase">
        {title}
      </p>
      <nav className="space-y-0.5">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          const hasChildren = item.children && item.children.length > 0;
          const isExpanded = expanded[item.href] ?? isActive;

          return (
            <div key={item.href}>
              <Link
                href={item.href}
                onClick={(e) => {
                  if (hasChildren) {
                    e.preventDefault();
                    setExpanded((prev) => ({
                      ...prev,
                      [item.href]: !prev[item.href],
                    }));
                  }
                }}
                className={cn(
                  "flex items-center gap-3 px-4 py-2.5 text-sm rounded-lg mx-2 transition-colors",
                  isActive
                    ? "bg-brand-500 text-white font-medium"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >
                <Icon className="w-[18px] h-[18px] flex-shrink-0" />
                <span className="flex-1">{item.label}</span>
                {hasChildren && (
                  <ChevronDown
                    className={cn(
                      "w-4 h-4 transition-transform",
                      isExpanded && "rotate-180"
                    )}
                  />
                )}
              </Link>
              {hasChildren && isExpanded && (
                <div className="ml-11 mt-0.5 space-y-0.5">
                  {item.children!.map((child) => (
                    <Link
                      key={child.href}
                      href={child.href}
                      className={cn(
                        "block px-3 py-1.5 text-sm rounded-md transition-colors",
                        pathname === child.href
                          ? "text-brand-500 font-medium bg-brand-50"
                          : "text-gray-500 hover:text-gray-700"
                      )}
                    >
                      {child.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>
    </div>
  );
}

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[260px] bg-white border-r border-gray-200 flex flex-col z-30">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 h-16 border-b border-gray-100">
        <div className="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
          <Truck className="w-5 h-5 text-white" />
        </div>
        <span className="text-lg font-bold text-gray-900">LogisPLAN</span>
      </div>

      {/* Search */}
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg text-gray-400 text-sm">
          <Search className="w-4 h-4" />
          <span className="flex-1">Buscar...</span>
          <kbd className="flex items-center gap-0.5 px-1.5 py-0.5 bg-white rounded border border-gray-200 text-[11px] font-medium">
            <Command className="w-3 h-3" /> K
          </kbd>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto py-2">
        <NavSection
          title="Navegacion Principal"
          items={mainNav}
          pathname={pathname}
        />
        <NavSection
          title="Analisis e Insights"
          items={analyticsNav}
          pathname={pathname}
        />
        <NavSection title="Soporte" items={supportNav} pathname={pathname} />
      </div>

      {/* User */}
      <div className="border-t border-gray-100 p-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-brand-100 rounded-full flex items-center justify-center text-brand-600 font-semibold text-sm">
            SL
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">
              Severino Logistica
            </p>
            <p className="text-xs text-gray-400 truncate">info@sevefernandez.com</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
