"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Bell,
  RefreshCw,
  History,
  AlertTriangle,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AlertCard, AlertFilters, AlertStats } from "@/components/alerts";
import { monitoringAPI } from "@/lib/api-client";
import { useMonitoringWebSocket } from "@/hooks/use-monitoring-websocket";
import {
  MonitoringAlert,
  MonitoringAlertSeverity,
  MonitoringAlertStatus,
  AlertSummary,
} from "@/types";
import { useAuthStore } from "@/store/auth-store";

export default function AlertsPage() {
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  // Alerts data
  const [alerts, setAlerts] = useState<MonitoringAlert[]>([]);
  const [historyAlerts, setHistoryAlerts] = useState<MonitoringAlert[]>([]);
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<MonitoringAlertStatus | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<MonitoringAlertSeverity | "all">("all");

  // Active tab
  const [activeTab, setActiveTab] = useState("active");

  // WebSocket handlers
  const handleAlertTriggered = useCallback((data: Record<string, any>) => {
    const newAlert: MonitoringAlert = {
      id: data.id,
      type: data.type,
      severity: data.severity,
      status: "active",
      title: data.title,
      message: data.message,
      triggered_at: data.triggered_at || new Date().toISOString(),
      acknowledged_at: null,
      acknowledged_by: null,
      resolved_at: null,
      remittance_id: data.remittance_id || null,
      job_id: data.job_id || null,
    };

    setAlerts((prev) => [newAlert, ...prev]);
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
    setLastUpdate(new Date());
  }, []);

  const handleAlertResolved = useCallback((data: Record<string, any>) => {
    setAlerts((prev) =>
      prev.map((alert) =>
        alert.id === data.id
          ? { ...alert, status: "resolved" as MonitoringAlertStatus, resolved_at: new Date().toISOString() }
          : alert
      )
    );
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
    setLastUpdate(new Date());
  }, []);

  // WebSocket connection
  const { isConnected } = useMonitoringWebSocket({
    onAlertTriggered: handleAlertTriggered,
    onAlertResolved: handleAlertResolved,
    autoReconnect: true,
  });

  // Load data
  const loadData = useCallback(async () => {
    try {
      setError(null);

      // Build params for active alerts
      const activeParams: { status?: string; severity?: string; limit?: number } = {
        limit: 100,
      };
      if (statusFilter !== "all") {
        activeParams.status = statusFilter;
      }
      if (severityFilter !== "all") {
        activeParams.severity = severityFilter;
      }

      // Load alerts and summary
      const [alertsData, summaryData] = await Promise.all([
        monitoringAPI.listAlerts(activeParams).catch(() => []),
        monitoringAPI.getAlertSummary().catch(() => null),
      ]);

      setAlerts(alertsData);
      setAlertSummary(summaryData);
      setLastUpdate(new Date());
    } catch (err: any) {
      console.error("Error loading alerts:", err);
      setError(err.message || "Error al cargar alertas");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, severityFilter]);

  // Load history
  const loadHistory = useCallback(async () => {
    try {
      const historyData = await monitoringAPI.listAlerts({
        status: "resolved",
        limit: 50,
      });
      setHistoryAlerts(historyData);
    } catch (err) {
      console.error("Error loading alert history:", err);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (activeTab === "history") {
      loadHistory();
    }
  }, [activeTab, loadHistory]);

  // Actions
  const handleAcknowledge = async (alertId: string, comment?: string) => {
    try {
      await monitoringAPI.acknowledgeAlert(alertId, user?.email || "admin", comment);
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === alertId
            ? {
                ...alert,
                status: "acknowledged" as MonitoringAlertStatus,
                acknowledged_at: new Date().toISOString(),
                acknowledged_by: user?.email || "admin",
              }
            : alert
        )
      );
    } catch (err: any) {
      console.error("Error acknowledging alert:", err);
      throw err;
    }
  };

  const handleResolve = async (alertId: string) => {
    try {
      await monitoringAPI.resolveAlert(alertId);
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === alertId
            ? {
                ...alert,
                status: "resolved" as MonitoringAlertStatus,
                resolved_at: new Date().toISOString(),
              }
            : alert
        )
      );
      // Update summary
      setAlertSummary((prev) => {
        if (!prev) return prev;
        const alert = alerts.find((a) => a.id === alertId);
        if (!alert) return prev;
        return {
          ...prev,
          total_active: Math.max(0, prev.total_active - 1),
          by_severity: {
            ...prev.by_severity,
            [alert.severity]: Math.max(0, (prev.by_severity[alert.severity] || 0) - 1),
          },
        };
      });
    } catch (err: any) {
      console.error("Error resolving alert:", err);
      throw err;
    }
  };

  const handleSilence = async (alertId: string, durationMinutes: number, reason?: string) => {
    try {
      await monitoringAPI.silenceAlert(alertId, durationMinutes, reason);
      setAlerts((prev) =>
        prev.map((alert) =>
          alert.id === alertId
            ? {
                ...alert,
                status: "silenced" as MonitoringAlertStatus,
              }
            : alert
        )
      );
    } catch (err: any) {
      console.error("Error silencing alert:", err);
      throw err;
    }
  };

  const clearFilters = () => {
    setStatusFilter("all");
    setSeverityFilter("all");
  };

  // Filter alerts for display
  const filteredAlerts = alerts.filter((alert) => {
    if (statusFilter !== "all" && alert.status !== statusFilter) return false;
    if (severityFilter !== "all" && alert.severity !== severityFilter) return false;
    return true;
  });

  const activeAlerts = filteredAlerts.filter(
    (a) => a.status === "active" || a.status === "acknowledged"
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">Cargando alertas...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
            <Bell className="h-8 w-8" />
            Panel de Alertas
          </h1>
          <p className="text-muted-foreground">
            Gestiona alertas del sistema y monitoreo
          </p>
        </div>
        <div className="flex items-center gap-4">
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

          {/* Refresh */}
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
          {isConnected && " (tiempo real activo)"}
        </p>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Stats */}
      {alertSummary && <AlertStats summary={alertSummary} />}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="active" className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Activas
              {activeAlerts.length > 0 && (
                <Badge variant="destructive" className="ml-1">
                  {activeAlerts.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="all" className="flex items-center gap-2">
              <Bell className="h-4 w-4" />
              Todas
            </TabsTrigger>
            <TabsTrigger value="history" className="flex items-center gap-2">
              <History className="h-4 w-4" />
              Historial
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Active Alerts Tab */}
        <TabsContent value="active" className="space-y-4">
          <AlertFilters
            status={statusFilter}
            severity={severityFilter}
            onStatusChange={setStatusFilter}
            onSeverityChange={setSeverityFilter}
            onClearFilters={clearFilters}
            activeCount={activeAlerts.length}
          />

          {activeAlerts.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <AlertTriangle className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-600">Sin alertas activas</h3>
              <p className="text-sm text-gray-500 mt-1">
                No hay alertas activas que requieran atencion
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {activeAlerts.map((alert) => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                  onSilence={handleSilence}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* All Alerts Tab */}
        <TabsContent value="all" className="space-y-4">
          <AlertFilters
            status={statusFilter}
            severity={severityFilter}
            onStatusChange={setStatusFilter}
            onSeverityChange={setSeverityFilter}
            onClearFilters={clearFilters}
            activeCount={filteredAlerts.length}
          />

          {filteredAlerts.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <Bell className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-600">Sin alertas</h3>
              <p className="text-sm text-gray-500 mt-1">
                No hay alertas que coincidan con los filtros
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredAlerts.map((alert) => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                  onSilence={handleSilence}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <History className="h-4 w-4" />
              Ultimas 50 alertas resueltas
            </div>
            <Button variant="outline" size="sm" onClick={loadHistory}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Actualizar
            </Button>
          </div>

          {historyAlerts.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <History className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-600">Sin historial</h3>
              <p className="text-sm text-gray-500 mt-1">
                No hay alertas resueltas en el historial
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {historyAlerts.map((alert) => (
                <AlertCard key={alert.id} alert={alert} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
