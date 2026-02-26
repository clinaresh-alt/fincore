"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { apiClient } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Settings,
  Bot,
  Key,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Eye,
  EyeOff,
  RefreshCw,
  Shield,
  Database,
  ArrowLeft,
} from "lucide-react";

interface SystemStatus {
  version: string;
  environment: string;
  database_connected: boolean;
  ai_integration: {
    anthropic_configured: boolean;
    anthropic_valid: boolean;
    ai_analysis_enabled: boolean;
    error_message: string | null;
  };
  total_configs: number;
}

interface ConfigItem {
  key: string;
  value: string | null;
  category: string;
  description: string | null;
  is_encrypted: boolean;
  is_active: boolean;
  updated_at: string | null;
}

export default function AdminSettingsPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [configs, setConfigs] = useState<ConfigItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form states
  const [anthropicKey, setAnthropicKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);

  // Check admin role
  useEffect(() => {
    if (user && user.rol !== "Admin") {
      router.push("/dashboard");
    }
  }, [user, router]);

  // Load system status and configs
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [statusRes, configsRes] = await Promise.all([
        apiClient.get("/admin/status"),
        apiClient.get("/admin/config/"),
      ]);

      setStatus(statusRes.data);
      setConfigs(configsRes.data);

      // Set form values from configs
      const aiConfig = configsRes.data.find((c: ConfigItem) => c.key === "ai_analysis_enabled");
      setAiEnabled(aiConfig?.value === "true");

    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("No tienes permisos para acceder a esta pagina");
      } else {
        setError(err.response?.data?.detail || "Error cargando configuracion");
      }
    } finally {
      setLoading(false);
    }
  };

  const validateKey = async () => {
    if (!anthropicKey.trim()) {
      setError("Ingresa una API key");
      return;
    }

    setValidating(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await apiClient.post("/admin/config/anthropic/validate", {
        value: anthropicKey,
      });

      if (response.data.valid) {
        setSuccess("API key valida. Puedes guardarla.");
      } else {
        setError(response.data.error || "API key invalida");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error validando API key");
    } finally {
      setValidating(false);
    }
  };

  const saveAnthropicKey = async (skipValidation: boolean = false) => {
    if (!anthropicKey.trim()) {
      setError("Ingresa una API key");
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await apiClient.put("/admin/config/anthropic_api_key", {
        value: anthropicKey,
        skip_validation: skipValidation,
      });

      setSuccess(skipValidation
        ? "API key guardada (sin validar). Verifica que funcione correctamente."
        : "API key guardada y validada correctamente"
      );
      setAnthropicKey("");
      loadData(); // Reload to get updated status

    } catch (err: any) {
      setError(err.response?.data?.detail || "Error guardando API key");
    } finally {
      setSaving(false);
    }
  };

  const toggleAiAnalysis = async () => {
    setSaving(true);
    setError(null);

    try {
      await apiClient.put("/admin/config/ai_analysis_enabled", {
        value: (!aiEnabled).toString(),
      });

      setAiEnabled(!aiEnabled);
      setSuccess(`Analisis IA ${!aiEnabled ? "habilitado" : "deshabilitado"}`);

    } catch (err: any) {
      setError(err.response?.data?.detail || "Error actualizando configuracion");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-3 text-muted-foreground">Cargando configuracion...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Configuracion del Sistema</h1>
          <p className="text-muted-foreground mt-1">
            Administra integraciones y configuraciones avanzadas
          </p>
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200">
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-600" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {success && (
        <div className="p-4 rounded-lg bg-green-50 border border-green-200">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <p className="text-sm text-green-700">{success}</p>
          </div>
        </div>
      )}

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Estado del Sistema
          </CardTitle>
          <CardDescription>Estado actual de los servicios</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg border bg-slate-50">
              <p className="text-xs text-muted-foreground">Version</p>
              <p className="text-lg font-semibold">{status?.version || "—"}</p>
            </div>
            <div className="p-4 rounded-lg border bg-slate-50">
              <p className="text-xs text-muted-foreground">Entorno</p>
              <p className="text-lg font-semibold capitalize">{status?.environment || "—"}</p>
            </div>
            <div className="p-4 rounded-lg border bg-slate-50">
              <p className="text-xs text-muted-foreground">Base de Datos</p>
              <div className="flex items-center gap-2 mt-1">
                {status?.database_connected ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-600" />
                )}
                <span className="font-medium">
                  {status?.database_connected ? "Conectada" : "Error"}
                </span>
              </div>
            </div>
            <div className="p-4 rounded-lg border bg-slate-50">
              <p className="text-xs text-muted-foreground">Configuraciones</p>
              <p className="text-lg font-semibold">{status?.total_configs || 0}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* AI Integration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Integracion de IA (Anthropic Claude)
          </CardTitle>
          <CardDescription>
            Configura la API de Anthropic para analisis de documentos con inteligencia artificial
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Current Status */}
          <div className="flex items-center justify-between p-4 rounded-lg border">
            <div className="flex items-center gap-4">
              <div
                className={`h-12 w-12 rounded-full flex items-center justify-center ${
                  status?.ai_integration.anthropic_valid
                    ? "bg-green-100"
                    : status?.ai_integration.anthropic_configured
                    ? "bg-yellow-100"
                    : "bg-slate-100"
                }`}
              >
                <Bot
                  className={`h-6 w-6 ${
                    status?.ai_integration.anthropic_valid
                      ? "text-green-600"
                      : status?.ai_integration.anthropic_configured
                      ? "text-yellow-600"
                      : "text-slate-400"
                  }`}
                />
              </div>
              <div>
                <p className="font-medium">Estado de la Integracion</p>
                <p className="text-sm text-muted-foreground">
                  {status?.ai_integration.anthropic_valid
                    ? "API key configurada y validada"
                    : status?.ai_integration.anthropic_configured
                    ? `Error: ${status?.ai_integration.error_message || "API key invalida"}`
                    : "No configurada"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {status?.ai_integration.anthropic_valid ? (
                <span className="flex items-center gap-2 px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                  <CheckCircle2 className="h-4 w-4" />
                  Activa
                </span>
              ) : status?.ai_integration.anthropic_configured ? (
                <span className="flex items-center gap-2 px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-sm font-medium">
                  <AlertTriangle className="h-4 w-4" />
                  Error
                </span>
              ) : (
                <span className="flex items-center gap-2 px-3 py-1 bg-slate-100 text-slate-600 rounded-full text-sm font-medium">
                  <XCircle className="h-4 w-4" />
                  No configurada
                </span>
              )}
            </div>
          </div>

          {/* API Key Input */}
          <div className="p-4 rounded-lg border bg-slate-50">
            <label className="text-sm font-medium flex items-center gap-2 mb-3">
              <Key className="h-4 w-4" />
              API Key de Anthropic
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  type={showKey ? "text" : "password"}
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  placeholder="sk-ant-api03-..."
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <Button
                variant="outline"
                onClick={validateKey}
                disabled={validating || !anthropicKey.trim()}
              >
                {validating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4 mr-2" />
                    Validar
                  </>
                )}
              </Button>
              <Button
                onClick={() => saveAnthropicKey(false)}
                disabled={saving || !anthropicKey.trim()}
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "Guardar"
                )}
              </Button>
            </div>
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-muted-foreground">
                Obtener API key en{" "}
                <a
                  href="https://console.anthropic.com/account/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  console.anthropic.com
                </a>
              </p>
              <button
                onClick={() => saveAnthropicKey(true)}
                disabled={saving || !anthropicKey.trim()}
                className="text-xs bg-amber-100 text-amber-700 hover:bg-amber-200 px-2 py-1 rounded disabled:opacity-50"
              >
                Guardar sin validar
              </button>
            </div>
          </div>

          {/* AI Analysis Toggle */}
          <div className="flex items-center justify-between p-4 rounded-lg border">
            <div className="flex items-center gap-4">
              <div className={`h-10 w-10 rounded-full flex items-center justify-center ${
                aiEnabled ? "bg-green-100" : "bg-slate-100"
              }`}>
                <Shield className={`h-5 w-5 ${aiEnabled ? "text-green-600" : "text-slate-400"}`} />
              </div>
              <div>
                <p className="font-medium">Analisis de Documentos con IA</p>
                <p className="text-sm text-muted-foreground">
                  Habilita el analisis automatico de estudios de factibilidad
                </p>
              </div>
            </div>
            <Button
              variant={aiEnabled ? "default" : "outline"}
              onClick={toggleAiAnalysis}
              disabled={saving || !status?.ai_integration.anthropic_valid}
            >
              {aiEnabled ? "Desactivar" : "Activar"}
            </Button>
          </div>

          {!status?.ai_integration.anthropic_valid && (
            <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />
                <p className="text-sm text-amber-700">
                  Configura una API key valida de Anthropic para habilitar el analisis de documentos con IA
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Refresh Button */}
      <div className="flex justify-end">
        <Button variant="outline" onClick={loadData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Actualizar Estado
        </Button>
      </div>
    </div>
  );
}
