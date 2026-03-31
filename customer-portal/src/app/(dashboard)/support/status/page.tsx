"use client";

import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  Wrench,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from "lucide-react";
import {
  useStatusPage,
  SystemStatus,
  systemStatusLabels,
  systemStatusColors,
} from "@/features/support/hooks/use-support";
import { format, formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";
import { useState } from "react";

const statusIcons: Record<SystemStatus, React.ReactNode> = {
  operational: <CheckCircle className="w-5 h-5 text-green-500" />,
  degraded: <AlertTriangle className="w-5 h-5 text-yellow-500" />,
  partial_outage: <AlertTriangle className="w-5 h-5 text-orange-500" />,
  major_outage: <XCircle className="w-5 h-5 text-red-500" />,
  maintenance: <Wrench className="w-5 h-5 text-blue-500" />,
};

export default function StatusPage() {
  const { data, isLoading, refetch, isFetching } = useStatusPage();
  const [expandedIncident, setExpandedIncident] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Error al cargar el estado del sistema</p>
      </div>
    );
  }

  const getOverallStatusColor = (status: string) => {
    switch (status) {
      case "operational":
        return "bg-green-500";
      case "degraded":
        return "bg-yellow-500";
      case "partial_outage":
        return "bg-orange-500";
      case "major_outage":
        return "bg-red-500";
      case "maintenance":
        return "bg-blue-500";
      default:
        return "bg-gray-500";
    }
  };

  const getOverallStatusText = (status: string) => {
    switch (status) {
      case "operational":
        return "Todos los sistemas operativos";
      case "degraded":
        return "Rendimiento degradado";
      case "partial_outage":
        return "Interrupción parcial";
      case "major_outage":
        return "Interrupción mayor";
      case "maintenance":
        return "En mantenimiento";
      default:
        return "Estado desconocido";
    }
  };

  // Group components by group
  const componentsByGroup = data.components.reduce(
    (acc, comp) => {
      const group = comp.group || "General";
      if (!acc[group]) acc[group] = [];
      acc[group].push(comp);
      return acc;
    },
    {} as Record<string, typeof data.components>
  );

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Estado del Sistema
          </h1>
          <p className="text-gray-600 mt-1">
            Estado actual de los servicios de FinCore
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`} />
          Actualizar
        </button>
      </div>

      {/* Overall Status */}
      <div
        className={`p-6 rounded-lg text-white ${getOverallStatusColor(data.overall_status)}`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {statusIcons[data.overall_status as SystemStatus]}
            <span className="text-xl font-semibold">
              {getOverallStatusText(data.overall_status)}
            </span>
          </div>
          <span className="text-sm opacity-90">
            Actualizado{" "}
            {formatDistanceToNow(new Date(data.last_updated), {
              addSuffix: true,
              locale: es,
            })}
          </span>
        </div>
      </div>

      {/* Active Incidents */}
      {data.active_incidents.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Incidentes Activos
          </h2>
          {data.active_incidents.map((incident) => (
            <div
              key={incident.id}
              className="bg-red-50 border border-red-200 rounded-lg overflow-hidden"
            >
              <button
                onClick={() =>
                  setExpandedIncident(
                    expandedIncident === incident.id ? null : incident.id
                  )
                }
                className="w-full p-4 flex items-center justify-between text-left"
              >
                <div className="flex items-center gap-3">
                  <XCircle className="w-5 h-5 text-red-500" />
                  <div>
                    <h3 className="font-medium text-gray-900">
                      {incident.title}
                    </h3>
                    <p className="text-sm text-gray-600">
                      {incident.component_name} -{" "}
                      {formatDistanceToNow(new Date(incident.created_at), {
                        addSuffix: true,
                        locale: es,
                      })}
                    </p>
                  </div>
                </div>
                {expandedIncident === incident.id ? (
                  <ChevronUp className="w-5 h-5 text-gray-400" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-gray-400" />
                )}
              </button>
              {expandedIncident === incident.id && (
                <div className="px-4 pb-4 space-y-3">
                  {incident.description && (
                    <p className="text-gray-700">{incident.description}</p>
                  )}
                  {incident.updates.length > 0 && (
                    <div className="border-t border-red-200 pt-3 space-y-2">
                      <h4 className="text-sm font-medium text-gray-700">
                        Actualizaciones
                      </h4>
                      {incident.updates.map((update) => (
                        <div key={update.id} className="flex gap-3 text-sm">
                          <span className="text-gray-500 whitespace-nowrap">
                            {format(new Date(update.created_at), "HH:mm", {
                              locale: es,
                            })}
                          </span>
                          <p className="text-gray-700">{update.message}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Scheduled Maintenance */}
      {data.scheduled_maintenances.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Mantenimiento Programado
          </h2>
          {data.scheduled_maintenances.map((maintenance) => (
            <div
              key={maintenance.id}
              className="bg-blue-50 border border-blue-200 rounded-lg p-4"
            >
              <div className="flex items-start gap-3">
                <Wrench className="w-5 h-5 text-blue-500 mt-0.5" />
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900">
                    {maintenance.title}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {maintenance.description}
                  </p>
                  {maintenance.scheduled_for && (
                    <div className="flex items-center gap-2 mt-2 text-sm text-blue-700">
                      <Clock className="w-4 h-4" />
                      {format(
                        new Date(maintenance.scheduled_for),
                        "PPp",
                        { locale: es }
                      )}
                      {maintenance.scheduled_until && (
                        <>
                          {" - "}
                          {format(
                            new Date(maintenance.scheduled_until),
                            "PPp",
                            { locale: es }
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Components by Group */}
      <div className="space-y-6">
        <h2 className="text-lg font-semibold text-gray-900">Componentes</h2>
        {Object.entries(componentsByGroup).map(([group, components]) => (
          <div
            key={group}
            className="bg-white rounded-lg border border-gray-200 overflow-hidden"
          >
            <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
              <h3 className="font-medium text-gray-700">{group}</h3>
            </div>
            <div className="divide-y divide-gray-100">
              {components.map((comp) => (
                <div
                  key={comp.id}
                  className="px-4 py-3 flex items-center justify-between"
                >
                  <div>
                    <span className="font-medium text-gray-900">
                      {comp.name}
                    </span>
                    {comp.description && (
                      <p className="text-sm text-gray-500">{comp.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {statusIcons[comp.status as SystemStatus]}
                    <span
                      className={`text-sm ${
                        comp.status === "operational"
                          ? "text-green-600"
                          : comp.status === "degraded"
                            ? "text-yellow-600"
                            : comp.status === "maintenance"
                              ? "text-blue-600"
                              : "text-red-600"
                      }`}
                    >
                      {systemStatusLabels[comp.status as SystemStatus]}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Recent Incidents */}
      {data.recent_incidents.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Incidentes Recientes
          </h2>
          <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
            {data.recent_incidents.map((incident) => (
              <div key={incident.id} className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <h3 className="font-medium text-gray-900">
                        {incident.title}
                      </h3>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {incident.component_name} - Resuelto{" "}
                      {incident.resolved_at &&
                        formatDistanceToNow(new Date(incident.resolved_at), {
                          addSuffix: true,
                          locale: es,
                        })}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="text-center text-sm text-gray-500 pt-6 border-t border-gray-200">
        <p>
          ¿Tienes problemas?{" "}
          <a href="/support" className="text-purple-600 hover:underline">
            Contacta a soporte
          </a>
        </p>
      </div>
    </div>
  );
}
