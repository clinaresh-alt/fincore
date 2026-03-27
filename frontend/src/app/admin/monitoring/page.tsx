"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  RefreshCw,
  Server,
  DollarSign,
  Send,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Percent,
  Cpu,
  HardDrive,
  Wifi,
  WifiOff,
  TrendingUp,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ServiceStatusCard, MetricsCard, QueueStatus } from "@/components/monitoring";
import { monitoringAPI } from "@/lib/api-client";
import { useMonitoringWebSocket } from "@/hooks/use-monitoring-websocket";
import {
  DashboardSnapshot,
  SystemStatus,
  RemittanceMetrics,
  FinancialMetrics,
  QueueMetrics,
  SystemMetrics,
  AlertSummary,
} from "@/types";
import { formatCurrency } from "@/lib/utils";

// Nombres de servicios
const SERVICE_NAMES: Record<string, string> = {
  database: "Base de Datos",
  redis: "Redis Cache",
  stp: "STP (SPEI)",
  bitso: "Bitso Exchange",
  blockchain: "Blockchain",
};

export default function MonitoringPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [useWebSocket, setUseWebSocket] = useState(true);

  // Data states
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [remittanceMetrics, setRemittanceMetrics] = useState<RemittanceMetrics | null>(null);
  const [financialMetrics, setFinancialMetrics] = useState<FinancialMetrics | null>(null);
  const [queueMetrics, setQueueMetrics] = useState<QueueMetrics | null>(null);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null);

  // WebSocket handlers para actualizaciones en tiempo real
  const handleMetricsUpdate = useCallback((data: Record<string, any>) => {
    setLastUpdate(new Date());

    if (data.remittance_metrics) {
      setRemittanceMetrics(data.remittance_metrics);
    }
    if (data.financial_metrics) {
      setFinancialMetrics(data.financial_metrics);
    }
    if (data.queue_metrics) {
      setQueueMetrics(data.queue_metrics);
    }
    if (data.system_metrics) {
      setSystemMetrics(data.system_metrics);
    }
    if (data.system_status) {
      setSystemStatus(data.system_status);
    }
    if (data.alert_summary) {
      setAlertSummary(data.alert_summary);
    }
  }, []);

  const handleAlertTriggered = useCallback((data: Record<string, any>) => {
    // Actualizar el resumen de alertas cuando se dispara una nueva
    setAlertSummary((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        total_active: prev.total_active + 1,
        by_severity: {
          ...prev.by_severity,
          [data.severity]: (prev.by_severity[data.severity] || 0) + 1,
        },
      };
    });
  }, []);

  const handleAlertResolved = useCallback((data: Record<string, any>) => {
    // Actualizar el resumen de alertas cuando se resuelve una
    setAlertSummary((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        total_active: Math.max(0, prev.total_active - 1),
        by_severity: {
          ...prev.by_severity,
          [data.severity]: Math.max(0, (prev.by_severity[data.severity] || 0) - 1),
        },
      };
    });
  }, []);

  const handleStatusChange = useCallback((data: Record<string, any>) => {
    // Actualizar estado de servicios en tiempo real
    setSystemStatus((prev) => {
      if (!prev || !data.service) return prev;
      return {
        ...prev,
        services: {
          ...prev.services,
          [data.service]: {
            status: data.status,
            latency_ms: data.latency_ms,
            error: data.error,
          },
        },
        overall_status: data.overall_status || prev.overall_status,
      };
    });
  }, []);

  // WebSocket connection
  const { isConnected, error: wsError } = useMonitoringWebSocket({
    onMetricsUpdate: handleMetricsUpdate,
    onAlertTriggered: handleAlertTriggered,
    onAlertResolved: handleAlertResolved,
    onStatusChange: handleStatusChange,
    autoReconnect: useWebSocket,
  });

  const loadData = useCallback(async () => {
    try {
      setError(null);

      // Cargar todos los datos en paralelo
      const [status, remittances, financial, queue, system, alerts] = await Promise.all([
        monitoringAPI.getSystemStatus().catch(() => null),
        monitoringAPI.getRemittanceMetrics().catch(() => null),
        monitoringAPI.getFinancialMetrics().catch(() => null),
        monitoringAPI.getQueueMetrics().catch(() => null),
        monitoringAPI.getSystemMetrics().catch(() => null),
        monitoringAPI.getAlertSummary().catch(() => null),
      ]);

      setSystemStatus(status);
      setRemittanceMetrics(remittances);
      setFinancialMetrics(financial);
      setQueueMetrics(queue);
      setSystemMetrics(system);
      setAlertSummary(alerts);
      setLastUpdate(new Date());
    } catch (err: any) {
      console.error("Error loading monitoring data:", err);
      setError(err.message || "Error al cargar datos de monitoreo");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh cada 30 segundos (solo cuando WebSocket no esta conectado)
  useEffect(() => {
    // Si el WebSocket esta conectado, no necesitamos polling
    if (isConnected || !autoRefresh) return;

    const interval = setInterval(() => {
      loadData();
    }, 30000);

    return () => clearInterval(interval);
  }, [autoRefresh, isConnected, loadData]);

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  const getOverallStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "bg-green-100 text-green-800 border-green-200";
      case "degraded":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      case "down":
        return "bg-red-100 text-red-800 border-red-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">Cargando dashboard de monitoreo...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Monitoreo del Sistema</h1>
          <p className="text-muted-foreground">
            Estado en tiempo real de servicios y metricas
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Overall Status Badge */}
          {systemStatus && (
            <Badge
              className={`px-4 py-2 text-sm font-medium ${getOverallStatusColor(
                systemStatus.overall_status
              )}`}
            >
              {systemStatus.overall_status === "healthy" ? (
                <CheckCircle2 className="h-4 w-4 mr-2" />
              ) : (
                <AlertTriangle className="h-4 w-4 mr-2" />
              )}
              {systemStatus.overall_status === "healthy"
                ? "Sistema Operativo"
                : systemStatus.overall_status === "degraded"
                ? "Degradado"
                : "Problemas"}
            </Badge>
          )}

          {/* WebSocket Status */}
          <Badge
            variant="outline"
            className={`${
              isConnected
                ? "bg-green-50 text-green-700 border-green-200"
                : "bg-gray-50 text-gray-500 border-gray-200"
            }`}
          >
            {isConnected ? (
              <Wifi className="h-3 w-3 mr-1.5" />
            ) : (
              <WifiOff className="h-3 w-3 mr-1.5" />
            )}
            {isConnected ? "Tiempo Real" : "Desconectado"}
          </Badge>

          {/* Auto Refresh Toggle (fallback cuando WS no esta disponible) */}
          {!isConnected && (
            <Button
              variant={autoRefresh ? "default" : "outline"}
              size="sm"
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              <Zap className={`h-4 w-4 mr-2 ${autoRefresh ? "text-yellow-300" : ""}`} />
              Auto
            </Button>
          )}

          {/* Manual Refresh */}
          <Button variant="outline" size="sm" onClick={loadData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Actualizar
          </Button>
        </div>
      </div>

      {/* Last Update */}
      {lastUpdate && (
        <p className="text-xs text-muted-foreground">
          Ultima actualizacion: {lastUpdate.toLocaleTimeString()}
          {isConnected
            ? " (WebSocket conectado)"
            : autoRefresh
            ? " (auto-refresh activo)"
            : ""}
        </p>
      )}

      {/* Error Alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Alert Summary */}
      {alertSummary && alertSummary.total_active > 0 && (
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AlertTriangle className="h-6 w-6 text-orange-600" />
                <div>
                  <span className="font-semibold text-orange-800">
                    {alertSummary.total_active} alertas activas
                  </span>
                  <div className="flex gap-2 mt-1">
                    {alertSummary.by_severity.critical && (
                      <Badge variant="destructive" className="text-xs">
                        {alertSummary.by_severity.critical} criticas
                      </Badge>
                    )}
                    {alertSummary.by_severity.error && (
                      <Badge className="bg-red-100 text-red-700 text-xs">
                        {alertSummary.by_severity.error} errores
                      </Badge>
                    )}
                    {alertSummary.by_severity.warning && (
                      <Badge className="bg-yellow-100 text-yellow-700 text-xs">
                        {alertSummary.by_severity.warning} warnings
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
              <Button variant="outline" size="sm" asChild>
                <a href="/admin/alerts">Ver Alertas</a>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Vista General</TabsTrigger>
          <TabsTrigger value="remittances">Remesas</TabsTrigger>
          <TabsTrigger value="financial">Financiero</TabsTrigger>
          <TabsTrigger value="system">Sistema</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Services Status Grid */}
          <div>
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Server className="h-5 w-5" />
              Estado de Servicios
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              {systemStatus &&
                Object.entries(systemStatus.services).map(([name, service]) => (
                  <ServiceStatusCard
                    key={name}
                    name={name}
                    displayName={SERVICE_NAMES[name] || name}
                    status={service.status}
                    latency={service.latency_ms}
                    error={service.error}
                  />
                ))}
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {remittanceMetrics && (
              <>
                <MetricsCard
                  title="Remesas Hoy"
                  value={remittanceMetrics.last_24h_count}
                  subtitle="ultimas 24 horas"
                  icon={Send}
                  color="blue"
                />
                <MetricsCard
                  title="Tasa de Exito"
                  value={`${remittanceMetrics.success_rate.toFixed(1)}%`}
                  subtitle={`${remittanceMetrics.completed_count} completadas`}
                  icon={Percent}
                  color={remittanceMetrics.success_rate >= 95 ? "green" : "yellow"}
                />
              </>
            )}
            {financialMetrics && (
              <>
                <MetricsCard
                  title="Balance USDC"
                  value={formatCurrency(financialMetrics.usdc_balance, "USD")}
                  subtitle="Disponible"
                  icon={DollarSign}
                  color={financialMetrics.usdc_balance > 1000 ? "green" : "red"}
                />
                <MetricsCard
                  title="Tasa USD/MXN"
                  value={financialMetrics.current_rate_usdc_mxn.toFixed(2)}
                  subtitle="Bitso actual"
                  icon={TrendingUp}
                  trend={
                    financialMetrics.rate_change_24h
                      ? { value: financialMetrics.rate_change_24h }
                      : undefined
                  }
                />
              </>
            )}
          </div>

          {/* Queue and System Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Queue Status */}
            {queueMetrics && <QueueStatus metrics={queueMetrics} />}

            {/* System Resources */}
            {systemMetrics && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Cpu className="h-5 w-5" />
                    Recursos del Sistema
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <Cpu className="h-4 w-4 text-blue-500" />
                        CPU
                      </span>
                      <span className="font-medium">{systemMetrics.cpu_usage.toFixed(1)}%</span>
                    </div>
                    <Progress
                      value={systemMetrics.cpu_usage}
                      className={`h-2 ${
                        systemMetrics.cpu_usage > 80 ? "bg-red-100" : "bg-blue-100"
                      }`}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <HardDrive className="h-4 w-4 text-purple-500" />
                        Memoria
                      </span>
                      <span className="font-medium">{systemMetrics.memory_usage.toFixed(1)}%</span>
                    </div>
                    <Progress
                      value={systemMetrics.memory_usage}
                      className={`h-2 ${
                        systemMetrics.memory_usage > 80 ? "bg-red-100" : "bg-purple-100"
                      }`}
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <HardDrive className="h-4 w-4 text-green-500" />
                        Disco
                      </span>
                      <span className="font-medium">{systemMetrics.disk_usage.toFixed(1)}%</span>
                    </div>
                    <Progress
                      value={systemMetrics.disk_usage}
                      className={`h-2 ${
                        systemMetrics.disk_usage > 80 ? "bg-red-100" : "bg-green-100"
                      }`}
                    />
                  </div>

                  <div className="pt-4 border-t grid grid-cols-2 gap-4">
                    <div className="text-center">
                      <div className="text-xs text-muted-foreground">Uptime</div>
                      <div className="text-xl font-bold text-green-600">
                        {formatUptime(systemMetrics.uptime_seconds)}
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-xs text-muted-foreground">Conexiones</div>
                      <div className="text-xl font-bold">{systemMetrics.active_connections}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* Remittances Tab */}
        <TabsContent value="remittances" className="space-y-6">
          {remittanceMetrics && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricsCard
                  title="Total Remesas"
                  value={remittanceMetrics.total_count}
                  icon={Send}
                  color="blue"
                />
                <MetricsCard
                  title="Completadas"
                  value={remittanceMetrics.completed_count}
                  icon={CheckCircle2}
                  color="green"
                />
                <MetricsCard
                  title="Pendientes"
                  value={remittanceMetrics.pending_count}
                  icon={Clock}
                  color="yellow"
                />
                <MetricsCard
                  title="Fallidas"
                  value={remittanceMetrics.failed_count}
                  icon={AlertTriangle}
                  color="red"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <MetricsCard
                  title="Volumen USDC"
                  value={formatCurrency(remittanceMetrics.total_volume_usdc, "USD")}
                  subtitle="Total procesado"
                  icon={DollarSign}
                  size="lg"
                />
                <MetricsCard
                  title="Volumen MXN"
                  value={formatCurrency(remittanceMetrics.total_volume_mxn, "MXN")}
                  subtitle="Total distribuido"
                  icon={DollarSign}
                  size="lg"
                />
                <MetricsCard
                  title="Tiempo Promedio"
                  value={`${(remittanceMetrics.avg_processing_time_seconds / 60).toFixed(1)} min`}
                  subtitle="De inicio a completado"
                  icon={Clock}
                  size="lg"
                />
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Actividad por Periodo</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center p-4 bg-slate-50 rounded-lg">
                      <div className="text-3xl font-bold text-blue-600">
                        {remittanceMetrics.last_hour_count}
                      </div>
                      <div className="text-sm text-muted-foreground">Ultima hora</div>
                    </div>
                    <div className="text-center p-4 bg-slate-50 rounded-lg">
                      <div className="text-3xl font-bold text-blue-600">
                        {remittanceMetrics.last_24h_count}
                      </div>
                      <div className="text-sm text-muted-foreground">Ultimas 24h</div>
                    </div>
                    <div className="text-center p-4 bg-slate-50 rounded-lg">
                      <div className="text-3xl font-bold text-blue-600">
                        {remittanceMetrics.last_7d_count}
                      </div>
                      <div className="text-sm text-muted-foreground">Ultimos 7 dias</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Financial Tab */}
        <TabsContent value="financial" className="space-y-6">
          {financialMetrics && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricsCard
                  title="Balance USDC"
                  value={formatCurrency(financialMetrics.usdc_balance, "USD")}
                  subtitle={`Disponible: ${formatCurrency(financialMetrics.usdc_available, "USD")}`}
                  icon={DollarSign}
                  color="blue"
                  size="lg"
                />
                <MetricsCard
                  title="Balance MXN"
                  value={formatCurrency(financialMetrics.mxn_balance, "MXN")}
                  subtitle={`Disponible: ${formatCurrency(financialMetrics.mxn_available, "MXN")}`}
                  icon={DollarSign}
                  color="green"
                  size="lg"
                />
                <MetricsCard
                  title="Volumen Diario USDC"
                  value={formatCurrency(financialMetrics.daily_volume_usdc, "USD")}
                  subtitle="Hoy"
                  icon={Activity}
                  color="purple"
                  size="lg"
                />
                <MetricsCard
                  title="Volumen Diario MXN"
                  value={formatCurrency(financialMetrics.daily_volume_mxn, "MXN")}
                  subtitle="Hoy"
                  icon={Activity}
                  color="purple"
                  size="lg"
                />
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Tipo de Cambio</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-8">
                    <div>
                      <div className="text-4xl font-bold">
                        ${financialMetrics.current_rate_usdc_mxn.toFixed(4)}
                      </div>
                      <div className="text-muted-foreground">USDC / MXN</div>
                    </div>
                    {financialMetrics.rate_change_24h !== 0 && (
                      <div
                        className={`flex items-center gap-1 ${
                          financialMetrics.rate_change_24h > 0 ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {financialMetrics.rate_change_24h > 0 ? (
                          <TrendingUp className="h-5 w-5" />
                        ) : (
                          <TrendingUp className="h-5 w-5 rotate-180" />
                        )}
                        <span className="text-lg font-medium">
                          {Math.abs(financialMetrics.rate_change_24h).toFixed(2)}%
                        </span>
                        <span className="text-sm text-muted-foreground">24h</span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* System Tab */}
        <TabsContent value="system" className="space-y-6">
          {systemMetrics && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricsCard
                  title="CPU"
                  value={`${systemMetrics.cpu_usage.toFixed(1)}%`}
                  icon={Cpu}
                  color={systemMetrics.cpu_usage > 80 ? "red" : "blue"}
                />
                <MetricsCard
                  title="Memoria"
                  value={`${systemMetrics.memory_usage.toFixed(1)}%`}
                  icon={HardDrive}
                  color={systemMetrics.memory_usage > 80 ? "red" : "purple"}
                />
                <MetricsCard
                  title="Disco"
                  value={`${systemMetrics.disk_usage.toFixed(1)}%`}
                  icon={HardDrive}
                  color={systemMetrics.disk_usage > 80 ? "red" : "green"}
                />
                <MetricsCard
                  title="Uptime"
                  value={formatUptime(systemMetrics.uptime_seconds)}
                  icon={Clock}
                  color="green"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Rendimiento de Red</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Conexiones Activas</span>
                      <span className="text-2xl font-bold">{systemMetrics.active_connections}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Requests/segundo</span>
                      <span className="text-2xl font-bold">
                        {systemMetrics.requests_per_second.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Tiempo Respuesta Prom.</span>
                      <span className="text-2xl font-bold">
                        {systemMetrics.avg_response_time_ms.toFixed(0)} ms
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Tasa de Error</span>
                      <span
                        className={`text-2xl font-bold ${
                          systemMetrics.error_rate > 0.01 ? "text-red-600" : "text-green-600"
                        }`}
                      >
                        {(systemMetrics.error_rate * 100).toFixed(2)}%
                      </span>
                    </div>
                  </CardContent>
                </Card>

                {queueMetrics && <QueueStatus metrics={queueMetrics} />}
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
