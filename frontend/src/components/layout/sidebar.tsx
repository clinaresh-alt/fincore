"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Briefcase,
  TrendingUp,
  FileText,
  Settings,
  LogOut,
  Shield,
  Building2,
} from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";

const navigation = [
  {
    name: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
    roles: ["Inversionista", "Admin"],
  },
  {
    name: "Proyectos",
    href: "/projects",
    icon: Building2,
    roles: ["Inversionista", "Analista", "Admin"],
  },
  {
    name: "Mis Inversiones",
    href: "/investments",
    icon: TrendingUp,
    roles: ["Inversionista"],
  },
  {
    name: "Evaluaciones",
    href: "/evaluations",
    icon: Briefcase,
    roles: ["Analista", "Admin"],
  },
  {
    name: "Documentos",
    href: "/documents",
    icon: FileText,
    roles: ["Cliente", "Inversionista", "Admin"],
  },
  {
    name: "Administracion",
    href: "/admin",
    icon: Shield,
    roles: ["Admin"],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  const filteredNav = navigation.filter(
    (item) => !user || item.roles.includes(user.rol)
  );

  return (
    <div className="flex h-full w-64 flex-col bg-slate-900">
      {/* Logo */}
      <div className="flex h-16 items-center px-6 border-b border-slate-700">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-white font-bold text-lg">F</span>
          </div>
          <span className="text-xl font-bold text-white">FinCore</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {filteredNav.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="border-t border-slate-700 p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-10 w-10 rounded-full bg-slate-700 flex items-center justify-center">
            <span className="text-white font-medium">
              {user?.email?.charAt(0).toUpperCase() || "U"}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">
              {user?.email || "Usuario"}
            </p>
            <p className="text-xs text-slate-400">{user?.rol || "Sin rol"}</p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="flex-1 text-slate-300 hover:text-white hover:bg-slate-800"
            asChild
          >
            <Link href="/settings">
              <Settings className="h-4 w-4 mr-2" />
              Config
            </Link>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-slate-300 hover:text-white hover:bg-slate-800"
            onClick={() => logout()}
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
