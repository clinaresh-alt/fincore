"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { companiesAPI } from "@/lib/api-client";
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
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Users,
  Search,
  Plus,
  Pencil,
  Trash2,
  Loader2,
  Building,
  FileText,
  FolderOpen,
  MapPin,
  Phone,
  Mail,
  CheckCircle,
  Clock,
  XCircle,
  AlertCircle,
} from "lucide-react";

interface Company {
  id: string;
  razon_social: string;
  nombre_comercial?: string;
  tipo_empresa: string;
  rfc: string;
  estado_verificacion: string;
  sector?: string;
  municipio?: string;
  estado?: string;
  total_proyectos?: number;
  created_at: string;
}

interface CompanyListResponse {
  items: Company[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const getStatusColor = (status: string) => {
  switch (status) {
    case "Verificada":
    case "Activa":
      return "bg-green-100 text-green-800";
    case "En Revision":
      return "bg-yellow-100 text-yellow-800";
    case "Pendiente":
      return "bg-gray-100 text-gray-800";
    case "Suspendida":
      return "bg-orange-100 text-orange-800";
    case "Rechazada":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case "Verificada":
    case "Activa":
      return <CheckCircle className="h-4 w-4" />;
    case "En Revision":
      return <Clock className="h-4 w-4" />;
    case "Pendiente":
      return <AlertCircle className="h-4 w-4" />;
    case "Suspendida":
    case "Rechazada":
      return <XCircle className="h-4 w-4" />;
    default:
      return <AlertCircle className="h-4 w-4" />;
  }
};

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Estados para eliminar
  const [deletingCompany, setDeletingCompany] = useState<Company | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadCompanies();
  }, [page, statusFilter]);

  const loadCompanies = async () => {
    setError(null);
    try {
      const data: CompanyListResponse = await companiesAPI.list({
        page,
        page_size: 12,
        estado: statusFilter || undefined,
        search: search || undefined,
      });
      setCompanies(data.items);
      setTotalPages(data.total_pages);
      setTotal(data.total);
    } catch (err: any) {
      console.error("Error loading companies:", err);
      if (err.response?.status === 401) {
        setError("Sesion expirada. Por favor inicia sesion nuevamente.");
      } else {
        setError("Error al cargar empresas. Verifica tu conexion.");
      }
      setCompanies([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    loadCompanies();
  };

  const handleDeleteCompany = async () => {
    if (!deletingCompany) return;
    setDeleting(true);
    try {
      await companiesAPI.delete(deletingCompany.id);
      setCompanies(companies.filter((c) => c.id !== deletingCompany.id));
      setDeletingCompany(null);
    } catch (err: any) {
      console.error("Error deleting company:", err);
      setError(err.response?.data?.detail || "Error al eliminar empresa");
    } finally {
      setDeleting(false);
    }
  };

  const statuses = ["Pendiente", "En Revision", "Verificada", "Activa", "Suspendida", "Rechazada"];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Empresas</h1>
          <p className="text-muted-foreground mt-1">
            Gestiona las empresas solicitantes de proyectos
          </p>
        </div>
        <Button asChild>
          <Link href="/companies/new">
            <Plus className="h-4 w-4 mr-2" />
            Nueva Empresa
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar por razon social o RFC..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="pl-10"
            />
          </div>
          <Button onClick={handleSearch} variant="outline">
            Buscar
          </Button>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            variant={statusFilter === null ? "default" : "outline"}
            size="sm"
            onClick={() => { setStatusFilter(null); setPage(1); }}
          >
            Todos
          </Button>
          {statuses.slice(0, 4).map((status) => (
            <Button
              key={status}
              variant={statusFilter === status ? "default" : "outline"}
              size="sm"
              onClick={() => { setStatusFilter(status); setPage(1); }}
            >
              {status}
            </Button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="text-sm text-muted-foreground">
        Mostrando {companies.length} de {total} empresas
      </div>

      {/* Error message */}
      {error && (
        <div className="p-6 rounded-lg bg-red-50 border border-red-200 text-center">
          <p className="text-red-700 mb-4">{error}</p>
          <Button variant="outline" onClick={() => { setLoading(true); loadCompanies(); }}>
            Reintentar
          </Button>
        </div>
      )}

      {/* Companies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {companies.map((company) => (
          <Card
            key={company.id}
            className="hover:shadow-lg transition-shadow cursor-pointer group"
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium mb-2 ${getStatusColor(
                      company.estado_verificacion
                    )}`}
                  >
                    {getStatusIcon(company.estado_verificacion)}
                    {company.estado_verificacion}
                  </span>
                  <CardTitle className="text-lg group-hover:text-primary transition-colors">
                    {company.razon_social}
                  </CardTitle>
                  {company.nombre_comercial && (
                    <p className="text-sm text-muted-foreground">
                      {company.nombre_comercial}
                    </p>
                  )}
                </div>
                <div className="h-10 w-10 rounded-lg bg-slate-100 flex items-center justify-center">
                  <Building className="h-5 w-5 text-slate-600" />
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Info */}
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  <span>RFC: {company.rfc}</span>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Users className="h-4 w-4" />
                  <span>{company.tipo_empresa}</span>
                </div>
                {(company.municipio || company.estado) && (
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <MapPin className="h-4 w-4" />
                    <span>
                      {[company.municipio, company.estado].filter(Boolean).join(", ")}
                    </span>
                  </div>
                )}
              </div>

              {/* Projects count */}
              <div className="flex items-center gap-2 pt-2 border-t">
                <FolderOpen className="h-4 w-4 text-blue-600" />
                <div>
                  <p className="text-sm font-semibold">
                    {company.total_proyectos || 0} proyectos
                  </p>
                  <p className="text-xs text-muted-foreground">asociados</p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <Button className="flex-1 group-hover:bg-primary/90" asChild>
                  <Link href={`/companies/${company.id}`}>
                    Ver Detalles
                  </Link>
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeletingCompany(company);
                  }}
                  title="Eliminar empresa"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {companies.length === 0 && (
        <div className="text-center py-12">
          <Users className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">
            No se encontraron empresas con los filtros seleccionados
          </p>
          <Button asChild className="mt-4">
            <Link href="/companies/new">
              <Plus className="h-4 w-4 mr-2" />
              Crear Primera Empresa
            </Link>
          </Button>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page - 1)}
            disabled={page === 1}
          >
            Anterior
          </Button>
          <span className="flex items-center px-4 text-sm text-muted-foreground">
            Pagina {page} de {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page === totalPages}
          >
            Siguiente
          </Button>
        </div>
      )}

      {/* Dialog de confirmacion para eliminar */}
      <AlertDialog open={!!deletingCompany} onOpenChange={(open) => !open && setDeletingCompany(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar Empresa</AlertDialogTitle>
            <AlertDialogDescription>
              ¿Estas seguro de eliminar la empresa "{deletingCompany?.razon_social}"?
              Esta accion no se puede deshacer y eliminara todos los documentos asociados.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteCompany}
              className="bg-red-600 hover:bg-red-700"
              disabled={deleting}
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Eliminando...
                </>
              ) : (
                "Eliminar"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
