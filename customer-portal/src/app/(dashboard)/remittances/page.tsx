"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Plus,
  Search,
  Filter,
  ChevronRight,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  RefreshCw,
  Ban,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useRemittances } from "@/features/remittances/hooks/use-remittances";
import type { RemittanceStatus, Remittance } from "@/types";

// Configuración de estados
const statusConfig: Record<
  RemittanceStatus,
  { label: string; color: string; icon: React.ComponentType<{ className?: string }> }
> = {
  initiated: { label: "Iniciada", color: "bg-blue-100 text-blue-800", icon: Clock },
  pending_deposit: { label: "Esperando pago", color: "bg-yellow-100 text-yellow-800", icon: Clock },
  deposited: { label: "Pagada", color: "bg-blue-100 text-blue-800", icon: CheckCircle2 },
  locked: { label: "Asegurada", color: "bg-purple-100 text-purple-800", icon: CheckCircle2 },
  processing: { label: "Procesando", color: "bg-blue-100 text-blue-800", icon: Loader2 },
  disbursed: { label: "Entregada", color: "bg-green-100 text-green-800", icon: CheckCircle2 },
  completed: { label: "Completada", color: "bg-green-100 text-green-800", icon: CheckCircle2 },
  refund_pending: { label: "Reembolso", color: "bg-orange-100 text-orange-800", icon: AlertCircle },
  refunded: { label: "Reembolsada", color: "bg-gray-100 text-gray-800", icon: RefreshCw },
  failed: { label: "Fallida", color: "bg-red-100 text-red-800", icon: XCircle },
  cancelled: { label: "Cancelada", color: "bg-gray-100 text-gray-800", icon: Ban },
  expired: { label: "Expirada", color: "bg-gray-100 text-gray-800", icon: XCircle },
};

const statusFilters = [
  { value: "all", label: "Todas" },
  { value: "active", label: "Activas" },
  { value: "completed", label: "Completadas" },
  { value: "cancelled", label: "Canceladas" },
];

export default function RemittancesPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Mapear filtro a estados del backend
  const getStatusParam = () => {
    switch (statusFilter) {
      case "active":
        return "initiated,pending_deposit,deposited,locked,processing";
      case "completed":
        return "completed,disbursed";
      case "cancelled":
        return "cancelled,failed,refunded,expired";
      default:
        return undefined;
    }
  };

  const { data, isLoading, error } = useRemittances({
    page,
    pageSize: 10,
    status: getStatusParam(),
  });

  const remittances = data?.items ?? [];
  const hasMore = data?.has_more ?? false;

  // Filtrar por búsqueda local (referencia o beneficiario)
  const filteredRemittances = searchQuery
    ? remittances.filter(
        (r) =>
          r.reference_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
          r.recipient_info.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : remittances;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Mis remesas</h1>
          <p className="text-muted-foreground">
            Historial de todas tus transferencias
          </p>
        </div>
        <Link href="/remittances/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Nueva remesa
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por referencia o beneficiario..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full sm:w-[180px]">
            <Filter className="h-4 w-4 mr-2" />
            <SelectValue placeholder="Filtrar por estado" />
          </SelectTrigger>
          <SelectContent>
            {statusFilters.map((filter) => (
              <SelectItem key={filter.value} value={filter.value}>
                {filter.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <Skeleton className="h-12 w-12 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                  <Skeleton className="h-6 w-20" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Error state */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <XCircle className="h-12 w-12 text-destructive" />
            <div className="text-center">
              <h2 className="text-lg font-semibold">Error al cargar remesas</h2>
              <p className="text-sm text-muted-foreground">
                {error instanceof Error ? error.message : "Intenta de nuevo"}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!isLoading && !error && filteredRemittances.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
              <Clock className="h-8 w-8 text-muted-foreground" />
            </div>
            <div className="text-center">
              <h2 className="text-lg font-semibold">No hay remesas</h2>
              <p className="text-sm text-muted-foreground">
                {searchQuery
                  ? "No se encontraron remesas con ese criterio"
                  : "Envía tu primera remesa para verla aquí"}
              </p>
            </div>
            {!searchQuery && (
              <Link href="/remittances/new">
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Enviar dinero
                </Button>
              </Link>
            )}
          </CardContent>
        </Card>
      )}

      {/* Remittances list */}
      {!isLoading && !error && filteredRemittances.length > 0 && (
        <div className="space-y-3">
          {filteredRemittances.map((remittance) => (
            <RemittanceCard key={remittance.id} remittance={remittance} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {!isLoading && !error && (remittances.length > 0 || page > 1) && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Anterior
          </Button>
          <span className="text-sm text-muted-foreground">Página {page}</span>
          <Button
            variant="outline"
            disabled={!hasMore}
            onClick={() => setPage((p) => p + 1)}
          >
            Siguiente
          </Button>
        </div>
      )}
    </div>
  );
}

// Remittance Card Component
function RemittanceCard({ remittance }: { remittance: Remittance }) {
  const status = statusConfig[remittance.status];
  const StatusIcon = status.icon;

  return (
    <Link href={`/remittances/${remittance.id}`}>
      <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            {/* Icon */}
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
              <span className="text-primary font-bold text-lg">
                {remittance.recipient_info.name.charAt(0).toUpperCase()}
              </span>
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="font-medium truncate">
                  {remittance.recipient_info.name}
                </p>
                <Badge variant="outline" className="text-[10px] shrink-0">
                  #{remittance.reference_code}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                {formatDate(remittance.created_at)}
              </p>
            </div>

            {/* Amount & Status */}
            <div className="text-right flex-shrink-0">
              <p className="font-semibold">
                {formatCurrency(remittance.amount_fiat_destination, remittance.currency_destination)}
              </p>
              <Badge className={`${status.color} text-[10px]`}>
                <StatusIcon className="h-3 w-3 mr-1" />
                {status.label}
              </Badge>
            </div>

            {/* Arrow */}
            <ChevronRight className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
