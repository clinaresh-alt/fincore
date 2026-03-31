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
  Monitor,
  Globe,
  Trash2,
  ShieldCheck,
  ShieldX,
  LogOut,
  Snowflake,
  Fish,
  KeyRound,
  MapPin,
  Clock,
  AlertCircle,
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  useCurrentUser,
  useSetupMFA,
  useEnableMFA,
  useChangePassword,
  useDevices,
  useUpdateDevice,
  useDeleteDevice,
  useSessions,
  useRevokeSession,
  useSecuritySummary,
  useFreezeAccount,
  useFreezeStatus,
  useAntiPhishing,
  useSetupAntiPhishing,
  useBackupCodesStatus,
  useGenerateBackupCodes,
  type MFASetupResponse,
  type Device,
  type Session,
} from "@/features/security/hooks/use-security";
import { cn } from "@/lib/utils";

export default function SecurityPage() {
  const { data: session } = useSession();
  const { data: user, isLoading } = useCurrentUser();
  const { data: securitySummary } = useSecuritySummary();

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

      {/* Score de seguridad */}
      {securitySummary && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Nivel de Seguridad</CardTitle>
            <CardDescription>
              Tu puntuación de seguridad actual
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-6">
              <div className="relative w-24 h-24">
                <svg className="w-24 h-24 transform -rotate-90">
                  <circle
                    cx="48"
                    cy="48"
                    r="40"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="none"
                    className="text-muted"
                  />
                  <circle
                    cx="48"
                    cy="48"
                    r="40"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="none"
                    strokeDasharray={`${(securitySummary.security_score / 100) * 251.2} 251.2`}
                    className={cn(
                      securitySummary.security_score >= 80 ? "text-green-500" :
                      securitySummary.security_score >= 60 ? "text-yellow-500" :
                      "text-red-500"
                    )}
                  />
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-2xl font-bold">
                  {securitySummary.security_score}
                </span>
              </div>
              <div className="flex-1">
                <p className={cn(
                  "font-semibold text-lg",
                  securitySummary.security_score >= 80 ? "text-green-600" :
                  securitySummary.security_score >= 60 ? "text-yellow-600" :
                  "text-red-600"
                )}>
                  {securitySummary.security_score >= 80 ? "Excelente" :
                   securitySummary.security_score >= 60 ? "Bueno" :
                   "Necesita mejoras"}
                </p>
                {securitySummary.recommendations.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {securitySummary.recommendations.slice(0, 3).map((rec, idx) => (
                      <li key={idx} className="text-sm text-muted-foreground flex items-center gap-2">
                        <AlertCircle className="h-3 w-3 text-yellow-500" />
                        {rec}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Estado de seguridad */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Estado de Seguridad</CardTitle>
          <CardDescription>
            Resumen de la seguridad de tu cuenta
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
              icon={Monitor}
              title="Dispositivos"
              status="info"
              description={`${securitySummary?.trusted_devices || 0} de confianza`}
            />
            <SecurityStatusItem
              icon={Globe}
              title="Sesiones activas"
              status="info"
              description={`${securitySummary?.active_sessions || 1} activas`}
            />
          </div>
        </CardContent>
      </Card>

      {/* Autenticación de dos factores */}
      <MFASection mfaEnabled={user?.mfa_enabled || false} isLoading={isLoading} />

      {/* Códigos de respaldo MFA */}
      {user?.mfa_enabled && <BackupCodesSection />}

      {/* Anti-Phishing */}
      <AntiPhishingSection />

      {/* Dispositivos */}
      <DevicesSection />

      {/* Sesiones activas */}
      <SessionsSection />

      {/* Cambiar contraseña */}
      <ChangePasswordSection />

      {/* Congelamiento de cuenta */}
      <AccountFreezeSection />
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
                >
                  {enableMutation.isPending ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    "Verificar y activar"
                  )}
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

// Sección de códigos de respaldo
function BackupCodesSection() {
  const [showCodes, setShowCodes] = useState(false);
  const [generatedCodes, setGeneratedCodes] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const { data: status, isLoading } = useBackupCodesStatus();
  const generateMutation = useGenerateBackupCodes();

  const handleGenerateCodes = async () => {
    try {
      const response = await generateMutation.mutateAsync();
      setGeneratedCodes(response.codes);
      setShowCodes(true);
      toast.success("Códigos de respaldo generados");
    } catch {
      toast.error("Error al generar códigos");
    }
  };

  const handleCopyCodes = async () => {
    await navigator.clipboard.writeText(generatedCodes.join("\n"));
    setCopied(true);
    toast.success("Códigos copiados");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <KeyRound className="h-5 w-5" />
          Códigos de Respaldo
        </CardTitle>
        <CardDescription>
          Códigos de un solo uso para acceder si pierdes tu dispositivo 2FA
        </CardDescription>
      </CardHeader>
      <CardContent>
        {showCodes && generatedCodes.length > 0 ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
              <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
              <div>
                <p className="font-medium text-yellow-900 dark:text-yellow-100">
                  Guarda estos códigos en un lugar seguro
                </p>
                <p className="text-sm text-yellow-700 dark:text-yellow-300">
                  Cada código solo puede usarse una vez. No los compartas.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 p-4 bg-muted rounded-lg">
              {generatedCodes.map((code, idx) => (
                <code key={idx} className="font-mono text-sm p-2 bg-background rounded text-center">
                  {code}
                </code>
              ))}
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={handleCopyCodes}>
                {copied ? (
                  <Check className="h-4 w-4 mr-2 text-green-500" />
                ) : (
                  <Copy className="h-4 w-4 mr-2" />
                )}
                Copiar todos
              </Button>
              <Button variant="outline" onClick={() => setShowCodes(false)}>
                Cerrar
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {status && (
              <div className="flex items-center gap-4 p-4 rounded-lg bg-muted/50">
                <div className="text-center">
                  <p className="text-2xl font-bold">{status.remaining_codes}</p>
                  <p className="text-xs text-muted-foreground">Disponibles</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">{status.used_codes}</p>
                  <p className="text-xs text-muted-foreground">Usados</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold">{status.total_codes}</p>
                  <p className="text-xs text-muted-foreground">Total</p>
                </div>
              </div>
            )}

            {(status?.remaining_codes || 0) < 3 && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5" />
                <p className="text-sm text-yellow-700 dark:text-yellow-300">
                  Te quedan pocos códigos. Genera nuevos pronto.
                </p>
              </div>
            )}

            <Button onClick={handleGenerateCodes} disabled={generateMutation.isPending}>
              {generateMutation.isPending ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <KeyRound className="h-4 w-4 mr-2" />
              )}
              {status?.total_codes ? "Regenerar códigos" : "Generar códigos"}
            </Button>

            {status?.total_codes ? (
              <p className="text-xs text-muted-foreground">
                Al regenerar, los códigos anteriores quedarán inválidos.
              </p>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Sección Anti-Phishing
function AntiPhishingSection() {
  const [phrase, setPhrase] = useState("");
  const [hint, setHint] = useState("");

  const { data: antiPhishing, isLoading } = useAntiPhishing();
  const setupMutation = useSetupAntiPhishing();

  const handleSetup = async () => {
    if (!phrase || phrase.length < 5) {
      toast.error("La frase debe tener al menos 5 caracteres");
      return;
    }

    try {
      await setupMutation.mutateAsync({ phrase, phrase_hint: hint || undefined });
      toast.success("Frase anti-phishing configurada");
      setPhrase("");
      setHint("");
    } catch {
      toast.error("Error al configurar frase");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Fish className="h-5 w-5" />
          Protección Anti-Phishing
        </CardTitle>
        <CardDescription>
          Una frase secreta que solo tú conoces para verificar que estás en el sitio real
        </CardDescription>
      </CardHeader>
      <CardContent>
        {antiPhishing?.is_configured ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-green-50 dark:bg-green-900/20">
              <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5" />
              <div>
                <p className="font-medium text-green-900 dark:text-green-100">
                  Frase anti-phishing configurada
                </p>
                <p className="text-sm text-green-700 dark:text-green-300">
                  Busca tu frase secreta en cada correo que te enviemos.
                </p>
                {antiPhishing.phrase_hint && (
                  <p className="text-sm mt-2">
                    <span className="font-medium">Pista:</span> {antiPhishing.phrase_hint}
                  </p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-w-md">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/50">
              <Fish className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="font-medium">Protégete del phishing</p>
                <p className="text-sm text-muted-foreground">
                  Tu frase aparecerá en todos nuestros correos legítimos.
                  Si no la ves, el correo es falso.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="anti-phishing-phrase">Tu frase secreta</Label>
              <Input
                id="anti-phishing-phrase"
                type="text"
                placeholder="Ej: Mi gato se llama Michi"
                value={phrase}
                onChange={(e) => setPhrase(e.target.value)}
                maxLength={100}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="anti-phishing-hint">Pista (opcional)</Label>
              <Input
                id="anti-phishing-hint"
                type="text"
                placeholder="Ej: Nombre de mascota"
                value={hint}
                onChange={(e) => setHint(e.target.value)}
                maxLength={50}
              />
              <p className="text-xs text-muted-foreground">
                La pista te ayudará a recordar tu frase
              </p>
            </div>

            <Button onClick={handleSetup} disabled={setupMutation.isPending || !phrase}>
              {setupMutation.isPending ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Fish className="h-4 w-4 mr-2" />
              )}
              Guardar frase
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Sección de Dispositivos
function DevicesSection() {
  const { data: devicesData, isLoading } = useDevices();
  const updateMutation = useUpdateDevice();
  const deleteMutation = useDeleteDevice();

  const handleTrustDevice = async (deviceId: string) => {
    try {
      await updateMutation.mutateAsync({ deviceId, data: { status: "trusted" } });
      toast.success("Dispositivo marcado como confiable");
    } catch {
      toast.error("Error al actualizar dispositivo");
    }
  };

  const handleBlockDevice = async (deviceId: string) => {
    try {
      await updateMutation.mutateAsync({ deviceId, data: { status: "blocked" } });
      toast.success("Dispositivo bloqueado");
    } catch {
      toast.error("Error al bloquear dispositivo");
    }
  };

  const handleDeleteDevice = async (deviceId: string) => {
    try {
      await deleteMutation.mutateAsync(deviceId);
      toast.success("Dispositivo eliminado");
    } catch {
      toast.error("Error al eliminar dispositivo");
    }
  };

  const getDeviceIcon = (deviceType: string | null) => {
    if (deviceType === "mobile") return <Smartphone className="h-5 w-5" />;
    if (deviceType === "tablet") return <Monitor className="h-5 w-5" />;
    return <Monitor className="h-5 w-5" />;
  };

  const getStatusBadge = (device: Device) => {
    if (device.is_current) {
      return <Badge className="bg-blue-100 text-blue-700">Actual</Badge>;
    }
    switch (device.status) {
      case "trusted":
        return <Badge className="bg-green-100 text-green-700">Confiable</Badge>;
      case "blocked":
        return <Badge variant="destructive">Bloqueado</Badge>;
      case "suspicious":
        return <Badge className="bg-yellow-100 text-yellow-700">Sospechoso</Badge>;
      default:
        return <Badge variant="outline">Desconocido</Badge>;
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
        <CardTitle className="text-lg flex items-center gap-2">
          <Monitor className="h-5 w-5" />
          Dispositivos Registrados
        </CardTitle>
        <CardDescription>
          Dispositivos que han accedido a tu cuenta
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {devicesData?.devices && devicesData.devices.length > 0 ? (
            devicesData.devices.map((device) => (
              <div
                key={device.id}
                className={cn(
                  "flex items-center justify-between p-4 rounded-lg border",
                  device.is_current && "border-blue-200 bg-blue-50/50 dark:bg-blue-900/10",
                  device.status === "blocked" && "border-red-200 bg-red-50/50 dark:bg-red-900/10"
                )}
              >
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "h-12 w-12 rounded-full flex items-center justify-center",
                    device.is_current ? "bg-blue-100 text-blue-600" :
                    device.status === "trusted" ? "bg-green-100 text-green-600" :
                    device.status === "blocked" ? "bg-red-100 text-red-600" :
                    "bg-muted text-muted-foreground"
                  )}>
                    {getDeviceIcon(device.device_type)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium">
                        {device.device_name || `${device.browser_name || "Navegador"} en ${device.os_name || "Sistema"}`}
                      </p>
                      {getStatusBadge(device)}
                      {device.is_vpn && (
                        <Badge variant="outline" className="text-yellow-600">VPN</Badge>
                      )}
                      {device.is_tor && (
                        <Badge variant="destructive">TOR</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground mt-1">
                      {device.last_city && device.last_country && (
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" />
                          {device.last_city}, {device.last_country}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(device.last_seen_at).toLocaleDateString()}
                      </span>
                      {device.last_ip && (
                        <span className="text-xs">IP: {device.last_ip}</span>
                      )}
                    </div>
                    {device.risk_score > 30 && (
                      <p className="text-xs text-yellow-600 mt-1">
                        Riesgo: {device.risk_score}/100
                      </p>
                    )}
                  </div>
                </div>

                {!device.is_current && (
                  <div className="flex items-center gap-2">
                    {device.status !== "trusted" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTrustDevice(device.id)}
                        disabled={updateMutation.isPending}
                      >
                        <ShieldCheck className="h-4 w-4 mr-1" />
                        Confiar
                      </Button>
                    )}
                    {device.status !== "blocked" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-yellow-600"
                        onClick={() => handleBlockDevice(device.id)}
                        disabled={updateMutation.isPending}
                      >
                        <ShieldX className="h-4 w-4 mr-1" />
                        Bloquear
                      </Button>
                    )}
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="icon" className="text-destructive">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Eliminar dispositivo</AlertDialogTitle>
                          <AlertDialogDescription>
                            Se eliminarán todas las sesiones de este dispositivo. Esta acción no se puede deshacer.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancelar</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => handleDeleteDevice(device.id)}
                            className="bg-destructive text-destructive-foreground"
                          >
                            Eliminar
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Monitor className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay dispositivos registrados</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// Sección de Sesiones
function SessionsSection() {
  const { data: sessionsData, isLoading } = useSessions();
  const revokeMutation = useRevokeSession();

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await revokeMutation.mutateAsync({ session_id: sessionId });
      toast.success("Sesión cerrada");
    } catch {
      toast.error("Error al cerrar sesión");
    }
  };

  const handleRevokeAllSessions = async () => {
    try {
      await revokeMutation.mutateAsync({ revoke_all: true });
      toast.success("Todas las demás sesiones cerradas");
    } catch {
      toast.error("Error al cerrar sesiones");
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

  const otherSessions = sessionsData?.sessions.filter(s => !s.is_current) || [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Globe className="h-5 w-5" />
              Sesiones Activas
            </CardTitle>
            <CardDescription>
              Sesiones iniciadas en diferentes dispositivos
            </CardDescription>
          </div>
          {otherSessions.length > 0 && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm" className="text-destructive">
                  <LogOut className="h-4 w-4 mr-2" />
                  Cerrar todas
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Cerrar todas las sesiones</AlertDialogTitle>
                  <AlertDialogDescription>
                    Se cerrarán todas las sesiones excepto la actual. Tendrás que iniciar sesión de nuevo en esos dispositivos.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleRevokeAllSessions}
                    className="bg-destructive text-destructive-foreground"
                  >
                    Cerrar todas
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {sessionsData?.sessions && sessionsData.sessions.length > 0 ? (
            sessionsData.sessions.map((session) => (
              <div
                key={session.id}
                className={cn(
                  "flex items-center justify-between p-4 rounded-lg border",
                  session.is_current && "border-green-200 bg-green-50/50 dark:bg-green-900/10"
                )}
              >
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "h-10 w-10 rounded-full flex items-center justify-center",
                    session.is_current ? "bg-green-100 text-green-600" : "bg-muted text-muted-foreground"
                  )}>
                    <Globe className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium">
                        {session.device_name || "Sesión"}
                      </p>
                      {session.is_current && (
                        <Badge className="bg-green-100 text-green-700">
                          <CheckCircle2 className="h-3 w-3 mr-1" />
                          Actual
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                      {session.city && session.country && (
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" />
                          {session.city}, {session.country}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(session.last_activity_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>

                {!session.is_current && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={() => handleRevokeSession(session.id)}
                    disabled={revokeMutation.isPending}
                  >
                    <LogOut className="h-4 w-4 mr-1" />
                    Cerrar
                  </Button>
                )}
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Globe className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay sesiones activas</p>
            </div>
          )}
        </div>
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
    } else if (formData.new.length < 12) {
      newErrors.new = "La contraseña debe tener al menos 12 caracteres";
    } else if (!/[A-Z]/.test(formData.new)) {
      newErrors.new = "Debe incluir al menos una mayúscula";
    } else if (!/[a-z]/.test(formData.new)) {
      newErrors.new = "Debe incluir al menos una minúscula";
    } else if (!/[0-9]/.test(formData.new)) {
      newErrors.new = "Debe incluir al menos un número";
    } else if (!/[!@#$%^&*(),.?":{}|<>]/.test(formData.new)) {
      newErrors.new = "Debe incluir al menos un símbolo especial";
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
            <p className="text-xs text-muted-foreground">
              Mínimo 12 caracteres, con mayúscula, minúscula, número y símbolo.
            </p>
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
          >
            {changePasswordMutation.isPending ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : null}
            Cambiar contraseña
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

// Sección de congelamiento de cuenta
function AccountFreezeSection() {
  const [reason, setReason] = useState("");
  const { data: freezeStatus, isLoading } = useFreezeStatus();
  const freezeMutation = useFreezeAccount();

  const handleFreeze = async () => {
    try {
      await freezeMutation.mutateAsync({ reason: reason || undefined });
      toast.success("Cuenta congelada. Contacta a soporte para descongelarla.");
      setReason("");
    } catch {
      toast.error("Error al congelar cuenta");
    }
  };

  if (isLoading) {
    return null;
  }

  return (
    <Card className="border-destructive/50">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2 text-destructive">
          <Snowflake className="h-5 w-5" />
          Congelar Cuenta
        </CardTitle>
        <CardDescription>
          Bloquea temporalmente todas las operaciones de tu cuenta
        </CardDescription>
      </CardHeader>
      <CardContent>
        {freezeStatus?.is_frozen ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-blue-50 dark:bg-blue-900/20">
              <Snowflake className="h-5 w-5 text-blue-600 mt-0.5" />
              <div>
                <p className="font-medium text-blue-900 dark:text-blue-100">
                  Tu cuenta está congelada
                </p>
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  No se pueden realizar retiros ni operaciones sensibles.
                  Contacta a soporte para descongelar tu cuenta.
                </p>
                {freezeStatus.frozen_at && (
                  <p className="text-xs mt-2">
                    Congelada el: {new Date(freezeStatus.frozen_at).toLocaleString()}
                  </p>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-w-md">
            <div className="flex items-start gap-3 p-4 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
              <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
              <div>
                <p className="font-medium text-yellow-900 dark:text-yellow-100">
                  Acción de emergencia
                </p>
                <p className="text-sm text-yellow-700 dark:text-yellow-300">
                  Usa esta opción si sospechas que tu cuenta fue comprometida.
                  Todas las operaciones se bloquearán hasta que contactes a soporte.
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="freeze-reason">Razón (opcional)</Label>
              <Input
                id="freeze-reason"
                type="text"
                placeholder="Ej: Sospecho acceso no autorizado"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={200}
              />
            </div>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <Snowflake className="h-4 w-4 mr-2" />
                  Congelar mi cuenta
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Congelar cuenta</AlertDialogTitle>
                  <AlertDialogDescription>
                    Esta acción bloqueará todos los retiros y operaciones sensibles.
                    Para descongelar la cuenta, necesitarás contactar a soporte y verificar tu identidad.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleFreeze}
                    className="bg-destructive text-destructive-foreground"
                  >
                    Confirmar congelamiento
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
