"use client";

import Link from "next/link";
import { ArrowRight, Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import type { Remittance, RemittanceStatus } from "@/types";

interface RecentRemittancesProps {
  remittances: Remittance[];
  isLoading?: boolean;
}

const statusConfig: Record<
  RemittanceStatus,
  {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    variant: "pending" | "processing" | "completed" | "failed" | "cancelled" | "default";
  }
> = {
  initiated: {
    label: "Iniciada",
    icon: Clock,
    variant: "default",
  },
  pending_deposit: {
    label: "Esperando depósito",
    icon: Clock,
    variant: "pending",
  },
  deposited: {
    label: "Depositado",
    icon: Loader2,
    variant: "processing",
  },
  locked: {
    label: "En escrow",
    icon: Loader2,
    variant: "processing",
  },
  processing: {
    label: "Procesando",
    icon: Loader2,
    variant: "processing",
  },
  disbursed: {
    label: "Enviado",
    icon: Loader2,
    variant: "processing",
  },
  completed: {
    label: "Completada",
    icon: CheckCircle2,
    variant: "completed",
  },
  refund_pending: {
    label: "Reembolso pendiente",
    icon: Clock,
    variant: "pending",
  },
  refunded: {
    label: "Reembolsada",
    icon: CheckCircle2,
    variant: "default",
  },
  failed: {
    label: "Fallida",
    icon: XCircle,
    variant: "failed",
  },
  cancelled: {
    label: "Cancelada",
    icon: XCircle,
    variant: "cancelled",
  },
  expired: {
    label: "Expirada",
    icon: XCircle,
    variant: "cancelled",
  },
};

function RemittanceItem({ remittance }: { remittance: Remittance }) {
  const status = statusConfig[remittance.status];
  const StatusIcon = status.icon;
  const isProcessing = ["deposited", "locked", "processing", "disbursed"].includes(
    remittance.status
  );

  return (
    <Link href={`/remittances/${remittance.id}`}>
      <div className="flex items-center justify-between py-3 px-4 -mx-4 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer group">
        <div className="flex items-center gap-3">
          <div
            className={`h-10 w-10 rounded-full flex items-center justify-center text-sm font-semibold
              ${
                remittance.status === "completed"
                  ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                  : remittance.status === "failed" || remittance.status === "cancelled"
                  ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                  : "bg-primary/10 text-primary"
              }
            `}
          >
            {remittance.recipient_info.name
              .split(" ")
              .map((n) => n[0])
              .slice(0, 2)
              .join("")
              .toUpperCase()}
          </div>
          <div>
            <p className="font-medium text-sm">
              {remittance.recipient_info.name}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatRelativeTime(remittance.created_at)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="font-medium text-sm">
              {formatCurrency(
                remittance.amount_fiat_destination,
                remittance.currency_destination
              )}
            </p>
            <div className="flex items-center justify-end gap-1">
              <StatusIcon
                className={`h-3 w-3 ${
                  isProcessing ? "animate-spin" : ""
                } ${
                  remittance.status === "completed"
                    ? "text-green-600"
                    : remittance.status === "failed"
                    ? "text-red-600"
                    : "text-muted-foreground"
                }`}
              />
              <Badge variant={status.variant} className="text-[10px] px-1.5 py-0">
                {status.label}
              </Badge>
            </div>
          </div>
          <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    </Link>
  );
}

export function RecentRemittances({
  remittances,
  isLoading = false,
}: RecentRemittancesProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-lg font-semibold">Envíos recientes</CardTitle>
          <Skeleton className="h-8 w-20" />
        </CardHeader>
        <CardContent>
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center justify-between py-3">
              <div className="flex items-center gap-3">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div>
                  <Skeleton className="h-4 w-24 mb-1" />
                  <Skeleton className="h-3 w-16" />
                </div>
              </div>
              <div className="text-right">
                <Skeleton className="h-4 w-20 mb-1" />
                <Skeleton className="h-5 w-16" />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (remittances.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg font-semibold">Envíos recientes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <div className="h-12 w-12 rounded-full bg-muted mx-auto mb-3 flex items-center justify-center">
              <Clock className="h-6 w-6 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground mb-4">
              No tienes envíos recientes
            </p>
            <Link href="/remittances/new">
              <Button>Hacer mi primer envío</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg font-semibold">Envíos recientes</CardTitle>
        <Link href="/remittances">
          <Button variant="ghost" size="sm" className="text-primary">
            Ver todos
            <ArrowRight className="h-4 w-4 ml-1" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        <div className="divide-y">
          {remittances.slice(0, 5).map((remittance) => (
            <RemittanceItem key={remittance.id} remittance={remittance} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
