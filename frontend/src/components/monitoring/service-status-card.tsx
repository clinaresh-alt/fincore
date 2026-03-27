"use client";

import { CheckCircle2, XCircle, AlertTriangle, HelpCircle, Wifi } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ServiceStatusCardProps {
  name: string;
  displayName: string;
  status: string;
  latency?: number | null;
  error?: string | null;
}

const STATUS_CONFIG: Record<string, { icon: React.ElementType; color: string; bgColor: string; label: string }> = {
  healthy: {
    icon: CheckCircle2,
    color: "text-green-600",
    bgColor: "bg-green-50 border-green-200",
    label: "Operativo",
  },
  degraded: {
    icon: AlertTriangle,
    color: "text-yellow-600",
    bgColor: "bg-yellow-50 border-yellow-200",
    label: "Degradado",
  },
  down: {
    icon: XCircle,
    color: "text-red-600",
    bgColor: "bg-red-50 border-red-200",
    label: "Caido",
  },
  unknown: {
    icon: HelpCircle,
    color: "text-gray-600",
    bgColor: "bg-gray-50 border-gray-200",
    label: "Desconocido",
  },
};

const SERVICE_ICONS: Record<string, React.ElementType> = {
  database: () => (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
    </svg>
  ),
  redis: () => (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M10.5 2.661l.54.997-1.797.644 2.409.218.748 1.246.467-1.165 2.384-.22-1.72-.644.54-.997-1.064.172-.803-1.176-.81 1.176-1.064-.172zm8.5 3.339c-1.5 0-3 .5-4.5 1.5-1.5 1-3 1.5-4.5 1.5s-3-.5-4.5-1.5c-1.5-1-3-1.5-4.5-1.5v14c1.5 0 3 .5 4.5 1.5 1.5 1 3 1.5 4.5 1.5s3-.5 4.5-1.5c1.5-1 3-1.5 4.5-1.5v-14z"/>
    </svg>
  ),
  stp: () => (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
    </svg>
  ),
  bitso: () => (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  blockchain: () => (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
    </svg>
  ),
};

export function ServiceStatusCard({ name, displayName, status, latency, error }: ServiceStatusCardProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.unknown;
  const StatusIcon = config.icon;
  const ServiceIcon = SERVICE_ICONS[name] || Wifi;

  return (
    <Card className={cn("border transition-all", config.bgColor)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn("p-2 rounded-lg", config.color, "bg-white/50")}>
              <ServiceIcon />
            </div>
            <div>
              <h3 className="font-semibold text-sm">{displayName}</h3>
              <div className="flex items-center gap-2 mt-0.5">
                <StatusIcon className={cn("h-3.5 w-3.5", config.color)} />
                <span className={cn("text-xs font-medium", config.color)}>
                  {config.label}
                </span>
              </div>
            </div>
          </div>
          {latency !== null && latency !== undefined && status === "healthy" && (
            <div className="text-right">
              <span className="text-lg font-bold text-gray-900">{latency.toFixed(0)}</span>
              <span className="text-xs text-gray-500 ml-1">ms</span>
            </div>
          )}
        </div>
        {error && (
          <div className="mt-2 text-xs text-red-600 bg-red-100 rounded px-2 py-1 truncate">
            {error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
