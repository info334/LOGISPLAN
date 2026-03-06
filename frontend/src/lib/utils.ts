import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatImporte(valor: number): string {
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
  }).format(valor);
}

export function formatPercent(valor: number): string {
  return `${valor >= 0 ? "+" : ""}${valor.toFixed(1)}%`;
}

export function formatFecha(fecha: string): string {
  if (!fecha) return "";
  const d = new Date(fecha);
  return d.toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
