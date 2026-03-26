"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Copy,
  CheckCircle2,
  Clock,
  XCircle,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Shield,
  Banknote,
  User,
  Building2,
  Hash,
  Calendar,
  Timer,
  Send,
  Lock,
  Unlock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { remittancesAPI } from "@/lib/api-client";
import { Remittance, RemittanceStatus, RemittanceBlockchainTx } from "@/types";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

const STATUS_CONFIG: Record<RemittanceStatus, { label: string; color: string; bgColor: string; icon: React.ElementType; description: string }> = {
  initiated: {
    label: "Iniciada",
    color: "text-slate-700",
    bgColor: "bg-slate-100",
    icon: Clock,
    description: "Remesa creada, esperando deposito"
  },
  pending_deposit: {
    label: "Pendiente Deposito",
    color: "text-yellow-700",
    bgColor: "bg-yellow-100",
    icon: Clock,
    description: "Esperando confirmacion del deposito"
  },
  deposited: {
    label: "Depositada",
    color: "text-blue-700",
    bgColor: "bg-blue-100",
    icon: Banknote,
    description: "Deposito confirmado, listo para escrow"
  },
  locked: {
    label: "En Escrow",
    color: "text-purple-700",
    bgColor: "bg-purple-100",
    icon: Lock,
    description: "Fondos bloqueados en contrato inteligente"
  },
  processing: {
    label: "Procesando",
    color: "text-indigo-700",
    bgColor: "bg-indigo-100",
    icon: RefreshCw,
    description: "Procesando desembolso al beneficiario"
  },
  disbursed: {
    label: "Desembolsada",
    color: "text-teal-700",
    bgColor: "bg-teal-100",
    icon: Send,
    description: "Fondos enviados al beneficiario"
  },
  completed: {
    label: "Completada",
    color: "text-green-700",
    bgColor: "bg-green-100",
    icon: CheckCircle2,
    description: "Transferencia completada exitosamente"
  },
  refund_pending: {
    label: "Reembolso Pendiente",
    color: "text-orange-700",
    bgColor: "bg-orange-100",
    icon: AlertCircle,
    description: "Escrow expirado, reembolso en proceso"
  },
  refunded: {
    label: "Reembolsada",
    color: "text-gray-700",
    bgColor: "bg-gray-100",
    icon: Unlock,
    description: "Fondos devueltos al remitente"
  },
  failed: {
    label: "Fallida",
    color: "text-red-700",
    bgColor: "bg-red-100",
    icon: XCircle,
    description: "Error en la transferencia"
  },
  cancelled: {
    label: "Cancelada",
    color: "text-gray-600",
    bgColor: "bg-gray-100",
    icon: XCircle,
    description: "Cancelada por el usuario"
  },
  expired: {
    label: "Expirada",
    color: "text-amber-700",
    bgColor: "bg-amber-100",
    icon: Timer,
    description: "Tiempo de escrow expirado"
  },
};

const TIMELINE_ORDER: RemittanceStatus[] = [
  "initiated",
  "pending_deposit",
  "deposited",
  "locked",
  "processing",
  "disbursed",
  "completed",
];

export default function RemittanceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuthStore();
  const [remittance, setRemittance] = useState<Remittance | null>(null);
  const [transactions, setTransactions] = useState<RemittanceBlockchainTx[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remittanceId = params.id as string;

  useEffect(() => {
    loadRemittance();
  }, [remittanceId]);

  const loadRemittance = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await remittancesAPI.get(remittanceId);
      setRemittance(data);

      // Try to load blockchain transactions
      try {
        const txs = await remittancesAPI.getTransactions(remittanceId);
        setTransactions(txs || []);
      } catch {
        // Transactions endpoint might not exist yet
        setTransactions([]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al cargar la remesa");
    } finally {
      setLoading(false);
    }
  };

  const handleLockFunds = async () => {
    setActionLoading(true);
    try {
      await remittancesAPI.lockFunds(remittanceId);
      await loadRemittance();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al bloquear fondos");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    setActionLoading(true);
    try {
      await remittancesAPI.cancel(remittanceId);
      await loadRemittance();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al cancelar");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRelease = async () => {
    setActionLoading(true);
    try {
      await remittancesAPI.releaseFunds(remittanceId);
      await loadRemittance();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al liberar fondos");
    } finally {
      setActionLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const getTimeRemaining = () => {
    if (!remittance?.escrow_expires_at) return null;
    const expires = new Date(remittance.escrow_expires_at);
    const now = new Date();
    const diff = expires.getTime() - now.getTime();
    if (diff <= 0) return "Expirado";
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${minutes}m`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !remittance) {
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error || "Remesa no encontrada"}
        </div>
        <Button asChild variant="outline">
          <Link href="/remittances">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver a Remesas
          </Link>
        </Button>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[remittance.status];
  const StatusIcon = statusConfig.icon;
  const currentStepIndex = TIMELINE_ORDER.indexOf(remittance.status);
  const isAdmin = user?.rol === "Admin" || user?.rol === "Analista";
  const canCancel = ["initiated", "pending_deposit", "deposited"].includes(remittance.status);
  const canLock = remittance.status === "deposited";
  const canRelease = remittance.status === "locked" && isAdmin;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/remittances">
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">Remesa</h1>
              <Badge className={`${statusConfig.bgColor} ${statusConfig.color} gap-1`}>
                <StatusIcon className="h-3 w-3" />
                {statusConfig.label}
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="font-mono">{remittance.reference_code}</span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => copyToClipboard(remittance.reference_code)}
              >
                <Copy className="h-3 w-3" />
              </Button>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadRemittance}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Transfer Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Resumen de Transferencia</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-primary/10 to-primary/5 rounded-lg">
                <div>
                  <div className="text-sm text-muted-foreground">Envia</div>
                  <div className="text-2xl font-bold">
                    {formatCurrency(Number(remittance.amount_fiat_source), remittance.currency_source)}
                  </div>
                </div>
                <ArrowRight className="h-6 w-6 text-muted-foreground" />
                <div className="text-right">
                  <div className="text-sm text-muted-foreground">Recibe</div>
                  <div className="text-2xl font-bold text-green-600">
                    {remittance.amount_fiat_destination
                      ? formatCurrency(Number(remittance.amount_fiat_destination), remittance.currency_destination)
                      : "-"}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Stablecoin</span>
                  <div className="font-medium flex items-center gap-1">
                    <Shield className="h-4 w-4 text-blue-500" />
                    {remittance.amount_stablecoin
                      ? `${Number(remittance.amount_stablecoin).toFixed(2)} ${remittance.stablecoin}`
                      : "-"}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground">Comisiones</span>
                  <div className="font-medium">
                    {formatCurrency(Number(remittance.total_fees || 0), remittance.currency_source)}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground">Tipo de Cambio</span>
                  <div className="font-medium">
                    {remittance.exchange_rate_usd_destination
                      ? `1 USD = ${Number(remittance.exchange_rate_usd_destination).toFixed(4)} ${remittance.currency_destination}`
                      : "-"}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground">Metodo Desembolso</span>
                  <div className="font-medium capitalize">
                    {remittance.disbursement_method?.replace("_", " ") || "-"}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Status Timeline */}
          <Card>
            <CardHeader>
              <CardTitle>Estado de la Transferencia</CardTitle>
              <CardDescription>{statusConfig.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="relative">
                {TIMELINE_ORDER.map((status, index) => {
                  const config = STATUS_CONFIG[status];
                  const Icon = config.icon;
                  const isCompleted = index < currentStepIndex;
                  const isCurrent = index === currentStepIndex;
                  const isFuture = index > currentStepIndex;

                  // Don't show future steps if cancelled/failed/refunded
                  if (isFuture && !TIMELINE_ORDER.includes(remittance.status)) {
                    return null;
                  }

                  return (
                    <div key={status} className="flex gap-4 pb-6 last:pb-0">
                      <div className="flex flex-col items-center">
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center ${
                            isCompleted
                              ? "bg-green-500 text-white"
                              : isCurrent
                              ? `${config.bgColor} ${config.color}`
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {isCompleted ? (
                            <CheckCircle2 className="h-4 w-4" />
                          ) : (
                            <Icon className="h-4 w-4" />
                          )}
                        </div>
                        {index < TIMELINE_ORDER.length - 1 && (
                          <div
                            className={`w-0.5 flex-1 mt-2 ${
                              isCompleted ? "bg-green-500" : "bg-muted"
                            }`}
                          />
                        )}
                      </div>
                      <div className="flex-1 pb-2">
                        <div className={`font-medium ${isFuture ? "text-muted-foreground" : ""}`}>
                          {config.label}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {config.description}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Escrow Timer */}
              {remittance.status === "locked" && remittance.escrow_expires_at && (
                <div className="mt-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Timer className="h-5 w-5 text-purple-600" />
                      <span className="font-medium text-purple-700">Tiempo restante en escrow</span>
                    </div>
                    <Badge className="bg-purple-100 text-purple-700">
                      {getTimeRemaining()}
                    </Badge>
                  </div>
                  <p className="text-sm text-purple-600 mt-2">
                    Si no se completa el desembolso, los fondos seran reembolsados automaticamente.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Blockchain Transactions */}
          {transactions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Transacciones Blockchain</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {transactions.map((tx) => (
                    <div
                      key={tx.id}
                      className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <Hash className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <div className="font-medium capitalize">{tx.operation}</div>
                          {tx.tx_hash && (
                            <div className="text-xs font-mono text-muted-foreground">
                              {tx.tx_hash.slice(0, 10)}...{tx.tx_hash.slice(-8)}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={tx.blockchain_status === "confirmed" ? "default" : "secondary"}
                        >
                          {tx.blockchain_status}
                        </Badge>
                        {tx.tx_hash && (
                          <Button variant="ghost" size="icon" className="h-8 w-8" asChild>
                            <a
                              href={`https://polygonscan.com/tx/${tx.tx_hash}`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Recipient Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-4 w-4" />
                Beneficiario
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <span className="text-muted-foreground">Nombre</span>
                <div className="font-medium">{remittance.recipient_info?.full_name || "-"}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Pais</span>
                <div className="font-medium">{remittance.recipient_info?.country || "-"}</div>
              </div>
              {remittance.recipient_info?.email && (
                <div>
                  <span className="text-muted-foreground">Email</span>
                  <div className="font-medium">{remittance.recipient_info.email}</div>
                </div>
              )}
              {remittance.recipient_info?.phone && (
                <div>
                  <span className="text-muted-foreground">Telefono</span>
                  <div className="font-medium">{remittance.recipient_info.phone}</div>
                </div>
              )}
              {remittance.recipient_info?.bank_name && (
                <div>
                  <span className="text-muted-foreground">Banco</span>
                  <div className="font-medium">{remittance.recipient_info.bank_name}</div>
                </div>
              )}
              {remittance.recipient_info?.clabe && (
                <div>
                  <span className="text-muted-foreground">CLABE</span>
                  <div className="font-mono text-xs">{remittance.recipient_info.clabe}</div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Dates */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Fechas
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div>
                <span className="text-muted-foreground">Creada</span>
                <div className="font-medium">{formatDate(remittance.created_at)}</div>
              </div>
              {remittance.escrow_locked_at && (
                <div>
                  <span className="text-muted-foreground">Escrow bloqueado</span>
                  <div className="font-medium">{formatDate(remittance.escrow_locked_at)}</div>
                </div>
              )}
              {remittance.completed_at && (
                <div>
                  <span className="text-muted-foreground">Completada</span>
                  <div className="font-medium text-green-600">{formatDate(remittance.completed_at)}</div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Actions */}
          {(canCancel || canLock || canRelease) && (
            <Card>
              <CardHeader>
                <CardTitle>Acciones</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {canLock && (
                  <Button
                    onClick={handleLockFunds}
                    disabled={actionLoading}
                    className="w-full"
                  >
                    {actionLoading ? (
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Lock className="h-4 w-4 mr-2" />
                    )}
                    Bloquear en Escrow
                  </Button>
                )}

                {canRelease && (
                  <Button
                    onClick={handleRelease}
                    disabled={actionLoading}
                    className="w-full"
                    variant="default"
                  >
                    {actionLoading ? (
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Unlock className="h-4 w-4 mr-2" />
                    )}
                    Liberar Fondos
                  </Button>
                )}

                {canCancel && (
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="destructive" className="w-full" disabled={actionLoading}>
                        <XCircle className="h-4 w-4 mr-2" />
                        Cancelar Remesa
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Cancelar Remesa</AlertDialogTitle>
                        <AlertDialogDescription>
                          Esta seguro que desea cancelar esta remesa? Esta accion no se puede deshacer.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>No, volver</AlertDialogCancel>
                        <AlertDialogAction onClick={handleCancel}>
                          Si, cancelar
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                )}
              </CardContent>
            </Card>
          )}

          {/* Notes */}
          {remittance.notes && (
            <Card>
              <CardHeader>
                <CardTitle>Notas</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{remittance.notes}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
