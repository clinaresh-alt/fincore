/**
 * Tests para utilidades de lib/utils.ts
 */

import { describe, it, expect } from "vitest";
import {
  cn,
  formatCurrency,
  formatPercentage,
  formatDate,
  getRiskLevelColor,
  getProjectStatusColor,
} from "@/lib/utils";

describe("cn (className merge)", () => {
  it("combina clases simples", () => {
    const result = cn("foo", "bar");
    expect(result).toBe("foo bar");
  });

  it("maneja clases condicionales", () => {
    const result = cn("base", true && "active", false && "hidden");
    expect(result).toBe("base active");
  });

  it("resuelve conflictos de Tailwind", () => {
    const result = cn("p-4", "p-8");
    expect(result).toBe("p-8");
  });

  it("combina clases de diferentes grupos", () => {
    const result = cn("text-red-500", "bg-blue-500");
    expect(result).toContain("text-red-500");
    expect(result).toContain("bg-blue-500");
  });

  it("maneja arrays de clases", () => {
    const result = cn(["foo", "bar"], "baz");
    expect(result).toBe("foo bar baz");
  });

  it("maneja objetos con condiciones", () => {
    const result = cn({
      base: true,
      active: true,
      hidden: false,
    });
    expect(result).toBe("base active");
  });

  it("retorna string vacio para inputs vacios", () => {
    const result = cn();
    expect(result).toBe("");
  });

  it("ignora valores undefined y null", () => {
    const result = cn("foo", undefined, null, "bar");
    expect(result).toBe("foo bar");
  });
});

describe("formatCurrency", () => {
  it("formatea moneda MXN por defecto", () => {
    const result = formatCurrency(1000);
    expect(result).toContain("1,000");
    // MXN currency in es-MX locale uses $ symbol
    expect(result).toContain("$");
  });

  it("formatea valores con decimales", () => {
    const result = formatCurrency(1234.56);
    expect(result).toContain("1,234.56");
  });

  it("formatea valores negativos", () => {
    const result = formatCurrency(-500);
    expect(result).toContain("500");
    expect(result).toContain("-");
  });

  it("formatea cero correctamente", () => {
    const result = formatCurrency(0);
    expect(result).toContain("0.00");
  });

  it("formatea valores grandes", () => {
    const result = formatCurrency(1000000);
    expect(result).toContain("1,000,000");
  });

  it("acepta moneda USD", () => {
    const result = formatCurrency(100, "USD", "en-US");
    expect(result).toContain("$");
    expect(result).toContain("100");
  });

  it("acepta moneda EUR", () => {
    const result = formatCurrency(100, "EUR", "de-DE");
    expect(result).toContain("100");
  });

  it("mantiene 2 decimales", () => {
    const result = formatCurrency(100.1);
    expect(result).toContain("100.10");
  });
});

describe("formatPercentage", () => {
  it("formatea porcentaje basico", () => {
    const result = formatPercentage(0.15);
    expect(result).toBe("15.00%");
  });

  it("formatea 100%", () => {
    const result = formatPercentage(1);
    expect(result).toBe("100.00%");
  });

  it("formatea 0%", () => {
    const result = formatPercentage(0);
    expect(result).toBe("0.00%");
  });

  it("formatea porcentajes negativos", () => {
    const result = formatPercentage(-0.1);
    expect(result).toBe("-10.00%");
  });

  it("respeta decimales personalizados", () => {
    const result = formatPercentage(0.12345, 1);
    expect(result).toBe("12.3%");
  });

  it("maneja sin decimales", () => {
    const result = formatPercentage(0.5, 0);
    expect(result).toBe("50%");
  });

  it("formatea valores mayores a 100%", () => {
    const result = formatPercentage(1.5);
    expect(result).toBe("150.00%");
  });

  it("formatea valores muy pequenos", () => {
    const result = formatPercentage(0.001, 2);
    expect(result).toBe("0.10%");
  });
});

describe("formatDate", () => {
  it("formatea fecha string ISO", () => {
    const result = formatDate("2024-01-15T12:00:00");
    expect(result).toContain("2024");
    expect(result).toContain("15");
  });

  it("formatea objeto Date", () => {
    const date = new Date(2024, 0, 15);
    const result = formatDate(date);
    expect(result).toContain("2024");
    expect(result).toContain("15");
  });

  it("acepta opciones personalizadas", () => {
    const result = formatDate("2024-06-20", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
    expect(result).toContain("2024");
    expect(result).toContain("20");
  });

  it("usa locale es-MX", () => {
    const result = formatDate("2024-03-15");
    // En espanol, marzo deberia aparecer
    expect(result).toMatch(/mar|Mar|marzo|Marzo/i);
  });
});

describe("getRiskLevelColor", () => {
  it("retorna color verde para AAA", () => {
    const result = getRiskLevelColor("AAA");
    expect(result).toContain("green-600");
    expect(result).toContain("bg-green-100");
  });

  it("retorna color verde claro para AA", () => {
    const result = getRiskLevelColor("AA");
    expect(result).toContain("green-500");
  });

  it("retorna color amarillo para A", () => {
    const result = getRiskLevelColor("A");
    expect(result).toContain("yellow-600");
  });

  it("retorna color naranja para B", () => {
    const result = getRiskLevelColor("B");
    expect(result).toContain("orange-600");
  });

  it("retorna color rojo para C", () => {
    const result = getRiskLevelColor("C");
    expect(result).toContain("red-600");
  });

  it("retorna gris para nivel desconocido", () => {
    const result = getRiskLevelColor("X");
    expect(result).toContain("gray-600");
  });

  it("retorna gris para string vacio", () => {
    const result = getRiskLevelColor("");
    expect(result).toContain("gray");
  });
});

describe("getProjectStatusColor", () => {
  it("retorna azul para En Evaluacion", () => {
    const result = getProjectStatusColor("En Evaluacion");
    expect(result).toContain("blue-600");
  });

  it("retorna verde para Aprobado", () => {
    const result = getProjectStatusColor("Aprobado");
    expect(result).toContain("green-600");
  });

  it("retorna rojo para Rechazado", () => {
    const result = getProjectStatusColor("Rechazado");
    expect(result).toContain("red-600");
  });

  it("retorna amarillo para Financiando", () => {
    const result = getProjectStatusColor("Financiando");
    expect(result).toContain("yellow-600");
  });

  it("retorna morado para Financiado", () => {
    const result = getProjectStatusColor("Financiado");
    expect(result).toContain("purple-600");
  });

  it("retorna indigo para En Ejecucion", () => {
    const result = getProjectStatusColor("En Ejecucion");
    expect(result).toContain("indigo-600");
  });

  it("retorna esmeralda para Completado", () => {
    const result = getProjectStatusColor("Completado");
    expect(result).toContain("emerald-600");
  });

  it("retorna rojo oscuro para Default", () => {
    const result = getProjectStatusColor("Default");
    expect(result).toContain("red-800");
  });

  it("retorna gris para estado desconocido", () => {
    const result = getProjectStatusColor("Estado Desconocido");
    expect(result).toContain("gray-600");
  });
});
