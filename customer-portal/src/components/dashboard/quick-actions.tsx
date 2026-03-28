"use client";

import Link from "next/link";
import {
  SendHorizontal,
  Wallet,
  Users,
  History,
  CreditCard,
  ArrowDownToLine,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface QuickAction {
  name: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
}

const actions: QuickAction[] = [
  {
    name: "Enviar dinero",
    description: "Nueva remesa",
    href: "/remittances/new",
    icon: SendHorizontal,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
  },
  {
    name: "Comprar crypto",
    description: "USDC, USDT",
    href: "/wallet/buy",
    icon: Wallet,
    color: "text-purple-600",
    bgColor: "bg-purple-100 dark:bg-purple-900/30",
  },
  {
    name: "Beneficiarios",
    description: "Gestionar",
    href: "/beneficiaries",
    icon: Users,
    color: "text-green-600",
    bgColor: "bg-green-100 dark:bg-green-900/30",
  },
  {
    name: "Historial",
    description: "Ver transacciones",
    href: "/remittances",
    icon: History,
    color: "text-amber-600",
    bgColor: "bg-amber-100 dark:bg-amber-900/30",
  },
  {
    name: "Agregar fondos",
    description: "Depositar",
    href: "/wallet/deposit",
    icon: ArrowDownToLine,
    color: "text-emerald-600",
    bgColor: "bg-emerald-100 dark:bg-emerald-900/30",
  },
  {
    name: "Métodos de pago",
    description: "Tarjetas",
    href: "/settings/payment-methods",
    icon: CreditCard,
    color: "text-rose-600",
    bgColor: "bg-rose-100 dark:bg-rose-900/30",
  },
];

export function QuickActions() {
  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
      {actions.map((action) => (
        <Link key={action.name} href={action.href}>
          <div className="flex flex-col items-center p-3 rounded-xl hover:bg-muted/50 transition-colors cursor-pointer group">
            <div
              className={cn(
                "h-12 w-12 rounded-xl flex items-center justify-center mb-2 transition-transform group-hover:scale-105",
                action.bgColor
              )}
            >
              <action.icon className={cn("h-6 w-6", action.color)} />
            </div>
            <p className="text-xs font-medium text-center">{action.name}</p>
            <p className="text-[10px] text-muted-foreground text-center">
              {action.description}
            </p>
          </div>
        </Link>
      ))}
    </div>
  );
}
