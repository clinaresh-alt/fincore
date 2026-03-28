"use client";

import Link from "next/link";
import { SendHorizontal, AlertTriangle, Loader2 } from "lucide-react";
import { useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BalanceCard } from "@/components/dashboard/balance-card";
import { RecentRemittances } from "@/components/dashboard/recent-remittances";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { useRemittances } from "@/features/remittances/hooks/use-remittances";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const { data: remittancesData, isLoading: isLoadingRemittances } = useRemittances({
    pageSize: 5,
  });

  // TODO: Obtener balances reales del backend
  const balanceUSD = 1250.0;
  const balanceMXN = 21250.0;
  const exchangeRate = 17.0;

  const needsKYC = session?.user?.kycStatus !== "approved";

  // Loading state
  if (status === "loading") {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Extraer nombre del email si no hay nombre
  const userName = session?.user?.name || session?.user?.email?.split("@")[0] || "Usuario";

  return (
    <div className="space-y-6">
      {/* Header con saludo */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Hola, {userName}
          </h1>
          <p className="text-muted-foreground">
            {session?.user?.email}
          </p>
        </div>
        <Link href="/remittances/new">
          <Button size="lg" className="hidden md:flex">
            <SendHorizontal className="h-4 w-4 mr-2" />
            Nueva remesa
          </Button>
        </Link>
      </div>

      {/* Alerta de KYC pendiente */}
      {needsKYC && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30">
          <CardContent className="flex items-center gap-4 py-4">
            <div className="h-10 w-10 rounded-full bg-amber-100 dark:bg-amber-900/50 flex items-center justify-center">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-amber-900 dark:text-amber-100">
                Verificación pendiente
              </p>
              <p className="text-sm text-amber-700 dark:text-amber-300">
                Completa tu verificación KYC para enviar remesas y acceder a
                todas las funciones.
              </p>
            </div>
            <Link href="/verify-kyc">
              <Button variant="outline" className="border-amber-300 hover:bg-amber-100">
                Verificar ahora
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Balance Card */}
      <BalanceCard
        balanceUSD={balanceUSD}
        balanceMXN={balanceMXN}
        isLoading={false}
      />

      {/* Tasa de cambio actual */}
      <Card>
        <CardContent className="flex items-center justify-between py-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              Tasa de cambio actual:
            </span>
            <Badge variant="secondary" className="font-mono">
              1 USD = {exchangeRate.toFixed(2)} MXN
            </Badge>
          </div>
          <span className="text-xs text-muted-foreground">
            Actualizado hace 5 min
          </span>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Acciones rápidas</h2>
        <QuickActions />
      </div>

      {/* Recent Remittances */}
      <RecentRemittances
        remittances={remittancesData?.items ?? []}
        isLoading={isLoadingRemittances}
      />

      {/* CTA Mobile */}
      <div className="md:hidden fixed bottom-20 left-4 right-4 z-40">
        <Link href="/remittances/new">
          <Button size="lg" className="w-full shadow-lg">
            <SendHorizontal className="h-5 w-5 mr-2" />
            Enviar dinero
          </Button>
        </Link>
      </div>
    </div>
  );
}
