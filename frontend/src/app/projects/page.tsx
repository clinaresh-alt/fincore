"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { projectsAPI } from "@/lib/api-client";
import { Project } from "@/types";
import { formatCurrency, formatPercentage, getProjectStatusColor } from "@/lib/utils";
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
  Building2,
  Search,
  Filter,
  ArrowUpRight,
  Clock,
  TrendingUp,
  Plus,
  Pencil,
  Trash2,
  Loader2,
} from "lucide-react";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Estados para editar
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [editForm, setEditForm] = useState({
    nombre: "",
    descripcion: "",
    sector: "",
    monto_solicitado: 0,
    monto_minimo_inversion: 0,
    plazo_meses: 0,
    fecha_inicio_estimada: "",
    fecha_fin_estimada: "",
    tasa_rendimiento_anual: 0,
    rendimiento_proyectado: 0,
    empresa_solicitante: "",
    tiene_documentacion_completa: false,
  });
  const [saving, setSaving] = useState(false);

  // Estados para eliminar
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    setError(null);
    try {
      const data = await projectsAPI.list();
      setProjects(data);
    } catch (err: any) {
      console.error("Error loading projects:", err);
      if (err.response?.status === 401) {
        setError("Sesion expirada. Por favor inicia sesion nuevamente.");
      } else {
        setError("Error al cargar proyectos. Verifica tu conexion.");
      }
      setProjects([]);
    } finally {
      setLoading(false);
    }
  };

  const sectors = [...new Set(projects.map((p) => p.sector))];

  const openEditModal = (project: Project) => {
    setEditingProject(project);
    setEditForm({
      nombre: project.nombre,
      descripcion: project.descripcion || "",
      sector: project.sector,
      monto_solicitado: project.monto_solicitado,
      monto_minimo_inversion: project.monto_minimo_inversion || 10000,
      plazo_meses: project.plazo_meses,
      fecha_inicio_estimada: project.fecha_inicio_estimada?.split("T")[0] || "",
      fecha_fin_estimada: project.fecha_fin_estimada?.split("T")[0] || "",
      tasa_rendimiento_anual: project.tasa_rendimiento_anual || 0,
      rendimiento_proyectado: project.rendimiento_proyectado || 0,
      empresa_solicitante: project.empresa_solicitante || "",
      tiene_documentacion_completa: project.tiene_documentacion_completa || false,
    });
  };

  const handleSaveProject = async () => {
    if (!editingProject) return;
    setSaving(true);
    try {
      const updated = await projectsAPI.update(editingProject.id, {
        nombre: editForm.nombre,
        descripcion: editForm.descripcion || undefined,
        sector: editForm.sector,
        monto_solicitado: editForm.monto_solicitado,
        monto_minimo_inversion: editForm.monto_minimo_inversion || undefined,
        plazo_meses: editForm.plazo_meses,
        fecha_inicio_estimada: editForm.fecha_inicio_estimada || undefined,
        fecha_fin_estimada: editForm.fecha_fin_estimada || undefined,
        tasa_rendimiento_anual: editForm.tasa_rendimiento_anual || undefined,
        rendimiento_proyectado: editForm.rendimiento_proyectado || undefined,
        empresa_solicitante: editForm.empresa_solicitante || undefined,
        tiene_documentacion_completa: editForm.tiene_documentacion_completa,
      });
      setProjects(projects.map(p => p.id === updated.id ? updated : p));
      setEditingProject(null);
    } catch (err: any) {
      console.error("Error updating project:", err);
      setError(err.response?.data?.detail || "Error al actualizar proyecto");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteProject = async () => {
    if (!deletingProject) return;
    setDeleting(true);
    try {
      await projectsAPI.delete(deletingProject.id);
      setProjects(projects.filter(p => p.id !== deletingProject.id));
      setDeletingProject(null);
    } catch (err: any) {
      console.error("Error deleting project:", err);
      setError(err.response?.data?.detail || "Error al eliminar proyecto");
    } finally {
      setDeleting(false);
    }
  };

  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      p.nombre.toLowerCase().includes(search.toLowerCase()) ||
      p.descripcion?.toLowerCase().includes(search.toLowerCase());
    const matchesSector = !sectorFilter || p.sector === sectorFilter;
    return matchesSearch && matchesSector;
  });

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
          <h1 className="text-3xl font-bold text-slate-900">Proyectos</h1>
          <p className="text-muted-foreground mt-1">
            Explora oportunidades de inversion disponibles
          </p>
        </div>
        <Button asChild>
          <Link href="/projects/new">
            <Plus className="h-4 w-4 mr-2" />
            Nuevo Proyecto
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar proyectos..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            variant={sectorFilter === null ? "default" : "outline"}
            size="sm"
            onClick={() => setSectorFilter(null)}
          >
            Todos
          </Button>
          {sectors.map((sector) => (
            <Button
              key={sector}
              variant={sectorFilter === sector ? "default" : "outline"}
              size="sm"
              onClick={() => setSectorFilter(sector)}
            >
              {sector}
            </Button>
          ))}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="p-6 rounded-lg bg-red-50 border border-red-200 text-center">
          <p className="text-red-700 mb-4">{error}</p>
          <Button variant="outline" onClick={() => { setLoading(true); loadProjects(); }}>
            Reintentar
          </Button>
        </div>
      )}

      {/* Projects Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredProjects.map((project) => (
          <Card
            key={project.id}
            className="hover:shadow-lg transition-shadow cursor-pointer group"
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <span
                    className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium mb-2 ${getProjectStatusColor(
                      project.estado
                    )}`}
                  >
                    {project.estado}
                  </span>
                  <CardTitle className="text-lg group-hover:text-primary transition-colors">
                    {project.nombre}
                  </CardTitle>
                </div>
                <div className="h-10 w-10 rounded-lg bg-slate-100 flex items-center justify-center">
                  <Building2 className="h-5 w-5 text-slate-600" />
                </div>
              </div>
              <p className="text-sm text-muted-foreground line-clamp-2">
                {project.descripcion}
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Progress bar */}
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Progreso</span>
                  <span className="font-medium">
                    {formatPercentage(
                      project.monto_financiado / project.monto_solicitado
                    )}
                  </span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full">
                  <div
                    className="h-full bg-primary rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        (project.monto_financiado / project.monto_solicitado) *
                          100,
                        100
                      )}%`,
                    }}
                  />
                </div>
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>{formatCurrency(project.monto_financiado)}</span>
                  <span>{formatCurrency(project.monto_solicitado)}</span>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-4 pt-2 border-t">
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-green-600" />
                  <div>
                    <p className="text-sm font-semibold">
                      {project.tasa_rendimiento_anual
                        ? formatPercentage(project.tasa_rendimiento_anual)
                        : "N/A"}
                    </p>
                    <p className="text-xs text-muted-foreground">Rendimiento</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-blue-600" />
                  <div>
                    <p className="text-sm font-semibold">
                      {project.plazo_meses} meses
                    </p>
                    <p className="text-xs text-muted-foreground">Plazo</p>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <Button className="flex-1 group-hover:bg-primary/90" asChild>
                  <Link href={`/projects/${project.id}`}>
                    Ver Detalles
                    <ArrowUpRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    openEditModal(project);
                  }}
                  title="Editar proyecto"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeletingProject(project);
                  }}
                  title="Eliminar proyecto"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {filteredProjects.length === 0 && (
        <div className="text-center py-12">
          <Building2 className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">
            No se encontraron proyectos con los filtros seleccionados
          </p>
        </div>
      )}

      {/* Modal de edicion */}
      <Dialog open={!!editingProject} onOpenChange={(open) => !open && setEditingProject(null)}>
        <DialogContent className="sm:max-w-[700px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Editar Proyecto</DialogTitle>
            <DialogDescription>
              Modifica los datos del proyecto. Los campos marcados con * son obligatorios.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {/* Seccion: Informacion Basica */}
            <div className="text-sm font-semibold text-muted-foreground border-b pb-1">Informacion Basica</div>
            <div className="grid gap-2">
              <Label htmlFor="nombre">Nombre *</Label>
              <Input
                id="nombre"
                value={editForm.nombre}
                onChange={(e) => setEditForm({ ...editForm, nombre: e.target.value })}
                placeholder="Nombre del proyecto"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="descripcion">Descripcion</Label>
              <textarea
                id="descripcion"
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={editForm.descripcion}
                onChange={(e) => setEditForm({ ...editForm, descripcion: e.target.value })}
                placeholder="Descripcion del proyecto"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="sector">Sector</Label>
                <Input
                  id="sector"
                  value={editForm.sector}
                  onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })}
                  placeholder="Ej: Tecnologia"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="empresa">Empresa Solicitante</Label>
                <Input
                  id="empresa"
                  value={editForm.empresa_solicitante}
                  onChange={(e) => setEditForm({ ...editForm, empresa_solicitante: e.target.value })}
                  placeholder="Nombre de la empresa"
                />
              </div>
            </div>

            {/* Seccion: Datos Financieros */}
            <div className="text-sm font-semibold text-muted-foreground border-b pb-1 mt-2">Datos Financieros</div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="monto">Monto Solicitado *</Label>
                <Input
                  id="monto"
                  type="number"
                  value={editForm.monto_solicitado}
                  onChange={(e) => setEditForm({ ...editForm, monto_solicitado: parseFloat(e.target.value) || 0 })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="monto_minimo">Monto Minimo Inversion</Label>
                <Input
                  id="monto_minimo"
                  type="number"
                  value={editForm.monto_minimo_inversion}
                  onChange={(e) => setEditForm({ ...editForm, monto_minimo_inversion: parseFloat(e.target.value) || 0 })}
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="plazo">Plazo (meses) *</Label>
                <Input
                  id="plazo"
                  type="number"
                  value={editForm.plazo_meses}
                  onChange={(e) => setEditForm({ ...editForm, plazo_meses: parseInt(e.target.value) || 0 })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="tasa">Tasa Anual (%)</Label>
                <Input
                  id="tasa"
                  type="number"
                  step="0.01"
                  value={(editForm.tasa_rendimiento_anual * 100).toFixed(2)}
                  onChange={(e) => setEditForm({ ...editForm, tasa_rendimiento_anual: (parseFloat(e.target.value) || 0) / 100 })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="rendimiento">Rendimiento Proyectado</Label>
                <Input
                  id="rendimiento"
                  type="number"
                  value={editForm.rendimiento_proyectado}
                  onChange={(e) => setEditForm({ ...editForm, rendimiento_proyectado: parseFloat(e.target.value) || 0 })}
                />
              </div>
            </div>

            {/* Seccion: Fechas */}
            <div className="text-sm font-semibold text-muted-foreground border-b pb-1 mt-2">Fechas Estimadas</div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="fecha_inicio">Fecha Inicio</Label>
                <Input
                  id="fecha_inicio"
                  type="date"
                  value={editForm.fecha_inicio_estimada}
                  onChange={(e) => setEditForm({ ...editForm, fecha_inicio_estimada: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="fecha_fin">Fecha Fin</Label>
                <Input
                  id="fecha_fin"
                  type="date"
                  value={editForm.fecha_fin_estimada}
                  onChange={(e) => setEditForm({ ...editForm, fecha_fin_estimada: e.target.value })}
                />
              </div>
            </div>

            {/* Seccion: Documentacion */}
            <div className="text-sm font-semibold text-muted-foreground border-b pb-1 mt-2">Documentacion</div>
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="documentacion"
                checked={editForm.tiene_documentacion_completa}
                onChange={(e) => setEditForm({ ...editForm, tiene_documentacion_completa: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300"
              />
              <Label htmlFor="documentacion" className="text-sm font-normal">
                Documentacion completa
              </Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingProject(null)}>
              Cancelar
            </Button>
            <Button onClick={handleSaveProject} disabled={saving || !editForm.nombre}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Guardando...
                </>
              ) : (
                "Guardar Cambios"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog de confirmacion para eliminar */}
      <AlertDialog open={!!deletingProject} onOpenChange={(open) => !open && setDeletingProject(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar Proyecto</AlertDialogTitle>
            <AlertDialogDescription>
              ¿Estas seguro de eliminar el proyecto "{deletingProject?.nombre}"?
              Esta accion no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteProject}
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
