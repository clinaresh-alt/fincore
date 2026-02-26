"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { investorAPI } from "@/lib/api-client";
import { Investment } from "@/types";
import { formatCurrency, formatPercentage, formatDate } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  TrendingUp,
  Calendar,
  ArrowUpRight,
  Wallet,
  PiggyBank,
} from "lucide-react";

const statusColors: Record<string, string> = {
  Pendiente: "text-yellow-600 bg-yellow-100",
  Activa: "text-green-600 bg-green-100",
  "En Rendimiento": "text-blue-600 bg-blue-100",
  Liquidada: "text-purple-600 bg-purple-100",
  Cancelada: "text-red-600 bg-red-100",
};

export default function InvestmentsPage() {
  const [investments, setInvestments] = useState<Investment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadInvestments();
  }, []);

  const loadInvestments = async () => {
    try {
      const data = await investorAPI.listInvestments();
      setInvestments(data || []);
    } catch (error) {
      console.error("Error loading investments:", error);
      // Sin datos - mostrar estado vacío
      setInvestments([]);
    } finally {
      setLoading(false);
    }
  };

  const totalInvertido = investments.reduce(
    (sum, inv) => sum + inv.monto_invertido,
    0
  );
  const totalRendimiento = investments.reduce(
    (sum, inv) => sum + inv.monto_rendimiento_acumulado,
    0
  );

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
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Mis Inversiones</h1>
        <p className="text-muted-foreground mt-1">
          Seguimiento de tu portafolio de inversiones
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                <Wallet className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Invertido</p>
                <p className="text-2xl font-bold">
                  {formatCurrency(totalInvertido)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <TrendingUp className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Rendimiento Acumulado
                </p>
                <p className="text-2xl font-bold text-green-600">
                  +{formatCurrency(totalRendimiento)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center">
                <PiggyBank className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">ROI Promedio</p>
                <p className="text-2xl font-bold text-purple-600">
                  {totalInvertido > 0
                    ? formatPercentage(totalRendimiento / totalInvertido)
                    : "0%"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Investments List */}
      <Card>
        <CardHeader>
          <CardTitle>Detalle de Inversiones</CardTitle>
        </CardHeader>
        <CardContent>
          {investments.length > 0 ? (
            <div className="space-y-4">
              {investments.map((investment) => (
                <div
                  key={investment.id}
                  className="flex items-center justify-between p-4 rounded-lg border hover:bg-slate-50 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold">
                        {investment.proyecto_nombre}
                      </h3>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          statusColors[investment.estado] || "bg-gray-100"
                        }`}
                      >
                        {investment.estado}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-4 w-4" />
                        {formatDate(investment.fecha_inversion)}
                      </span>
                      {investment.porcentaje_participacion && (
                        <span>
                          {formatPercentage(investment.porcentaje_participacion)}{" "}
                          participacion
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="text-right mr-4">
                    <p className="font-semibold">
                      {formatCurrency(investment.monto_invertido)}
                    </p>
                    <p className="text-sm text-green-600">
                      +{formatCurrency(investment.monto_rendimiento_acumulado)}
                    </p>
                  </div>

                  <Button variant="ghost" size="sm" asChild>
                    <Link href={`/investments/${investment.id}`}>
                      <ArrowUpRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <Wallet className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
              <p className="text-muted-foreground">
                Aun no tienes inversiones
              </p>
              <Button className="mt-4" asChild>
                <Link href="/projects">Explorar Proyectos</Link>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
