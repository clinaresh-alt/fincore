"use client";

import { useState, useEffect } from "react";
import { auditAPI } from "@/lib/api-client";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Shield,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Clock,
  Activity,
  FileCode,
  Bell,
  AlertOctagon,
  RefreshCw,
  Eye,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { SecurityDashboard, AuditIncident, AuditAlert } from "@/types";

// Severity badge colors
const severityColors: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-blue-100 text-blue-800 border-blue-200",
  info: "bg-gray-100 text-gray-800 border-gray-200",
  sev1: "bg-red-100 text-red-800 border-red-200",
  sev2: "bg-orange-100 text-orange-800 border-orange-200",
  sev3: "bg-yellow-100 text-yellow-800 border-yellow-200",
  sev4: "bg-blue-100 text-blue-800 border-blue-200",
};

const statusColors: Record<string, string> = {
  detected: "bg-red-100 text-red-800",
  investigating: "bg-yellow-100 text-yellow-800",
  contained: "bg-blue-100 text-blue-800",
  eradicating: "bg-purple-100 text-purple-800",
  recovering: "bg-indigo-100 text-indigo-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-gray-100 text-gray-800",
};

export default function AuditPage() {
  const [dashboard, setDashboard] = useState<SecurityDashboard | null>(null);
  const [incidents, setIncidents] = useState<AuditIncident[]>([]);
  const [alerts, setAlerts] = useState<AuditAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialog states
  const [showIncidentDialog, setShowIncidentDialog] = useState(false);
  const [showAuditDialog, setShowAuditDialog] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form states
  const [newIncident, setNewIncident] = useState({
    title: "",
    description: "",
    severity: "sev3" as "sev1" | "sev2" | "sev3" | "sev4",
    affected_contracts: [] as string[],
  });
  const [contractPath, setContractPath] = useState("");

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError(null);
      const [dashboardData, incidentsData, alertsData] = await Promise.all([
        auditAPI.getDashboard(),
        auditAPI.listIncidents(true),
        auditAPI.getAlerts({ limit: 20 }),
      ]);
      setDashboard(dashboardData);
      setIncidents(incidentsData);
      setAlerts(alertsData);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al cargar dashboard de seguridad");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  const handleCreateIncident = async () => {
    if (!newIncident.title || !newIncident.description) return;

    try {
      setSubmitting(true);
      await auditAPI.createIncident(newIncident);
      setShowIncidentDialog(false);
      setNewIncident({
        title: "",
        description: "",
        severity: "sev3",
        affected_contracts: [],
      });
      loadDashboard();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al crear incidente");
    } finally {
      setSubmitting(false);
    }
  };

  const handleContainIncident = async (incidentId: string) => {
    try {
      await auditAPI.containIncident(incidentId);
      loadDashboard();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al contener incidente");
    }
  };

  const handleResolveIncident = async (incidentId: string) => {
    try {
      await auditAPI.resolveIncident(incidentId);
      loadDashboard();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al resolver incidente");
    }
  };

  const handleAcknowledgeAlert = async (alertId: string) => {
    try {
      await auditAPI.acknowledgeAlert(alertId);
      loadDashboard();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al reconocer alerta");
    }
  };

  const handleAuditContract = async () => {
    if (!contractPath) return;

    try {
      setSubmitting(true);
      await auditAPI.auditContract({ contract_path: contractPath, generate_html: true });
      setShowAuditDialog(false);
      setContractPath("");
      // Could show results in a new modal or redirect
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al auditar contrato");
    } finally {
      setSubmitting(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString("es-MX", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <PageHeader
        title="Auditoria de Smart Contracts"
        description="Monitoreo de seguridad, alertas e incidentes"
        backHref="/dashboard"
        actions={
          <div className="flex gap-2">
            <Dialog open={showAuditDialog} onOpenChange={setShowAuditDialog}>
              <DialogTrigger asChild>
                <Button variant="outline">
                  <FileCode className="h-4 w-4 mr-2" />
                  Auditar Contrato
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Auditar Smart Contract</DialogTitle>
                  <DialogDescription>
                    Ejecutar analisis de seguridad con Slither
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="contract_path">Ruta del Contrato</Label>
                    <Input
                      id="contract_path"
                      placeholder="contracts/MyToken.sol"
                      value={contractPath}
                      onChange={(e) => setContractPath(e.target.value)}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowAuditDialog(false)}>
                    Cancelar
                  </Button>
                  <Button onClick={handleAuditContract} disabled={submitting || !contractPath}>
                    {submitting ? "Analizando..." : "Iniciar Auditoria"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Dialog open={showIncidentDialog} onOpenChange={setShowIncidentDialog}>
              <DialogTrigger asChild>
                <Button>
                  <AlertOctagon className="h-4 w-4 mr-2" />
                  Reportar Incidente
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Reportar Incidente de Seguridad</DialogTitle>
                  <DialogDescription>
                    Los incidentes SEV1 activaran automaticamente el circuit breaker
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="title">Titulo</Label>
                    <Input
                      id="title"
                      placeholder="Ej: Transaccion sospechosa detectada"
                      value={newIncident.title}
                      onChange={(e) => setNewIncident({ ...newIncident, title: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="description">Descripcion</Label>
                    <Input
                      id="description"
                      placeholder="Descripcion detallada del incidente"
                      value={newIncident.description}
                      onChange={(e) => setNewIncident({ ...newIncident, description: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="severity">Severidad</Label>
                    <Select
                      value={newIncident.severity}
                      onValueChange={(value: "sev1" | "sev2" | "sev3" | "sev4") =>
                        setNewIncident({ ...newIncident, severity: value })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="sev1">SEV1 - Critico (Circuit Breaker)</SelectItem>
                        <SelectItem value="sev2">SEV2 - Alto</SelectItem>
                        <SelectItem value="sev3">SEV3 - Medio</SelectItem>
                        <SelectItem value="sev4">SEV4 - Bajo</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowIncidentDialog(false)}>
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleCreateIncident}
                    disabled={submitting || !newIncident.title || !newIncident.description}
                  >
                    {submitting ? "Creando..." : "Crear Incidente"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
          <XCircle className="h-5 w-5" />
          {error}
          <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setError(null)}>
            Cerrar
          </Button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Alertas
            </CardTitle>
            <Bell className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard?.alert_statistics.total_alerts || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {dashboard?.alert_statistics.unacknowledged_count || 0} sin reconocer
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Incidentes Activos
            </CardTitle>
            <AlertOctagon className="h-5 w-5 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard?.incident_statistics.active_incidents || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {dashboard?.incident_statistics.total_incidents || 0} totales
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              MTTR
            </CardTitle>
            <Clock className="h-5 w-5 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard?.incident_statistics.mttr_hours?.toFixed(1) || "N/A"}h
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Tiempo medio de resolucion
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Resueltos
            </CardTitle>
            <CheckCircle className="h-5 w-5 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard?.incident_statistics.resolved_incidents || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Incidentes cerrados
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs for different views */}
      <Tabs defaultValue="incidents" className="space-y-6">
        <TabsList>
          <TabsTrigger value="incidents" className="flex items-center gap-2">
            <AlertOctagon className="h-4 w-4" />
            Incidentes
          </TabsTrigger>
          <TabsTrigger value="alerts" className="flex items-center gap-2">
            <Bell className="h-4 w-4" />
            Alertas
          </TabsTrigger>
          <TabsTrigger value="statistics" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Estadisticas
          </TabsTrigger>
        </TabsList>

        {/* Incidents Tab */}
        <TabsContent value="incidents">
          <Card>
            <CardHeader>
              <CardTitle>Incidentes Activos</CardTitle>
            </CardHeader>
            <CardContent>
              {incidents.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Shield className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No hay incidentes activos</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {incidents.map((incident) => (
                    <div
                      key={incident.id}
                      className="border rounded-lg p-4 hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span
                              className={cn(
                                "px-2 py-1 text-xs font-medium rounded border",
                                severityColors[incident.severity]
                              )}
                            >
                              {incident.severity.toUpperCase()}
                            </span>
                            <span
                              className={cn(
                                "px-2 py-1 text-xs font-medium rounded",
                                statusColors[incident.status]
                              )}
                            >
                              {incident.status}
                            </span>
                          </div>
                          <h3 className="font-semibold">{incident.title}</h3>
                          <p className="text-sm text-muted-foreground mt-1">
                            {incident.description}
                          </p>
                          <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                            <span>Detectado: {formatDate(incident.detected_at)}</span>
                            <span>{incident.actions_count} acciones tomadas</span>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          {incident.status === "detected" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleContainIncident(incident.id)}
                            >
                              Contener
                            </Button>
                          )}
                          {incident.status === "contained" && (
                            <Button
                              size="sm"
                              variant="default"
                              onClick={() => handleResolveIncident(incident.id)}
                            >
                              Resolver
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Alerts Tab */}
        <TabsContent value="alerts">
          <Card>
            <CardHeader>
              <CardTitle>Alertas Recientes</CardTitle>
            </CardHeader>
            <CardContent>
              {alerts.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No hay alertas recientes</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className="flex items-center justify-between border rounded-lg p-3 hover:bg-muted/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {alert.severity === "critical" ? (
                          <AlertOctagon className="h-5 w-5 text-red-500" />
                        ) : alert.severity === "high" ? (
                          <AlertTriangle className="h-5 w-5 text-orange-500" />
                        ) : (
                          <AlertCircle className="h-5 w-5 text-yellow-500" />
                        )}
                        <div>
                          <div className="flex items-center gap-2">
                            <span
                              className={cn(
                                "px-2 py-0.5 text-xs font-medium rounded border",
                                severityColors[alert.severity]
                              )}
                            >
                              {alert.severity}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {alert.type}
                            </span>
                          </div>
                          <p className="font-medium mt-1">{alert.title}</p>
                          <p className="text-sm text-muted-foreground">
                            {alert.description}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          {formatDate(alert.timestamp)}
                        </span>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleAcknowledgeAlert(alert.id)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Statistics Tab */}
        <TabsContent value="statistics">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Alertas por Severidad</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(dashboard?.alert_statistics.by_severity || {}).map(
                    ([severity, count]) => (
                      <div key={severity} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              "px-2 py-1 text-xs font-medium rounded border w-20 text-center",
                              severityColors[severity]
                            )}
                          >
                            {severity}
                          </span>
                        </div>
                        <span className="font-semibold">{count}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Incidentes por Severidad</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(dashboard?.incident_statistics.by_severity || {}).map(
                    ([severity, count]) => (
                      <div key={severity} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              "px-2 py-1 text-xs font-medium rounded border w-20 text-center",
                              severityColors[severity]
                            )}
                          >
                            {severity.toUpperCase()}
                          </span>
                        </div>
                        <span className="font-semibold">{count}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Alertas por Tipo</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(dashboard?.alert_statistics.by_type || {}).map(
                    ([type, count]) => (
                      <div key={type} className="flex items-center justify-between">
                        <span className="text-sm">{type.replace(/_/g, " ")}</span>
                        <span className="font-semibold">{count}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Metricas de Respuesta</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                    <div>
                      <p className="text-sm text-muted-foreground">MTTR (Mean Time to Resolve)</p>
                      <p className="text-2xl font-bold">
                        {dashboard?.incident_statistics.mttr_hours?.toFixed(1) || "N/A"}h
                      </p>
                    </div>
                    <Clock className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                    <div>
                      <p className="text-sm text-muted-foreground">MTTD (Mean Time to Detect)</p>
                      <p className="text-2xl font-bold">
                        {dashboard?.incident_statistics.mttd_minutes?.toFixed(0) || "N/A"} min
                      </p>
                    </div>
                    <Activity className="h-8 w-8 text-muted-foreground" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
