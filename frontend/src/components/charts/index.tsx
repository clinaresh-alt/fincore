"use client";

import dynamic from "next/dynamic";

// Lazy loading de componentes de charts para mejor rendimiento
// Los charts solo se cargan cuando realmente se necesitan

export const PortfolioChart = dynamic(
  () => import("./portfolio-chart").then((mod) => mod.PortfolioChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] w-full flex items-center justify-center bg-muted/20 rounded-lg animate-pulse">
        <span className="text-muted-foreground text-sm">Cargando grafico...</span>
      </div>
    ),
  }
);

export const CashFlowChart = dynamic(
  () => import("./cashflow-chart").then((mod) => mod.CashFlowChart),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] w-full flex items-center justify-center bg-muted/20 rounded-lg animate-pulse">
        <span className="text-muted-foreground text-sm">Cargando grafico...</span>
      </div>
    ),
  }
);
