"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Shield,
  Users,
  Building2,
  DollarSign,
  TrendingUp,
  Search,
  MoreVertical,
  UserCheck,
  UserX,
  Settings,
  Bot,
} from "lucide-react";
import Link from "next/link";
import { formatCurrency } from "@/lib/utils";

interface User {
  id: string;
  email: string;
  rol: string;
  status: "activo" | "inactivo" | "bloqueado";
  mfa_enabled: boolean;
  created_at: string;
}

const mockUsers: User[] = [
  { id: "1", email: "admin@fincore.com", rol: "Admin", status: "activo", mfa_enabled: true, created_at: "2024-01-01" },
  { id: "2", email: "analista@fincore.com", rol: "Analista", status: "activo", mfa_enabled: true, created_at: "2024-01-15" },
  { id: "3", email: "inversor1@gmail.com", rol: "Inversionista", status: "activo", mfa_enabled: false, created_at: "2024-02-01" },
  { id: "4", email: "cliente@empresa.com", rol: "Cliente", status: "inactivo", mfa_enabled: false, created_at: "2024-02-10" },
  { id: "5", email: "bloqueado@test.com", rol: "Inversionista", status: "bloqueado", mfa_enabled: false, created_at: "2024-01-20" },
];

const statusColors = {
  activo: "bg-green-100 text-green-800",
  inactivo: "bg-gray-100 text-gray-800",
  bloqueado: "bg-red-100 text-red-800",
};

export default function AdminPage() {
  const [users] = useState<User[]>(mockUsers);
  const [search, setSearch] = useState("");

  const filteredUsers = users.filter((u) =>
    u.email.toLowerCase().includes(search.toLowerCase())
  );

  const totalUsuarios = users.length;
  const usuariosActivos = users.filter((u) => u.status === "activo").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Administracion</h1>
          <p className="text-muted-foreground mt-1">
            Panel de control del sistema
          </p>
        </div>
        <Link href="/admin/settings">
          <Button variant="outline">
            <Settings className="mr-2 h-4 w-4" />
            Configuracion del Sistema
          </Button>
        </Link>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{totalUsuarios}</p>
                <p className="text-sm text-muted-foreground">Usuarios</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <UserCheck className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{usuariosActivos}</p>
                <p className="text-sm text-muted-foreground">Activos</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center">
                <Building2 className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">12</p>
                <p className="text-sm text-muted-foreground">Proyectos</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-amber-100 flex items-center justify-center">
                <DollarSign className="h-6 w-6 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{formatCurrency(85000000)}</p>
                <p className="text-sm text-muted-foreground">Volumen Total</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Users Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Gestion de Usuarios</CardTitle>
          <Button>
            <Users className="mr-2 h-4 w-4" />
            Nuevo Usuario
          </Button>
        </CardHeader>
        <CardContent>
          {/* Search */}
          <div className="relative max-w-md mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Buscar usuarios..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Users Table */}
          <div className="border rounded-lg">
            <table className="w-full">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left p-3 text-sm font-medium text-muted-foreground">Email</th>
                  <th className="text-left p-3 text-sm font-medium text-muted-foreground">Rol</th>
                  <th className="text-left p-3 text-sm font-medium text-muted-foreground">Estado</th>
                  <th className="text-left p-3 text-sm font-medium text-muted-foreground">MFA</th>
                  <th className="text-right p-3 text-sm font-medium text-muted-foreground">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((user) => (
                  <tr key={user.id} className="border-t hover:bg-slate-50">
                    <td className="p-3">
                      <p className="font-medium">{user.email}</p>
                    </td>
                    <td className="p-3">
                      <span className="px-2 py-1 rounded-full text-xs font-medium bg-slate-100">
                        {user.rol}
                      </span>
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${
                          statusColors[user.status]
                        }`}
                      >
                        {user.status}
                      </span>
                    </td>
                    <td className="p-3">
                      {user.mfa_enabled ? (
                        <Shield className="h-4 w-4 text-green-600" />
                      ) : (
                        <span className="text-xs text-muted-foreground">No</span>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <Button variant="ghost" size="sm">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* System Health */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Estado del Sistema</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">API Backend</span>
              <span className="flex items-center gap-2 text-green-600 text-sm">
                <span className="h-2 w-2 rounded-full bg-green-600"></span>
                Operativo
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Base de Datos</span>
              <span className="flex items-center gap-2 text-green-600 text-sm">
                <span className="h-2 w-2 rounded-full bg-green-600"></span>
                Operativo
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Servicio de Correo</span>
              <span className="flex items-center gap-2 text-green-600 text-sm">
                <span className="h-2 w-2 rounded-full bg-green-600"></span>
                Operativo
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Almacenamiento S3</span>
              <span className="flex items-center gap-2 text-yellow-600 text-sm">
                <span className="h-2 w-2 rounded-full bg-yellow-600"></span>
                Configurar
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm flex items-center gap-2">
                <Bot className="h-4 w-4" />
                Inteligencia Artificial
              </span>
              <Link href="/admin/settings">
                <span className="flex items-center gap-2 text-yellow-600 text-sm hover:underline cursor-pointer">
                  <span className="h-2 w-2 rounded-full bg-yellow-600"></span>
                  Configurar
                </span>
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Actividad Reciente</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <div className="h-2 w-2 rounded-full bg-green-600"></div>
              <span className="flex-1">Usuario registrado: inversor1@gmail.com</span>
              <span className="text-muted-foreground">Hace 2h</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <div className="h-2 w-2 rounded-full bg-blue-600"></div>
              <span className="flex-1">Proyecto aprobado: Torre Corporativa</span>
              <span className="text-muted-foreground">Hace 4h</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <div className="h-2 w-2 rounded-full bg-purple-600"></div>
              <span className="flex-1">Inversion realizada: $50,000 MXN</span>
              <span className="text-muted-foreground">Hace 6h</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <div className="h-2 w-2 rounded-full bg-red-600"></div>
              <span className="flex-1">Usuario bloqueado: bloqueado@test.com</span>
              <span className="text-muted-foreground">Hace 1d</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
