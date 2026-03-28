"use client";

import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Copy,
  Clock,
  User,
  Building2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  ExternalLink,
  Ban,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useRemittance, useCancelRemittance } from "@/features/remittances/hooks/use-remittances";
import type { RemittanceStatus } from "@/types";

interface RemittanceDetailPageProps {
  params: Promise<{ id: string }>;
}

// Configuración de estados
const statusConfig: Record<
  RemittanceStatus,
  { label: string; color: string; icon: React.ComponentType<{ className?: string }> }
> = {
  initiated: { label: "Iniciada", color: "bg-blue-100 text-blue-800", icon: Clock },
  pending_deposit: { label: "Esperando depósito", color: "bg-yellow-100 text-yellow-800", icon: Clock },
  deposited: { label: "Depósito recibido", color: "bg-blue-100 text-blue-800", icon: CheckCircle2 },
  locked: { label: "Fondos bloqueados", color: "bg-purple-100 text-purple-800", icon: CheckCircle2 },
  processing: { label: "Procesando", color: "bg-blue-100 text-blue-800", icon: Loader2 },
  disbursed: { label: "Entregado", color: "bg-green-100 text-green-800", icon: CheckCircle2 },
  completed: { label: "Completada", color: "bg-green-100 text-green-800", icon: CheckCircle2 },
  refund_pending: { label: "Reembolso pendiente", color: "bg-orange-100 text-orange-800", icon: AlertCircle },
  refunded: { label: "Reembolsada", color: "bg-gray-100 text-gray-800", icon: RefreshCw },
  failed: { label: "Fallida", color: "bg-red-100 text-red-800", icon: XCircle },
  cancelled: { label: "Cancelada", color: "bg-gray-100 text-gray-800", icon: Ban },
  expired: { label: "Expirada", color: "bg-gray-100 text-gray-800", icon: XCircle },
};

// Estados que permiten cancelación
const cancellableStatuses: RemittanceStatus[] = ["initiated", "pending_deposit"];

export default function RemittanceDetailPage({ params }: RemittanceDetailPageProps) {
  const { id } = use(params);
  const router = useRouter();
  const { data: remittance, isLoading, error, refetch } = useRemittance(id);
  const cancelMutation = useCancelRemittance();

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copiado`);
  };

  const handleCancel = async () => {
    if (!remittance) return;

    const confirmed = window.confirm(
      "¿Estás seguro de cancelar esta remesa? Esta acción no se puede deshacer."
    );

    if (!confirmed) return;

    try {
      await cancelMutation.mutateAsync(remittance.id);
      toast.success("Remesa cancelada");
      refetch();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error al cancelar";
      toast.error(message);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  // Error state
  if (error || !remittance) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card className="border-destructive">
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <XCircle className="h-12 w-12 text-destructive" />
            <div className="text-center">
              <h2 className="text-lg font-semibold">Remesa no encontrada</h2>
              <p className="text-sm text-muted-foreground">
                {error instanceof Error ? error.message : "No se pudo cargar la remesa"}
              </p>
            </div>
            <Button variant="outline" onClick={() => router.push("/")}>
              Volver al inicio
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const status = statusConfig[remittance.status];
  const StatusIcon = status.icon;
  const canCancel = cancellableStatuses.includes(remittance.status);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold">Remesa</h1>
              <button
                onClick={() => copyToClipboard(remittance.reference_code, "Referencia")}
                className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
              >
                #{remittance.reference_code}
                <Copy className="h-3 w-3" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground">
              {formatDate(remittance.created_at)}
            </p>
          </div>
        </div>

        <Badge className={status.color}>
          <StatusIcon className="h-3 w-3 mr-1" />
          {status.label}
        </Badge>
      </div>

      {/* Amount Card */}
      <Card>
        <CardContent className="py-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Enviaste</p>
              <p className="text-2xl font-bold">
                {formatCurrency(
                  remittance.amount_fiat_source + remittance.total_fees,
                  remittance.currency_source
                )}
              </p>
            </div>
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <span className="text-primary font-bold">→</span>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">Recibe</p>
              <p className="text-2xl font-bold text-primary">
                {formatCurrency(remittance.amount_fiat_destination, remittance.currency_destination)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Status Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Estado de la remesa</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Timeline items based on status */}
            <TimelineItem
              completed={true}
              label="Remesa creada"
              date={remittance.created_at}
            />
            <TimelineItem
              completed={["deposited", "locked", "processing", "disbursed", "completed"].includes(remittance.status)}
              active={remittance.status === "pending_deposit"}
              label="Depósito recibido"
              date={remittance.status !== "initiated" && remittance.status !== "pending_deposit" ? remittance.updated_at : undefined}
            />
            <TimelineItem
              completed={["locked", "processing", "disbursed", "completed"].includes(remittance.status)}
              active={remittance.status === "deposited"}
              label="Fondos asegurados"
              date={remittance.escrow_locked_at}
            />
            <TimelineItem
              completed={["disbursed", "completed"].includes(remittance.status)}
              active={remittance.status === "processing"}
              label="En proceso de entrega"
            />
            <TimelineItem
              completed={remittance.status === "completed"}
              active={remittance.status === "disbursed"}
              label="Completada"
              date={remittance.completed_at}
              isLast
            />
          </div>
        </CardContent>
      </Card>

      {/* Beneficiary Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Beneficiario</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <User className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="font-medium">{remittance.recipient_info.name}</p>
              {remittance.recipient_info.email && (
                <p className="text-sm text-muted-foreground">
                  {remittance.recipient_info.email}
                </p>
              )}
            </div>
          </div>

          <Separator />

          <div className="space-y-2 text-sm">
            {remittance.recipient_info.bank_name && (
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <span>{remittance.recipient_info.bank_name}</span>
              </div>
            )}
            {remittance.recipient_info.clabe && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">CLABE</span>
                <button
                  onClick={() => copyToClipboard(remittance.recipient_info.clabe!, "CLABE")}
                  className="flex items-center gap-1 font-mono hover:text-primary"
                >
                  ****{remittance.recipient_info.clabe.slice(-4)}
                  <Copy className="h-3 w-3" />
                </button>
              </div>
            )}
            {remittance.recipient_info.country && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">País</span>
                <span>{remittance.recipient_info.country}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Transaction Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Detalles de la transacción</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Monto enviado</span>
            <span className="font-medium">
              {formatCurrency(remittance.amount_fiat_source, remittance.currency_source)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Comisión plataforma</span>
            <span className="font-medium">
              {formatCurrency(remittance.platform_fee, remittance.currency_source)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Fee de red</span>
            <span className="font-medium">
              {formatCurrency(remittance.network_fee, remittance.currency_source)}
            </span>
          </div>
          <Separator />
          <div className="flex justify-between">
            <span className="text-muted-foreground">Total cobrado</span>
            <span className="font-bold">
              {formatCurrency(
                remittance.amount_fiat_source + remittance.total_fees,
                remittance.currency_source
              )}
            </span>
          </div>
          <Separator />
          <div className="flex justify-between">
            <span className="text-muted-foreground">Tasa de cambio</span>
            <span className="font-medium">
              1 {remittance.currency_source} = {remittance.exchange_rate_source_usd?.toFixed(4)}{" "}
              {remittance.currency_destination}
            </span>
          </div>
          {remittance.amount_stablecoin && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Stablecoin</span>
              <span className="font-mono">
                {remittance.amount_stablecoin} {remittance.stablecoin}
              </span>
            </div>
          )}
          {remittance.blockchain_tx_hash && (
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">TX Blockchain</span>
              <a
                href={`https://polygonscan.com/tx/${remittance.blockchain_tx_hash}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-primary hover:underline font-mono text-xs"
              >
                {remittance.blockchain_tx_hash.slice(0, 8)}...
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="outline" className="flex-1" onClick={() => router.push("/")}>
          Volver al inicio
        </Button>
        {canCancel && (
          <Button
            variant="destructive"
            className="flex-1"
            onClick={handleCancel}
            disabled={cancelMutation.isPending}
          >
            {cancelMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Ban className="h-4 w-4 mr-2" />
            )}
            Cancelar remesa
          </Button>
        )}
      </div>
    </div>
  );
}

// Timeline Item Component
function TimelineItem({
  completed,
  active,
  label,
  date,
  isLast,
}: {
  completed: boolean;
  active?: boolean;
  label: string;
  date?: string;
  isLast?: boolean;
}) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div
          className={`h-6 w-6 rounded-full flex items-center justify-center ${
            completed
              ? "bg-green-500"
              : active
              ? "bg-primary animate-pulse"
              : "bg-muted"
          }`}
        >
          {completed ? (
            <CheckCircle2 className="h-4 w-4 text-white" />
          ) : active ? (
            <Loader2 className="h-3 w-3 text-primary-foreground animate-spin" />
          ) : (
            <div className="h-2 w-2 rounded-full bg-muted-foreground/50" />
          )}
        </div>
        {!isLast && (
          <div
            className={`w-0.5 h-8 ${
              completed ? "bg-green-500" : "bg-muted"
            }`}
          />
        )}
      </div>
      <div className="flex-1 pb-4">
        <p
          className={`font-medium ${
            completed || active ? "text-foreground" : "text-muted-foreground"
          }`}
        >
          {label}
        </p>
        {date && (
          <p className="text-xs text-muted-foreground">{formatDate(date)}</p>
        )}
      </div>
    </div>
  );
}
