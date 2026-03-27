"use client";

import { useState } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  XCircle,
  Clock,
  CheckCircle2,
  Bell,
  BellOff,
  User,
  MessageSquare,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { MonitoringAlert, MonitoringAlertSeverity, MonitoringAlertStatus } from "@/types";

interface AlertCardProps {
  alert: MonitoringAlert;
  onAcknowledge?: (alertId: string, comment?: string) => Promise<void>;
  onResolve?: (alertId: string) => Promise<void>;
  onSilence?: (alertId: string, durationMinutes: number, reason?: string) => Promise<void>;
}

const SEVERITY_CONFIG: Record<
  MonitoringAlertSeverity,
  { icon: typeof AlertTriangle; color: string; bg: string; border: string }
> = {
  critical: {
    icon: XCircle,
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
  },
  error: {
    icon: AlertCircle,
    color: "text-orange-700",
    bg: "bg-orange-50",
    border: "border-orange-200",
  },
  warning: {
    icon: AlertTriangle,
    color: "text-yellow-700",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
  },
  info: {
    icon: Info,
    color: "text-blue-700",
    bg: "bg-blue-50",
    border: "border-blue-200",
  },
};

const STATUS_CONFIG: Record<MonitoringAlertStatus, { label: string; color: string }> = {
  active: { label: "Activa", color: "bg-red-100 text-red-800" },
  acknowledged: { label: "Reconocida", color: "bg-yellow-100 text-yellow-800" },
  resolved: { label: "Resuelta", color: "bg-green-100 text-green-800" },
  silenced: { label: "Silenciada", color: "bg-gray-100 text-gray-800" },
};

const TYPE_LABELS: Record<string, string> = {
  "service.down": "Servicio Caido",
  "service.degraded": "Servicio Degradado",
  "service.latency": "Latencia Alta",
  "remittance.failed": "Remesa Fallida",
  "remittance.stuck": "Remesa Estancada",
  "remittance.volume": "Volumen Anormal",
  "financial.balance_low": "Balance Bajo",
  "financial.rate_spike": "Variacion de Tasa",
  "queue.backlog": "Cola Saturada",
  "queue.failed_jobs": "Jobs Fallidos",
  "system.cpu": "CPU Alto",
  "system.memory": "Memoria Alta",
  "system.disk": "Disco Lleno",
  "compliance.alert": "Alerta Compliance",
};

export function AlertCard({ alert, onAcknowledge, onResolve, onSilence }: AlertCardProps) {
  const [isAcknowledging, setIsAcknowledging] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  const [isSilencing, setIsSilencing] = useState(false);
  const [comment, setComment] = useState("");
  const [silenceDuration, setSilenceDuration] = useState(60);
  const [silenceReason, setSilenceReason] = useState("");
  const [showAckDialog, setShowAckDialog] = useState(false);
  const [showSilenceDialog, setShowSilenceDialog] = useState(false);

  const severityConfig = SEVERITY_CONFIG[alert.severity];
  const statusConfig = STATUS_CONFIG[alert.status];
  const SeverityIcon = severityConfig.icon;

  const handleAcknowledge = async () => {
    if (!onAcknowledge) return;
    setIsAcknowledging(true);
    try {
      await onAcknowledge(alert.id, comment || undefined);
      setShowAckDialog(false);
      setComment("");
    } finally {
      setIsAcknowledging(false);
    }
  };

  const handleResolve = async () => {
    if (!onResolve) return;
    setIsResolving(true);
    try {
      await onResolve(alert.id);
    } finally {
      setIsResolving(false);
    }
  };

  const handleSilence = async () => {
    if (!onSilence) return;
    setIsSilencing(true);
    try {
      await onSilence(alert.id, silenceDuration, silenceReason || undefined);
      setShowSilenceDialog(false);
      setSilenceReason("");
    } finally {
      setIsSilencing(false);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("es-MX", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getTimeSince = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `hace ${diffDays}d`;
    if (diffHours > 0) return `hace ${diffHours}h`;
    if (diffMins > 0) return `hace ${diffMins}m`;
    return "ahora";
  };

  return (
    <Card className={cn("transition-all hover:shadow-md", severityConfig.border, severityConfig.bg)}>
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          {/* Severity Icon */}
          <div className={cn("p-2 rounded-lg", severityConfig.bg)}>
            <SeverityIcon className={cn("h-5 w-5", severityConfig.color)} />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className={statusConfig.color}>
                    {statusConfig.label}
                  </Badge>
                  <Badge variant="outline" className="capitalize">
                    {alert.severity}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {TYPE_LABELS[alert.type] || alert.type}
                  </span>
                </div>
                <h3 className="font-semibold text-sm">{alert.title}</h3>
                <p className="text-sm text-muted-foreground mt-1">{alert.message}</p>
              </div>

              <div className="text-right text-xs text-muted-foreground whitespace-nowrap">
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {getTimeSince(alert.triggered_at)}
                </div>
                <div className="mt-1">{formatDate(alert.triggered_at)}</div>
              </div>
            </div>

            {/* Metadata */}
            {(alert.acknowledged_by || alert.acknowledged_at) && (
              <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                <User className="h-3 w-3" />
                <span>
                  Reconocida por {alert.acknowledged_by || "Sistema"}
                  {alert.acknowledged_at && ` - ${formatDate(alert.acknowledged_at)}`}
                </span>
              </div>
            )}

            {alert.resolved_at && (
              <div className="mt-1 flex items-center gap-2 text-xs text-green-600">
                <CheckCircle2 className="h-3 w-3" />
                <span>Resuelta {formatDate(alert.resolved_at)}</span>
              </div>
            )}

            {/* Actions */}
            {alert.status === "active" && (
              <div className="flex items-center gap-2 mt-3">
                {/* Acknowledge Dialog */}
                <Dialog open={showAckDialog} onOpenChange={setShowAckDialog}>
                  <DialogTrigger asChild>
                    <Button variant="outline" size="sm">
                      <CheckCircle2 className="h-4 w-4 mr-1" />
                      Reconocer
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Reconocer Alerta</DialogTitle>
                      <DialogDescription>
                        Al reconocer esta alerta, indicas que estas al tanto del problema y trabajando en
                        el.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="comment">Comentario (opcional)</Label>
                        <Textarea
                          id="comment"
                          placeholder="Describe las acciones que estas tomando..."
                          value={comment}
                          onChange={(e) => setComment(e.target.value)}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowAckDialog(false)}>
                        Cancelar
                      </Button>
                      <Button onClick={handleAcknowledge} disabled={isAcknowledging}>
                        {isAcknowledging ? "Reconociendo..." : "Reconocer"}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>

                {/* Silence Dialog */}
                <Dialog open={showSilenceDialog} onOpenChange={setShowSilenceDialog}>
                  <DialogTrigger asChild>
                    <Button variant="outline" size="sm">
                      <BellOff className="h-4 w-4 mr-1" />
                      Silenciar
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Silenciar Alerta</DialogTitle>
                      <DialogDescription>
                        La alerta no generara notificaciones durante el tiempo especificado.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="duration">Duracion (minutos)</Label>
                        <Input
                          id="duration"
                          type="number"
                          min={5}
                          max={1440}
                          value={silenceDuration}
                          onChange={(e) => setSilenceDuration(parseInt(e.target.value) || 60)}
                        />
                        <p className="text-xs text-muted-foreground">
                          Minimo 5 minutos, maximo 24 horas (1440 minutos)
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="reason">Razon (opcional)</Label>
                        <Textarea
                          id="reason"
                          placeholder="Explica por que silencias esta alerta..."
                          value={silenceReason}
                          onChange={(e) => setSilenceReason(e.target.value)}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowSilenceDialog(false)}>
                        Cancelar
                      </Button>
                      <Button onClick={handleSilence} disabled={isSilencing}>
                        {isSilencing ? "Silenciando..." : "Silenciar"}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            )}

            {alert.status === "acknowledged" && (
              <div className="flex items-center gap-2 mt-3">
                <Button variant="default" size="sm" onClick={handleResolve} disabled={isResolving}>
                  <CheckCircle2 className="h-4 w-4 mr-1" />
                  {isResolving ? "Resolviendo..." : "Marcar Resuelta"}
                </Button>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
