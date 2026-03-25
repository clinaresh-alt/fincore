"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Shield,
  AlertTriangle,
  FileText,
  Users,
  CheckCircle,
  XCircle,
  Clock,
  Eye,
  Search,
  Download,
  Upload,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  Activity,
} from "lucide-react";
import { complianceAPI } from "@/lib/api-client";
import { useToast } from "@/hooks/use-toast";

interface DashboardData {
  kyc_statistics: {
    total_profiles: number;
    by_level: Record<string, number>;
    by_status: Record<string, number>;
    pending_verification: number;
    high_risk_users: number;
    pep_count: number;
    avg_risk_score: number;
  };
  aml_statistics: {
    total_alerts: number;
    open_alerts: number;
    by_severity: Record<string, number>;
    by_type: Record<string, number>;
    alerts_this_month: number;
    escalation_rate: number;
  };
  reporting_statistics: {
    total_reports: number;
    by_type: Record<string, number>;
    by_status: Record<string, number>;
    total_amount_reported_mxn: number;
    year: number;
  };
}

interface AMLAlert {
  id: string;
  alert_type: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  amount: number | null;
  currency: string;
  detected_at: string;
  user_id: string;
  rule_name: string | null;
}

interface Report {
  id: string;
  report_type: string;
  reference_number: string;
  period_start: string;
  period_end: string;
  status: string;
  transactions_count: number;
  total_amount: number | null;
  created_at: string;
}

const severityColors: Record<string, string> = {
  low: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

const statusColors: Record<string, string> = {
  open: "bg-blue-100 text-blue-800",
  investigating: "bg-purple-100 text-purple-800",
  escalated: "bg-orange-100 text-orange-800",
  reported: "bg-green-100 text-green-800",
  closed_false_positive: "bg-gray-100 text-gray-800",
  closed_confirmed: "bg-red-100 text-red-800",
};

const reportStatusColors: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  ready: "bg-blue-100 text-blue-800",
  approved: "bg-purple-100 text-purple-800",
  submitted: "bg-green-100 text-green-800",
  accepted: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
};

export default function CompliancePage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [alerts, setAlerts] = useState<AMLAlert[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAlert, setSelectedAlert] = useState<AMLAlert | null>(null);
  const [investigationNotes, setInvestigationNotes] = useState("");
  const [closeNotes, setCloseNotes] = useState("");
  const [isFalsePositive, setIsFalsePositive] = useState(false);
  const [rovPeriod, setRovPeriod] = useState({ start: "", end: "" });
  const { toast } = useToast();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [dashboardData, alertsData, reportsData] = await Promise.all([
        complianceAPI.getDashboard(),
        complianceAPI.listAlerts({ limit: 50 }),
        complianceAPI.listReports(),
      ]);
      setDashboard(dashboardData);
      setAlerts(alertsData);
      setReports(reportsData);
    } catch (error) {
      console.error("Error loading compliance data:", error);
      toast({
        title: "Error",
        description: "No se pudo cargar la informacion de compliance",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleInvestigate = async (alertId: string) => {
    try {
      await complianceAPI.investigateAlert(alertId, investigationNotes);
      toast({
        title: "Investigacion iniciada",
        description: "La alerta ha sido marcada para investigacion",
      });
      setInvestigationNotes("");
      setSelectedAlert(null);
      loadData();
    } catch (error) {
      toast({
        title: "Error",
        description: "No se pudo iniciar la investigacion",
        variant: "destructive",
      });
    }
  };

  const handleEscalate = async (alertId: string) => {
    try {
      await complianceAPI.escalateAlert(alertId);
      toast({
        title: "Alerta escalada",
        description: "La alerta ha sido escalada al nivel superior",
      });
      loadData();
    } catch (error) {
      toast({
        title: "Error",
        description: "No se pudo escalar la alerta",
        variant: "destructive",
      });
    }
  };

  const handleCloseAlert = async (alertId: string) => {
    try {
      await complianceAPI.closeAlert(alertId, {
        false_positive: isFalsePositive,
        notes: closeNotes,
      });
      toast({
        title: "Alerta cerrada",
        description: "La alerta ha sido cerrada correctamente",
      });
      setCloseNotes("");
      setIsFalsePositive(false);
      setSelectedAlert(null);
      loadData();
    } catch (error) {
      toast({
        title: "Error",
        description: "No se pudo cerrar la alerta",
        variant: "destructive",
      });
    }
  };

  const handleGenerateROV = async () => {
    if (!rovPeriod.start || !rovPeriod.end) {
      toast({
        title: "Error",
        description: "Seleccione el periodo del reporte",
        variant: "destructive",
      });
      return;
    }
    try {
      await complianceAPI.generateROV(rovPeriod.start, rovPeriod.end);
      toast({
        title: "Reporte generado",
        description: "El ROV ha sido generado correctamente",
      });
      loadData();
    } catch (error) {
      toast({
        title: "Error",
        description: "No se pudo generar el reporte",
        variant: "destructive",
      });
    }
  };

  const handleApproveReport = async (reportId: string) => {
    try {
      await complianceAPI.approveReport(reportId);
      toast({
        title: "Reporte aprobado",
        description: "El reporte ha sido aprobado para envio",
      });
      loadData();
    } catch (error) {
      toast({
        title: "Error",
        description: "No se pudo aprobar el reporte",
        variant: "destructive",
      });
    }
  };

  const handleSubmitReport = async (reportId: string) => {
    try {
      await complianceAPI.submitReport(reportId);
      toast({
        title: "Reporte enviado",
        description: "El reporte ha sido enviado a la UIF",
      });
      loadData();
    } catch (error) {
      toast({
        title: "Error",
        description: "No se pudo enviar el reporte",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Compliance PLD/AML</h1>
          <p className="text-muted-foreground">
            Sistema de cumplimiento regulatorio - LFPIORPI / UIF
          </p>
        </div>
        <Button onClick={loadData} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Actualizar
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Perfiles KYC</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard?.kyc_statistics?.total_profiles || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              {dashboard?.kyc_statistics?.pending_verification || 0} pendientes de verificacion
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Alertas AML</CardTitle>
            <AlertTriangle className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard?.aml_statistics?.open_alerts || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              {dashboard?.aml_statistics?.alerts_this_month || 0} este mes
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Reportes UIF</CardTitle>
            <FileText className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard?.reporting_statistics?.by_status?.submitted || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              {(dashboard?.reporting_statistics?.by_status?.ready || 0) + (dashboard?.reporting_statistics?.by_status?.draft || 0)} pendientes
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Alto Riesgo</CardTitle>
            <Shield className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard?.kyc_statistics?.high_risk_users || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              {dashboard?.kyc_statistics?.pep_count || 0} PEPs identificados
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Tabs */}
      <Tabs defaultValue="alerts" className="space-y-4">
        <TabsList>
          <TabsTrigger value="alerts">
            <AlertTriangle className="h-4 w-4 mr-2" />
            Alertas AML
          </TabsTrigger>
          <TabsTrigger value="reports">
            <FileText className="h-4 w-4 mr-2" />
            Reportes UIF
          </TabsTrigger>
          <TabsTrigger value="statistics">
            <Activity className="h-4 w-4 mr-2" />
            Estadisticas
          </TabsTrigger>
        </TabsList>

        {/* Alerts Tab */}
        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Alertas de Prevencion de Lavado de Dinero</CardTitle>
                  <CardDescription>
                    Monitoreo automatico de transacciones sospechosas
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Select defaultValue="all">
                    <SelectTrigger className="w-32">
                      <SelectValue placeholder="Severidad" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todas</SelectItem>
                      <SelectItem value="critical">Criticas</SelectItem>
                      <SelectItem value="high">Altas</SelectItem>
                      <SelectItem value="medium">Medias</SelectItem>
                      <SelectItem value="low">Bajas</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Titulo</TableHead>
                    <TableHead>Severidad</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Monto</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead>Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {alerts.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                        <CheckCircle className="h-12 w-12 mx-auto mb-2 text-green-500" />
                        No hay alertas activas
                      </TableCell>
                    </TableRow>
                  ) : (
                    alerts.map((alert) => (
                      <TableRow key={alert.id}>
                        <TableCell>
                          <Badge variant="outline">
                            {alert.alert_type.replace(/_/g, " ")}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium">{alert.title}</TableCell>
                        <TableCell>
                          <Badge className={severityColors[alert.severity] || "bg-gray-100"}>
                            {alert.severity.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className={statusColors[alert.status] || "bg-gray-100"}>
                            {alert.status.replace(/_/g, " ")}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {alert.amount
                            ? `$${alert.amount.toLocaleString()} ${alert.currency}`
                            : "-"}
                        </TableCell>
                        <TableCell>
                          {new Date(alert.detected_at).toLocaleDateString("es-MX")}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Dialog>
                              <DialogTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setSelectedAlert(alert)}
                                >
                                  <Eye className="h-4 w-4" />
                                </Button>
                              </DialogTrigger>
                              <DialogContent className="max-w-2xl">
                                <DialogHeader>
                                  <DialogTitle>Detalle de Alerta</DialogTitle>
                                  <DialogDescription>
                                    {alert.title}
                                  </DialogDescription>
                                </DialogHeader>
                                <div className="space-y-4">
                                  <div className="grid grid-cols-2 gap-4">
                                    <div>
                                      <Label>Tipo</Label>
                                      <p className="text-sm">{alert.alert_type.replace(/_/g, " ")}</p>
                                    </div>
                                    <div>
                                      <Label>Severidad</Label>
                                      <Badge className={severityColors[alert.severity]}>
                                        {alert.severity.toUpperCase()}
                                      </Badge>
                                    </div>
                                    <div>
                                      <Label>Monto</Label>
                                      <p className="text-sm">
                                        {alert.amount
                                          ? `$${alert.amount.toLocaleString()} ${alert.currency}`
                                          : "N/A"}
                                      </p>
                                    </div>
                                    <div>
                                      <Label>Regla</Label>
                                      <p className="text-sm">{alert.rule_name || "Automatica"}</p>
                                    </div>
                                  </div>
                                  <div>
                                    <Label>Descripcion</Label>
                                    <p className="text-sm text-muted-foreground">
                                      {alert.description}
                                    </p>
                                  </div>
                                  {alert.status === "open" && (
                                    <div>
                                      <Label>Notas de Investigacion</Label>
                                      <Textarea
                                        value={investigationNotes}
                                        onChange={(e) => setInvestigationNotes(e.target.value)}
                                        placeholder="Ingrese notas para la investigacion..."
                                      />
                                    </div>
                                  )}
                                </div>
                                <DialogFooter className="gap-2">
                                  {alert.status === "open" && (
                                    <>
                                      <Button
                                        variant="outline"
                                        onClick={() => handleInvestigate(alert.id)}
                                      >
                                        <Search className="h-4 w-4 mr-2" />
                                        Investigar
                                      </Button>
                                      <Button
                                        variant="destructive"
                                        onClick={() => handleEscalate(alert.id)}
                                      >
                                        <AlertCircle className="h-4 w-4 mr-2" />
                                        Escalar
                                      </Button>
                                    </>
                                  )}
                                  {(alert.status === "open" || alert.status === "investigating") && (
                                    <Dialog>
                                      <DialogTrigger asChild>
                                        <Button variant="secondary">
                                          <XCircle className="h-4 w-4 mr-2" />
                                          Cerrar
                                        </Button>
                                      </DialogTrigger>
                                      <DialogContent>
                                        <DialogHeader>
                                          <DialogTitle>Cerrar Alerta</DialogTitle>
                                        </DialogHeader>
                                        <div className="space-y-4">
                                          <div className="flex items-center gap-2">
                                            <input
                                              type="checkbox"
                                              id="falsePositive"
                                              checked={isFalsePositive}
                                              onChange={(e) => setIsFalsePositive(e.target.checked)}
                                            />
                                            <Label htmlFor="falsePositive">
                                              Marcar como falso positivo
                                            </Label>
                                          </div>
                                          <div>
                                            <Label>Notas de cierre</Label>
                                            <Textarea
                                              value={closeNotes}
                                              onChange={(e) => setCloseNotes(e.target.value)}
                                              placeholder="Explique la razon del cierre..."
                                            />
                                          </div>
                                        </div>
                                        <DialogFooter>
                                          <Button onClick={() => handleCloseAlert(alert.id)}>
                                            Confirmar Cierre
                                          </Button>
                                        </DialogFooter>
                                      </DialogContent>
                                    </Dialog>
                                  )}
                                </DialogFooter>
                              </DialogContent>
                            </Dialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Reports Tab */}
        <TabsContent value="reports" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Generate ROV */}
            <Card>
              <CardHeader>
                <CardTitle>Generar ROV</CardTitle>
                <CardDescription>
                  Reporte de Operaciones con Activos Virtuales
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Fecha Inicio</Label>
                    <Input
                      type="date"
                      value={rovPeriod.start}
                      onChange={(e) =>
                        setRovPeriod({ ...rovPeriod, start: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <Label>Fecha Fin</Label>
                    <Input
                      type="date"
                      value={rovPeriod.end}
                      onChange={(e) =>
                        setRovPeriod({ ...rovPeriod, end: e.target.value })
                      }
                    />
                  </div>
                </div>
                <Button onClick={handleGenerateROV} className="w-full">
                  <FileText className="h-4 w-4 mr-2" />
                  Generar Reporte ROV
                </Button>
              </CardContent>
            </Card>

            {/* Generate ROS Info */}
            <Card>
              <CardHeader>
                <CardTitle>Generar ROS</CardTitle>
                <CardDescription>
                  Reporte de Operaciones Sospechosas
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Para generar un ROS, seleccione las alertas relevantes desde la
                  pestana de Alertas AML y escale para incluirlas en el reporte.
                </p>
                <div className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 text-orange-500" />
                  <span>
                    {dashboard?.aml_statistics?.by_severity?.critical || 0} alertas criticas
                    pendientes
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Reports List */}
          <Card>
            <CardHeader>
              <CardTitle>Historial de Reportes</CardTitle>
              <CardDescription>
                Reportes generados para la UIF
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Referencia</TableHead>
                    <TableHead>Periodo</TableHead>
                    <TableHead>Transacciones</TableHead>
                    <TableHead>Monto Total</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reports.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                        No hay reportes generados
                      </TableCell>
                    </TableRow>
                  ) : (
                    reports.map((report) => (
                      <TableRow key={report.id}>
                        <TableCell>
                          <Badge variant="outline">{report.report_type.toUpperCase()}</Badge>
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {report.reference_number}
                        </TableCell>
                        <TableCell>
                          {new Date(report.period_start).toLocaleDateString("es-MX")} -{" "}
                          {new Date(report.period_end).toLocaleDateString("es-MX")}
                        </TableCell>
                        <TableCell>{report.transactions_count}</TableCell>
                        <TableCell>
                          {report.total_amount
                            ? `$${report.total_amount.toLocaleString()} MXN`
                            : "-"}
                        </TableCell>
                        <TableCell>
                          <Badge className={reportStatusColors[report.status]}>
                            {report.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {report.status === "ready" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleApproveReport(report.id)}
                              >
                                <CheckCircle className="h-4 w-4" />
                              </Button>
                            )}
                            {report.status === "approved" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleSubmitReport(report.id)}
                              >
                                <Upload className="h-4 w-4" />
                              </Button>
                            )}
                            <Button variant="ghost" size="sm">
                              <Download className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Statistics Tab */}
        <TabsContent value="statistics" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {/* KYC by Level */}
            <Card>
              <CardHeader>
                <CardTitle>KYC por Nivel</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(dashboard?.kyc_statistics?.by_level || {}).map(
                    ([level, count]) => (
                      <div key={level} className="flex justify-between items-center">
                        <span className="text-sm">{level.replace(/_/g, " ")}</span>
                        <Badge variant="secondary">{count as number}</Badge>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Alerts by Severity */}
            <Card>
              <CardHeader>
                <CardTitle>Alertas por Severidad</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(dashboard?.aml_statistics?.by_severity || {}).map(
                    ([severity, count]) => (
                      <div key={severity} className="flex justify-between items-center">
                        <Badge className={severityColors[severity]}>
                          {severity.toUpperCase()}
                        </Badge>
                        <span className="font-medium">{count as number}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Alerts by Type */}
            <Card>
              <CardHeader>
                <CardTitle>Alertas por Tipo</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(dashboard?.aml_statistics?.by_type || {}).map(
                    ([type, count]) => (
                      <div key={type} className="flex justify-between items-center">
                        <span className="text-sm">{type.replace(/_/g, " ")}</span>
                        <Badge variant="outline">{count as number}</Badge>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Risk Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Resumen de Riesgo</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Score Promedio</span>
                    <Badge variant="secondary">
                      {dashboard?.kyc_statistics?.avg_risk_score?.toFixed(1) || 0}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Usuarios Alto Riesgo</span>
                    <Badge className="bg-red-100 text-red-800">
                      {dashboard?.kyc_statistics?.high_risk_users || 0}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">PEPs Identificados</span>
                    <Badge className="bg-orange-100 text-orange-800">
                      {dashboard?.kyc_statistics?.pep_count || 0}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Escalation Rate */}
            <Card>
              <CardHeader>
                <CardTitle>Tasa de Escalamiento</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-center">
                  <div className="text-4xl font-bold text-orange-500">
                    {((dashboard?.aml_statistics?.escalation_rate || 0) * 100).toFixed(1)}%
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    de alertas requieren escalamiento
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Monthly Trend */}
            <Card>
              <CardHeader>
                <CardTitle>Tendencia Mensual</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center gap-2">
                  <TrendingUp className="h-8 w-8 text-green-500" />
                  <div>
                    <div className="text-2xl font-bold">
                      {dashboard?.aml_statistics?.alerts_this_month || 0}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      alertas este mes
                    </p>
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
