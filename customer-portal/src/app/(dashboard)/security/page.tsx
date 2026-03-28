"use client";

import { useState } from "react";
import {
  Shield,
  Smartphone,
  Key,
  Lock,
  Eye,
  EyeOff,
  QrCode,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Check,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { useSession } from "next-auth/react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  useCurrentUser,
  useSetupMFA,
  useEnableMFA,
  useChangePassword,
  type MFASetupResponse,
} from "@/features/security/hooks/use-security";
import { cn } from "@/lib/utils";

export default function SecurityPage() {
  const { data: session } = useSession();
  const { data: user, isLoading } = useCurrentUser();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="h-6 w-6" />
          Seguridad
        </h1>
        <p className="text-muted-foreground">
          Configura la seguridad de tu cuenta
        </p>
      </div>

      {/* Estado de seguridad */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Estado de Seguridad</CardTitle>
          <CardDescription>
            Resumen de la seguridad de tu cuenta
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <SecurityStatusItem
              icon={Lock}
              title="Contraseña"
              status="configured"
              description="Configurada"
            />
            <SecurityStatusItem
              icon={Smartphone}
              title="Autenticación 2FA"
              status={user?.mfa_enabled ? "configured" : "not_configured"}
              description={user?.mfa_enabled ? "Habilitada" : "No configurada"}
            />
            <SecurityStatusItem
              icon={Key}
              title="Último acceso"
              status="info"
              description={
                user?.ultimo_login
                  ? new Date(user.ultimo_login).toLocaleString()
                  : "Nunca"
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Autenticación de dos factores */}
      <MFASection mfaEnabled={user?.mfa_enabled || false} isLoading={isLoading} />

      {/* Cambiar contraseña */}
      <ChangePasswordSection />

      {/* Información de sesión */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Sesión Actual</CardTitle>
          <CardDescription>
            Información sobre tu sesión activa
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">{session?.user?.email}</p>
              <p className="text-sm text-muted-foreground">
                Sesión iniciada
              </p>
            </div>
            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Activa
            </Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Componente de estado de seguridad
interface SecurityStatusItemProps {
  icon: typeof Shield;
  title: string;
  status: "configured" | "not_configured" | "warning" | "info";
  description: string;
}

function SecurityStatusItem({ icon: Icon, title, status, description }: SecurityStatusItemProps) {
  const statusStyles = {
    configured: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    not_configured: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    warning: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    info: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border">
      <div className={cn("h-10 w-10 rounded-full flex items-center justify-center", statusStyles[status])}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

// Sección de MFA
interface MFASectionProps {
  mfaEnabled: boolean;
  isLoading: boolean;
}

function MFASection({ mfaEnabled, isLoading }: MFASectionProps) {
  const [showSetup, setShowSetup] = useState(false);
  const [setupData, setSetupData] = useState<MFASetupResponse | null>(null);
  const [verificationCode, setVerificationCode] = useState("");
  const [copied, setCopied] = useState(false);

  const setupMutation = useSetupMFA();
  const enableMutation = useEnableMFA();

  const handleStartSetup = async () => {
    try {
      const data = await setupMutation.mutateAsync();
      setSetupData(data);
      setShowSetup(true);
    } catch {
      toast.error("Error al configurar 2FA");
    }
  };

  const handleEnableMFA = async () => {
    if (verificationCode.length !== 6) {
      toast.error("El código debe tener 6 dígitos");
      return;
    }

    try {
      await enableMutation.mutateAsync(verificationCode);
      toast.success("Autenticación 2FA habilitada");
      setShowSetup(false);
      setSetupData(null);
      setVerificationCode("");
    } catch {
      toast.error("Código incorrecto");
    }
  };

  const handleCopySecret = async () => {
    if (setupData?.secret) {
      await navigator.clipboard.writeText(setupData.secret);
      setCopied(true);
      toast.success("Clave copiada");
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex items-center justify-center">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Smartphone className="h-5 w-5" />
              Autenticación de Dos Factores (2FA)
            </CardTitle>
            <CardDescription>
              Agrega una capa extra de seguridad a tu cuenta
            </CardDescription>
          </div>
          {mfaEnabled && (
            <Badge className="bg-green-100 text-green-700 border-green-200">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Habilitada
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {mfaEnabled ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-green-50 dark:bg-green-900/20">
              <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5" />
              <div>
                <p className="font-medium text-green-900 dark:text-green-100">
                  Tu cuenta está protegida con 2FA
                </p>
                <p className="text-sm text-green-700 dark:text-green-300">
                  Cada vez que inicies sesión, necesitarás tu código de autenticación.
                </p>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Si necesitas deshabilitar 2FA, contacta al soporte.
            </p>
          </div>
        ) : showSetup && setupData ? (
          <div className="space-y-6">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
              <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
              <div>
                <p className="font-medium text-yellow-900 dark:text-yellow-100">
                  Configura tu aplicación de autenticación
                </p>
                <p className="text-sm text-yellow-700 dark:text-yellow-300">
                  Escanea el código QR con Google Authenticator, Authy u otra app compatible.
                </p>
              </div>
            </div>

            {/* QR Code */}
            <div className="flex flex-col items-center gap-4">
              <div className="p-4 bg-white rounded-lg border">
                <img
                  src={`data:image/png;base64,${setupData.qr_code_base64}`}
                  alt="QR Code para 2FA"
                  className="w-48 h-48"
                />
              </div>

              <div className="text-center">
                <p className="text-sm text-muted-foreground mb-2">
                  O ingresa esta clave manualmente:
                </p>
                <div className="flex items-center gap-2 justify-center">
                  <code className="px-3 py-1.5 bg-muted rounded font-mono text-sm">
                    {setupData.secret}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleCopySecret}
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-green-500" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>

            <Separator />

            {/* Verificación */}
            <div className="space-y-4">
              <Label htmlFor="verification-code">
                Ingresa el código de 6 dígitos de tu app
              </Label>
              <div className="flex gap-2">
                <Input
                  id="verification-code"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  placeholder="000000"
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ""))}
                  className="font-mono text-center text-lg tracking-widest"
                />
                <Button
                  onClick={handleEnableMFA}
                  disabled={verificationCode.length !== 6 || enableMutation.isPending}
                  isLoading={enableMutation.isPending}
                >
                  Verificar y activar
                </Button>
              </div>
            </div>

            <Button
              variant="outline"
              className="w-full"
              onClick={() => {
                setShowSetup(false);
                setSetupData(null);
                setVerificationCode("");
              }}
            >
              Cancelar
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/50">
              <QrCode className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="font-medium">Protege tu cuenta</p>
                <p className="text-sm text-muted-foreground">
                  Usa una aplicación como Google Authenticator o Authy para generar códigos de verificación.
                </p>
              </div>
            </div>
            <Button onClick={handleStartSetup} disabled={setupMutation.isPending}>
              {setupMutation.isPending ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Configurando...
                </>
              ) : (
                <>
                  <Smartphone className="h-4 w-4 mr-2" />
                  Configurar 2FA
                </>
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Sección de cambio de contraseña
function ChangePasswordSection() {
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false,
  });
  const [formData, setFormData] = useState({
    current: "",
    new: "",
    confirm: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const changePasswordMutation = useChangePassword();

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.current) {
      newErrors.current = "Ingresa tu contraseña actual";
    }

    if (!formData.new) {
      newErrors.new = "Ingresa la nueva contraseña";
    } else if (formData.new.length < 8) {
      newErrors.new = "La contraseña debe tener al menos 8 caracteres";
    }

    if (formData.new !== formData.confirm) {
      newErrors.confirm = "Las contraseñas no coinciden";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;

    try {
      await changePasswordMutation.mutateAsync({
        current_password: formData.current,
        new_password: formData.new,
      });
      toast.success("Contraseña actualizada");
      setFormData({ current: "", new: "", confirm: "" });
    } catch {
      toast.error("Error al cambiar contraseña. Verifica tu contraseña actual.");
    }
  };

  const toggleVisibility = (field: keyof typeof showPasswords) => {
    setShowPasswords((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Key className="h-5 w-5" />
          Cambiar Contraseña
        </CardTitle>
        <CardDescription>
          Actualiza tu contraseña regularmente para mayor seguridad
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
          <div className="space-y-2">
            <Label htmlFor="current-password">Contraseña actual</Label>
            <div className="relative">
              <Input
                id="current-password"
                type={showPasswords.current ? "text" : "password"}
                value={formData.current}
                onChange={(e) => setFormData((prev) => ({ ...prev, current: e.target.value }))}
                className={errors.current ? "border-destructive pr-10" : "pr-10"}
              />
              <button
                type="button"
                onClick={() => toggleVisibility("current")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPasswords.current ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.current && <p className="text-xs text-destructive">{errors.current}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-password">Nueva contraseña</Label>
            <div className="relative">
              <Input
                id="new-password"
                type={showPasswords.new ? "text" : "password"}
                value={formData.new}
                onChange={(e) => setFormData((prev) => ({ ...prev, new: e.target.value }))}
                className={errors.new ? "border-destructive pr-10" : "pr-10"}
              />
              <button
                type="button"
                onClick={() => toggleVisibility("new")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPasswords.new ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.new && <p className="text-xs text-destructive">{errors.new}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm-password">Confirmar nueva contraseña</Label>
            <div className="relative">
              <Input
                id="confirm-password"
                type={showPasswords.confirm ? "text" : "password"}
                value={formData.confirm}
                onChange={(e) => setFormData((prev) => ({ ...prev, confirm: e.target.value }))}
                className={errors.confirm ? "border-destructive pr-10" : "pr-10"}
              />
              <button
                type="button"
                onClick={() => toggleVisibility("confirm")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPasswords.confirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {errors.confirm && <p className="text-xs text-destructive">{errors.confirm}</p>}
          </div>

          <Button
            type="submit"
            disabled={changePasswordMutation.isPending}
            isLoading={changePasswordMutation.isPending}
          >
            Cambiar contraseña
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
