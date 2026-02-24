"use client";

import { useState } from "react";
import { useAuthStore } from "@/store/auth-store";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Settings,
  User,
  Shield,
  Bell,
  Key,
  Smartphone,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuthStore();
  const [mfaSetupMode, setMfaSetupMode] = useState(false);

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Configuracion</h1>
        <p className="text-muted-foreground mt-1">
          Administra tu cuenta y preferencias
        </p>
      </div>

      {/* Profile Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Perfil
          </CardTitle>
          <CardDescription>Informacion basica de tu cuenta</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">Email</label>
              <Input value={user?.email || ""} disabled className="mt-1" />
            </div>
            <div>
              <label className="text-sm font-medium">Rol</label>
              <Input value={user?.rol || ""} disabled className="mt-1" />
            </div>
          </div>
          <div className="flex items-center gap-4 pt-2">
            <div className="flex items-center gap-2">
              {user?.email_verified ? (
                <CheckCircle2 className="h-4 w-4 text-green-600" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
              )}
              <span className="text-sm">
                Email {user?.email_verified ? "verificado" : "no verificado"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Security Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Seguridad
          </CardTitle>
          <CardDescription>Opciones de seguridad de tu cuenta</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Password */}
          <div className="flex items-center justify-between p-4 rounded-lg border">
            <div className="flex items-center gap-4">
              <div className="h-10 w-10 rounded-full bg-slate-100 flex items-center justify-center">
                <Key className="h-5 w-5 text-slate-600" />
              </div>
              <div>
                <p className="font-medium">Contrasena</p>
                <p className="text-sm text-muted-foreground">
                  Ultima actualizacion hace 30 dias
                </p>
              </div>
            </div>
            <Button variant="outline">Cambiar</Button>
          </div>

          {/* MFA */}
          <div className="flex items-center justify-between p-4 rounded-lg border">
            <div className="flex items-center gap-4">
              <div
                className={`h-10 w-10 rounded-full flex items-center justify-center ${
                  user?.mfa_enabled ? "bg-green-100" : "bg-yellow-100"
                }`}
              >
                <Smartphone
                  className={`h-5 w-5 ${
                    user?.mfa_enabled ? "text-green-600" : "text-yellow-600"
                  }`}
                />
              </div>
              <div>
                <p className="font-medium">Autenticacion de dos factores (MFA)</p>
                <p className="text-sm text-muted-foreground">
                  {user?.mfa_enabled
                    ? "Proteccion adicional activada"
                    : "Agrega una capa extra de seguridad"}
                </p>
              </div>
            </div>
            {user?.mfa_enabled ? (
              <span className="flex items-center gap-2 text-green-600 text-sm font-medium">
                <CheckCircle2 className="h-4 w-4" />
                Activado
              </span>
            ) : (
              <Button onClick={() => setMfaSetupMode(true)}>Configurar</Button>
            )}
          </div>

          {mfaSetupMode && !user?.mfa_enabled && (
            <Card className="bg-slate-50">
              <CardContent className="p-6">
                <div className="text-center">
                  <Smartphone className="h-12 w-12 mx-auto text-primary mb-4" />
                  <h3 className="font-semibold mb-2">Configurar Google Authenticator</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Escanea el codigo QR con tu app de autenticacion
                  </p>
                  <div className="h-48 w-48 bg-white border mx-auto mb-4 flex items-center justify-center">
                    <span className="text-muted-foreground text-sm">QR Code</span>
                  </div>
                  <div className="max-w-xs mx-auto space-y-3">
                    <Input placeholder="Codigo de 6 digitos" className="text-center" />
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        className="flex-1"
                        onClick={() => setMfaSetupMode(false)}
                      >
                        Cancelar
                      </Button>
                      <Button className="flex-1">Verificar</Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      {/* Notifications Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notificaciones
          </CardTitle>
          <CardDescription>Configura tus preferencias de notificacion</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Inversiones</p>
              <p className="text-sm text-muted-foreground">
                Notificaciones sobre tus inversiones
              </p>
            </div>
            <input type="checkbox" defaultChecked className="h-4 w-4" />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Rendimientos</p>
              <p className="text-sm text-muted-foreground">
                Alertas de pagos y rendimientos
              </p>
            </div>
            <input type="checkbox" defaultChecked className="h-4 w-4" />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Nuevos Proyectos</p>
              <p className="text-sm text-muted-foreground">
                Notificaciones de nuevas oportunidades
              </p>
            </div>
            <input type="checkbox" defaultChecked className="h-4 w-4" />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Marketing</p>
              <p className="text-sm text-muted-foreground">
                Promociones y novedades
              </p>
            </div>
            <input type="checkbox" className="h-4 w-4" />
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-600">Zona de Peligro</CardTitle>
          <CardDescription>Acciones irreversibles</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 rounded-lg border border-red-200 bg-red-50">
            <div>
              <p className="font-medium text-red-800">Eliminar Cuenta</p>
              <p className="text-sm text-red-600">
                Esta accion es permanente y no se puede deshacer
              </p>
            </div>
            <Button variant="outline" className="border-red-300 text-red-600 hover:bg-red-100">
              Eliminar
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
