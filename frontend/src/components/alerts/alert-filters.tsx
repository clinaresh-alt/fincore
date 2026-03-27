"use client";

import { Filter, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MonitoringAlertSeverity, MonitoringAlertStatus } from "@/types";

interface AlertFiltersProps {
  status: MonitoringAlertStatus | "all";
  severity: MonitoringAlertSeverity | "all";
  onStatusChange: (status: MonitoringAlertStatus | "all") => void;
  onSeverityChange: (severity: MonitoringAlertSeverity | "all") => void;
  onClearFilters: () => void;
  activeCount?: number;
}

export function AlertFilters({
  status,
  severity,
  onStatusChange,
  onSeverityChange,
  onClearFilters,
  activeCount,
}: AlertFiltersProps) {
  const hasFilters = status !== "all" || severity !== "all";

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Filtros:</span>
      </div>

      {/* Status Filter */}
      <Select value={status} onValueChange={(value) => onStatusChange(value as MonitoringAlertStatus | "all")}>
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Estado" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Todos los estados</SelectItem>
          <SelectItem value="active">Activas</SelectItem>
          <SelectItem value="acknowledged">Reconocidas</SelectItem>
          <SelectItem value="resolved">Resueltas</SelectItem>
          <SelectItem value="silenced">Silenciadas</SelectItem>
        </SelectContent>
      </Select>

      {/* Severity Filter */}
      <Select value={severity} onValueChange={(value) => onSeverityChange(value as MonitoringAlertSeverity | "all")}>
        <SelectTrigger className="w-[160px]">
          <SelectValue placeholder="Severidad" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Todas las severidades</SelectItem>
          <SelectItem value="critical">Critica</SelectItem>
          <SelectItem value="error">Error</SelectItem>
          <SelectItem value="warning">Warning</SelectItem>
          <SelectItem value="info">Info</SelectItem>
        </SelectContent>
      </Select>

      {/* Clear Filters */}
      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={onClearFilters}>
          <X className="h-4 w-4 mr-1" />
          Limpiar
        </Button>
      )}

      {/* Active Count */}
      {activeCount !== undefined && (
        <Badge variant="secondary" className="ml-auto">
          {activeCount} alertas
        </Badge>
      )}
    </div>
  );
}
