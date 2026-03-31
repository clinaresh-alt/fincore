"use client";

import Link from "next/link";
import {
  KeyRound,
  Shield,
  Bell,
  User,
  CreditCard,
  FileText,
  ChevronRight,
} from "lucide-react";

const settingsItems = [
  {
    title: "API Keys",
    description: "Gestiona tus API keys para acceso programático",
    href: "/settings/api-keys",
    icon: KeyRound,
    color: "text-purple-600 bg-purple-100",
  },
  {
    title: "Seguridad",
    description: "2FA, dispositivos, sesiones y whitelist",
    href: "/security",
    icon: Shield,
    color: "text-red-600 bg-red-100",
  },
  {
    title: "Notificaciones",
    description: "Configura alertas por email y push",
    href: "/settings/notifications",
    icon: Bell,
    color: "text-blue-600 bg-blue-100",
  },
  {
    title: "Perfil",
    description: "Información personal y verificación KYC",
    href: "/settings/profile",
    icon: User,
    color: "text-green-600 bg-green-100",
  },
  {
    title: "Métodos de Pago",
    description: "Cuentas bancarias y tarjetas vinculadas",
    href: "/settings/payment-methods",
    icon: CreditCard,
    color: "text-orange-600 bg-orange-100",
  },
  {
    title: "Centro de Impuestos",
    description: "Reportes fiscales y verificación SAT 69-B",
    href: "/settings/tax-center",
    icon: FileText,
    color: "text-teal-600 bg-teal-100",
  },
];

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Configuración</h1>
        <p className="text-gray-600 mt-1">
          Administra tu cuenta y preferencias
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {settingsItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="flex items-start gap-4 p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all group"
          >
            <div className={`p-3 rounded-lg ${item.color}`}>
              <item.icon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-900">{item.title}</h3>
                <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-gray-600 transition-colors" />
              </div>
              <p className="text-sm text-gray-500 mt-1">{item.description}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
