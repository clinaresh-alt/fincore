"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Send,
  Plus,
  Search,
  Filter,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowRight,
  RefreshCw,
  DollarSign,
  Globe,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { remittancesAPI } from "@/lib/api-client";
import { Remittance, RemittanceStatus } from "@/types";
import { formatCurrency, formatDate } from "@/lib/utils";

const STATUS_CONFIG: Record<RemittanceStatus, { label: string; color: string; icon: React.ElementType }> = {
  initiated: { label: "Iniciada", color: "bg-slate-100 text-slate-700", icon: Clock },
  pending_deposit: { label: "Pendiente Dep.", color: "bg-yellow-100 text-yellow-700", icon: Clock },
  deposited: { label: "Depositada", color: "bg-blue-100 text-blue-700", icon: DollarSign },
  locked: { label: "En Escrow", color: "bg-purple-100 text-purple-700", icon: Clock },
  processing: { label: "Procesando", color: "bg-indigo-100 text-indigo-700", icon: RefreshCw },
  disbursed: { label: "Desembolsada", color: "bg-teal-100 text-teal-700", icon: Send },
  completed: { label: "Completada", color: "bg-green-100 text-green-700", icon: CheckCircle2 },
  refund_pending: { label: "Reembolso Pend.", color: "bg-orange-100 text-orange-700", icon: AlertCircle },
  refunded: { label: "Reembolsada", color: "bg-gray-100 text-gray-700", icon: RefreshCw },
  failed: { label: "Fallida", color: "bg-red-100 text-red-700", icon: XCircle },
  cancelled: { label: "Cancelada", color: "bg-gray-100 text-gray-600", icon: XCircle },
  expired: { label: "Expirada", color: "bg-amber-100 text-amber-700", icon: Clock },
};

const CURRENCY_FLAGS: Record<string, string> = {
  USD: "US",
  MXN: "MX",
  EUR: "EU",
  CLP: "CL",
  COP: "CO",
  PEN: "PE",
  BRL: "BR",
  ARS: "AR",
};

export default function RemittancesPage() {
  const router = useRouter();
  const [remittances, setRemittances] = useState<Remittance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // KPIs
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    completed: 0,
    totalVolume: 0,
  });

  useEffect(() => {
    loadRemittances();
  }, []);

  const loadRemittances = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await remittancesAPI.list();
      const remittanceList = data.remittances || data || [];
      setRemittances(remittanceList);

      // Calculate stats
      const total = remittanceList.length;
      const pending = remittanceList.filter((r: Remittance) =>
        ["initiated", "pending_deposit", "deposited", "locked", "processing"].includes(r.status)
      ).length;
      const completed = remittanceList.filter((r: Remittance) => r.status === "completed").length;
      const totalVolume = remittanceList.reduce(
        (sum: number, r: Remittance) => sum + Number(r.amount_fiat_source || 0),
        0
      );

      setStats({ total, pending, completed, totalVolume });
    } catch (err: any) {
      console.error("Error loading remittances:", err);
      setError(err.response?.data?.detail || "Error al cargar las remesas");
    } finally {
      setLoading(false);
    }
  };

  const filteredRemittances = remittances.filter((r) => {
    const matchesSearch =
      r.reference_code.toLowerCase().includes(search.toLowerCase()) ||
      r.recipient_info?.full_name?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || r.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: RemittanceStatus) => {
    const config = STATUS_CONFIG[status] || STATUS_CONFIG.initiated;
    const Icon = config.icon;
    return (
      <Badge className={`${config.color} gap-1`}>
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Remesas</h1>
          <p className="text-muted-foreground">
            Enviar dinero de forma segura usando blockchain
          </p>
        </div>
        <Button asChild>
          <Link href="/remittances/new">
            <Plus className="mr-2 h-4 w-4" />
            Nueva Remesa
          </Link>
        </Button>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Remesas</CardTitle>
            <Send className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">En Proceso</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pending}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completadas</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.completed}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Volumen Total</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(stats.totalVolume, "USD")}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Mis Remesas</CardTitle>
          <CardDescription>
            Historial de transferencias internacionales
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar por referencia o beneficiario..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-48">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Estado" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los estados</SelectItem>
                <SelectItem value="initiated">Iniciada</SelectItem>
                <SelectItem value="pending_deposit">Pendiente Dep.</SelectItem>
                <SelectItem value="locked">En Escrow</SelectItem>
                <SelectItem value="processing">Procesando</SelectItem>
                <SelectItem value="completed">Completada</SelectItem>
                <SelectItem value="refunded">Reembolsada</SelectItem>
                <SelectItem value="cancelled">Cancelada</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={loadRemittances}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>

          {filteredRemittances.length === 0 ? (
            <div className="text-center py-12">
              <Globe className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No hay remesas</h3>
              <p className="text-muted-foreground mb-4">
                {search || statusFilter !== "all"
                  ? "No se encontraron remesas con los filtros seleccionados"
                  : "Comienza enviando tu primera remesa internacional"}
              </p>
              {!search && statusFilter === "all" && (
                <Button asChild>
                  <Link href="/remittances/new">
                    <Plus className="mr-2 h-4 w-4" />
                    Nueva Remesa
                  </Link>
                </Button>
              )}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Referencia</TableHead>
                    <TableHead>Beneficiario</TableHead>
                    <TableHead>Corredor</TableHead>
                    <TableHead className="text-right">Monto</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Fecha</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRemittances.map((remittance) => (
                    <TableRow
                      key={remittance.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => router.push(`/remittances/${remittance.id}`)}
                    >
                      <TableCell className="font-mono text-sm">
                        {remittance.reference_code}
                      </TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">
                            {remittance.recipient_info?.full_name || "N/A"}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {remittance.recipient_info?.country || ""}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{remittance.currency_source}</span>
                          <ArrowRight className="h-3 w-3 text-muted-foreground" />
                          <span className="font-medium">{remittance.currency_destination}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div>
                          <div className="font-medium">
                            {formatCurrency(
                              Number(remittance.amount_fiat_source),
                              remittance.currency_source
                            )}
                          </div>
                          {remittance.amount_fiat_destination && (
                            <div className="text-xs text-muted-foreground">
                              {formatCurrency(
                                Number(remittance.amount_fiat_destination),
                                remittance.currency_destination
                              )}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{getStatusBadge(remittance.status)}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(remittance.created_at)}
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm">
                          <ArrowRight className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
