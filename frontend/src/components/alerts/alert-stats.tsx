"use client";

import { AlertTriangle, AlertCircle, CheckCircle2, BellOff, XCircle, Info } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { AlertSummary } from "@/types";

interface AlertStatsProps {
  summary: AlertSummary;
}

export function AlertStats({ summary }: AlertStatsProps) {
  const stats = [
    {
      label: "Activas",
      value: summary.total_active,
      icon: AlertTriangle,
      color: "text-red-600",
      bg: "bg-red-50",
    },
    {
      label: "Criticas",
      value: summary.by_severity.critical || 0,
      icon: XCircle,
      color: "text-red-700",
      bg: "bg-red-100",
    },
    {
      label: "Errores",
      value: summary.by_severity.error || 0,
      icon: AlertCircle,
      color: "text-orange-600",
      bg: "bg-orange-50",
    },
    {
      label: "Warnings",
      value: summary.by_severity.warning || 0,
      icon: AlertTriangle,
      color: "text-yellow-600",
      bg: "bg-yellow-50",
    },
    {
      label: "Info",
      value: summary.by_severity.info || 0,
      icon: Info,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {stats.map((stat) => (
        <Card key={stat.label} className={cn("border", stat.value > 0 && "border-current", stat.color)}>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className={cn("p-2 rounded-lg", stat.bg)}>
                <stat.icon className={cn("h-5 w-5", stat.color)} />
              </div>
              <div>
                <div className="text-2xl font-bold">{stat.value}</div>
                <div className="text-xs text-muted-foreground">{stat.label}</div>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
