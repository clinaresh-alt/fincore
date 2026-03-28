"use client";

import { Eye, EyeOff, Plus, ArrowUpRight, ArrowDownLeft } from "lucide-react";
import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";

interface BalanceCardProps {
  balanceUSD: number;
  balanceMXN: number;
  isLoading?: boolean;
}

export function BalanceCard({
  balanceUSD,
  balanceMXN,
  isLoading = false,
}: BalanceCardProps) {
  const [showBalance, setShowBalance] = useState(true);

  if (isLoading) {
    return (
      <Card className="bg-gradient-to-br from-primary to-primary/80 text-primary-foreground">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <Skeleton className="h-4 w-32 bg-primary-foreground/20" />
            <Skeleton className="h-8 w-8 rounded-full bg-primary-foreground/20" />
          </div>
          <Skeleton className="h-10 w-48 bg-primary-foreground/20 mb-2" />
          <Skeleton className="h-4 w-36 bg-primary-foreground/20 mb-6" />
          <div className="flex gap-2">
            <Skeleton className="h-10 flex-1 bg-primary-foreground/20" />
            <Skeleton className="h-10 flex-1 bg-primary-foreground/20" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-gradient-to-br from-primary to-primary/80 text-primary-foreground overflow-hidden relative">
      {/* Decorative elements */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2" />
      <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/5 rounded-full translate-y-1/2 -translate-x-1/2" />

      <CardContent className="p-6 relative">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-primary-foreground/80">Saldo disponible</p>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-primary-foreground/80 hover:text-primary-foreground hover:bg-white/10"
            onClick={() => setShowBalance(!showBalance)}
          >
            {showBalance ? (
              <Eye className="h-4 w-4" />
            ) : (
              <EyeOff className="h-4 w-4" />
            )}
          </Button>
        </div>

        <div className="mb-1">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            {showBalance ? formatCurrency(balanceUSD, "USD") : "••••••"}
          </h2>
        </div>

        <p className="text-sm text-primary-foreground/70 mb-6">
          {showBalance ? (
            <>Equivalente a {formatCurrency(balanceMXN, "MXN")}</>
          ) : (
            "••••••"
          )}
        </p>

        <div className="flex gap-2">
          <Button
            variant="secondary"
            className="flex-1 bg-white/20 hover:bg-white/30 text-primary-foreground border-0"
          >
            <Plus className="h-4 w-4 mr-2" />
            Agregar fondos
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className="bg-white/20 hover:bg-white/30 text-primary-foreground border-0"
            title="Recibir"
          >
            <ArrowDownLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className="bg-white/20 hover:bg-white/30 text-primary-foreground border-0"
            title="Enviar"
          >
            <ArrowUpRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
