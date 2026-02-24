import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Formatea un numero como moneda
 */
export function formatCurrency(
  value: number,
  currency: string = "MXN",
  locale: string = "es-MX"
): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Formatea un numero como porcentaje
 */
export function formatPercentage(
  value: number,
  decimals: number = 2
): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Formatea una fecha
 */
export function formatDate(
  date: string | Date,
  options?: Intl.DateTimeFormatOptions
): string {
  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
    ...options,
  };
  return new Date(date).toLocaleDateString("es-MX", defaultOptions);
}

/**
 * Obtiene el color del nivel de riesgo
 */
export function getRiskLevelColor(level: string): string {
  const colors: Record<string, string> = {
    AAA: "text-green-600 bg-green-100",
    AA: "text-green-500 bg-green-50",
    A: "text-yellow-600 bg-yellow-100",
    B: "text-orange-600 bg-orange-100",
    C: "text-red-600 bg-red-100",
  };
  return colors[level] || "text-gray-600 bg-gray-100";
}

/**
 * Obtiene el color del estado del proyecto
 */
export function getProjectStatusColor(status: string): string {
  const colors: Record<string, string> = {
    "En Evaluacion": "text-blue-600 bg-blue-100",
    Aprobado: "text-green-600 bg-green-100",
    Rechazado: "text-red-600 bg-red-100",
    Financiando: "text-yellow-600 bg-yellow-100",
    Financiado: "text-purple-600 bg-purple-100",
    "En Ejecucion": "text-indigo-600 bg-indigo-100",
    Completado: "text-emerald-600 bg-emerald-100",
    Default: "text-red-800 bg-red-200",
  };
  return colors[status] || "text-gray-600 bg-gray-100";
}
