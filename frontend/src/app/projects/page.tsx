"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { projectsAPI } from "@/lib/api-client";
import { Project } from "@/types";
import { formatCurrency, formatPercentage, getProjectStatusColor } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Building2,
  Search,
  Filter,
  ArrowUpRight,
  Clock,
  TrendingUp,
  Plus,
} from "lucide-react";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState<string | null>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      const data = await projectsAPI.list();
      setProjects(data);
    } catch (error) {
      console.error("Error loading projects:", error);
      // Mock data para demo
      setProjects([
        {
          id: "1",
          nombre: "Plaza Comercial Reforma",
          descripcion: "Desarrollo de centro comercial premium en Av. Reforma",
          sector: "Inmobiliario",
          monto_solicitado: 15000000,
          monto_financiado: 9000000,
          plazo_meses: 36,
          estado: "Financiando",
          tasa_rendimiento_anual: 0.18,
          created_at: "2024-01-15",
        },
        {
          id: "2",
          nombre: "Fintech Pagos Digitales",
          descripcion: "Plataforma de pagos instantaneos para comercios",
          sector: "Tecnologia",
          monto_solicitado: 5000000,
          monto_financiado: 3500000,
          plazo_meses: 24,
          estado: "Financiando",
          tasa_rendimiento_anual: 0.22,
          created_at: "2024-02-01",
        },
        {
          id: "3",
          nombre: "Parque Solar Sonora",
          descripcion: "Instalacion de 50MW de energia solar fotovoltaica",
          sector: "Energia",
          monto_solicitado: 25000000,
          monto_financiado: 25000000,
          plazo_meses: 60,
          estado: "Financiado",
          tasa_rendimiento_anual: 0.14,
          created_at: "2023-11-20",
        },
        {
          id: "4",
          nombre: "Agrotech Vertical Farms",
          descripcion: "Granjas verticales con tecnologia hidroponica",
          sector: "Agrotech",
          monto_solicitado: 8000000,
          monto_financiado: 2400000,
          plazo_meses: 30,
          estado: "Aprobado",
          tasa_rendimiento_anual: 0.16,
          created_at: "2024-02-10",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const sectors = [...new Set(projects.map((p) => p.sector))];

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

              {/* Action */}
              <Button className="w-full group-hover:bg-primary/90" asChild>
                <Link href={`/projects/${project.id}`}>
                  Ver Detalles
                  <ArrowUpRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
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
    </div>
  );
}
