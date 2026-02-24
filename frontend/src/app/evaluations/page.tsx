"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Briefcase,
  Search,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { formatCurrency, formatPercentage, getRiskLevelColor } from "@/lib/utils";

interface Evaluation {
  id: string;
  proyecto_nombre: string;
  sector: string;
  monto_solicitado: number;
  van: number;
  tir: number | null;
  roi: number;
  risk_level: string;
  status: "pendiente" | "aprobado" | "rechazado";
  fecha_evaluacion: string;
}

const mockEvaluations: Evaluation[] = [
  {
    id: "1",
    proyecto_nombre: "Torre Corporativa Santa Fe",
    sector: "Inmobiliario",
    monto_solicitado: 25000000,
    van: 5200000,
    tir: 0.19,
    roi: 0.42,
    risk_level: "AA",
    status: "pendiente",
    fecha_evaluacion: "2024-02-15",
  },
  {
    id: "2",
    proyecto_nombre: "Plataforma SaaS Logistica",
    sector: "Tecnologia",
    monto_solicitado: 8000000,
    van: 2100000,
    tir: 0.28,
    roi: 0.56,
    risk_level: "A",
    status: "aprobado",
    fecha_evaluacion: "2024-02-10",
  },
  {
    id: "3",
    proyecto_nombre: "Planta Tratamiento Agua",
    sector: "Infraestructura",
    monto_solicitado: 45000000,
    van: -1500000,
    tir: 0.08,
    roi: 0.12,
    risk_level: "C",
    status: "rechazado",
    fecha_evaluacion: "2024-02-05",
  },
];

const statusConfig = {
  pendiente: { color: "bg-yellow-100 text-yellow-800", icon: Clock, label: "Pendiente" },
  aprobado: { color: "bg-green-100 text-green-800", icon: CheckCircle2, label: "Aprobado" },
  rechazado: { color: "bg-red-100 text-red-800", icon: AlertTriangle, label: "Rechazado" },
};

export default function EvaluationsPage() {
  const [search, setSearch] = useState("");
  const [evaluations] = useState<Evaluation[]>(mockEvaluations);

  const filteredEvaluations = evaluations.filter((e) =>
    e.proyecto_nombre.toLowerCase().includes(search.toLowerCase())
  );

  const pendientes = evaluations.filter((e) => e.status === "pendiente").length;
  const aprobados = evaluations.filter((e) => e.status === "aprobado").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Evaluaciones</h1>
        <p className="text-muted-foreground mt-1">
          Panel de evaluacion financiera de proyectos
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-yellow-100 flex items-center justify-center">
                <Clock className="h-6 w-6 text-yellow-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{pendientes}</p>
                <p className="text-sm text-muted-foreground">Pendientes</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle2 className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{aprobados}</p>
                <p className="text-sm text-muted-foreground">Aprobados</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                <TrendingUp className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{evaluations.length}</p>
                <p className="text-sm text-muted-foreground">Total</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar proyectos..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Evaluations List */}
      <Card>
        <CardHeader>
          <CardTitle>Proyectos en Evaluacion</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {filteredEvaluations.map((evaluation) => {
              const StatusIcon = statusConfig[evaluation.status].icon;
              return (
                <div
                  key={evaluation.id}
                  className="flex items-center justify-between p-4 rounded-lg border hover:bg-slate-50 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold">{evaluation.proyecto_nombre}</h3>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 ${
                          statusConfig[evaluation.status].color
                        }`}
                      >
                        <StatusIcon className="h-3 w-3" />
                        {statusConfig[evaluation.status].label}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${getRiskLevelColor(
                          evaluation.risk_level
                        )}`}
                      >
                        {evaluation.risk_level}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                      <span>{evaluation.sector}</span>
                      <span>|</span>
                      <span>{formatCurrency(evaluation.monto_solicitado)}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-6 text-center mx-4">
                    <div>
                      <p
                        className={`font-semibold ${
                          evaluation.van >= 0 ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {formatCurrency(evaluation.van)}
                      </p>
                      <p className="text-xs text-muted-foreground">VAN</p>
                    </div>
                    <div>
                      <p className="font-semibold">
                        {evaluation.tir ? formatPercentage(evaluation.tir) : "N/A"}
                      </p>
                      <p className="text-xs text-muted-foreground">TIR</p>
                    </div>
                    <div>
                      <p className="font-semibold">{formatPercentage(evaluation.roi)}</p>
                      <p className="text-xs text-muted-foreground">ROI</p>
                    </div>
                  </div>

                  {evaluation.status === "pendiente" && (
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline">
                        Rechazar
                      </Button>
                      <Button size="sm">Aprobar</Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
