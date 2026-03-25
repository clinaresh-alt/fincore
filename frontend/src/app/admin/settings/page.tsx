"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth-store";
import { apiClient } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  Wallet,
  Link2,
  FileCode2,
  Globe,
  Server,
  ExternalLink,
  Save,
  RotateCcw,
  Upload,
  DollarSign,
  Clock,
} from "lucide-react";
import { PageHeader } from "@/components/page-header";
import {
  useConfigStore,
  useProductionReady,
  BlockchainConfig,
  SystemConfig,
} from "@/store/config-store";
import { toast } from "sonner";

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

  // AI Form states
  const [anthropicKey, setAnthropicKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);

  // Blockchain config store
  const {
    blockchain,
    system,
    isLoaded,
    lastUpdated,
    setBlockchainConfig,
    setSystemConfig,
    saveConfig,
    resetToDefaults,
  } = useConfigStore();

  const { isReady, missingItems } = useProductionReady();

  // Local form state for blockchain
  const [blockchainForm, setBlockchainForm] = useState<BlockchainConfig>(blockchain);
  const [systemForm, setSystemForm] = useState<SystemConfig>(system);

  useEffect(() => {
    setBlockchainForm(blockchain);
    setSystemForm(system);
  }, [blockchain, system]);

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
      loadData();

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

  // Blockchain config handlers
  const handleSaveBlockchain = async () => {
    setSaving(true);
    try {
      setBlockchainConfig(blockchainForm);
      setSystemConfig(systemForm);
      await saveConfig();
      toast.success("Configuracion blockchain guardada correctamente");
    } catch (error) {
      toast.error("Error al guardar la configuracion");
    } finally {
      setSaving(false);
    }
  };

  const handleResetBlockchain = () => {
    resetToDefaults();
    setBlockchainForm(blockchain);
    setSystemForm(system);
    toast.info("Configuracion restablecida a valores por defecto");
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
    <div className="space-y-6">
      <PageHeader
        title="Configuracion del Sistema"
        description="Administra blockchain, IA y configuraciones avanzadas"
        backHref="/admin"
        actions={
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Actualizar
          </Button>
        }
      />

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

      {/* Main Tabs */}
      <Tabs defaultValue="blockchain" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="blockchain" className="flex items-center gap-2">
            <Wallet className="h-4 w-4" />
            Blockchain
          </TabsTrigger>
          <TabsTrigger value="ai" className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Inteligencia Artificial
          </TabsTrigger>
          <TabsTrigger value="system" className="flex items-center gap-2">
            <Server className="h-4 w-4" />
            Sistema
          </TabsTrigger>
        </TabsList>

        {/* ==================== BLOCKCHAIN TAB ==================== */}
        <TabsContent value="blockchain" className="space-y-6">
          {/* Production Ready Status */}
          <Card className={isReady ? "border-green-200 bg-green-50" : "border-yellow-200 bg-yellow-50"}>
            <CardContent className="p-4">
              <div className="flex items-start gap-4">
                {isReady ? (
                  <CheckCircle2 className="h-6 w-6 text-green-600 mt-0.5" />
                ) : (
                  <AlertTriangle className="h-6 w-6 text-yellow-600 mt-0.5" />
                )}
                <div className="flex-1">
                  <h3 className={`font-semibold ${isReady ? "text-green-800" : "text-yellow-800"}`}>
                    {isReady ? "Blockchain Listo para Produccion" : "Configuracion Blockchain Incompleta"}
                  </h3>
                  {!isReady && (
                    <div className="mt-2">
                      <p className="text-sm text-yellow-700 mb-2">
                        Elementos pendientes de configurar:
                      </p>
                      <ul className="text-sm text-yellow-600 space-y-1">
                        {missingItems.map((item, i) => (
                          <li key={i} className="flex items-center gap-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-yellow-500" />
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {lastUpdated && (
                    <p className="text-xs text-muted-foreground mt-2">
                      Ultima actualizacion: {new Date(lastUpdated).toLocaleString("es-MX")}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleResetBlockchain}>
                    <RotateCcw className="h-4 w-4 mr-1" />
                    Reset
                  </Button>
                  <Button size="sm" onClick={handleSaveBlockchain} disabled={saving}>
                    {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Save className="h-4 w-4 mr-1" />}
                    Guardar
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* WalletConnect */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Link2 className="h-5 w-5" />
                WalletConnect
              </CardTitle>
              <CardDescription>
                Configuracion para conectar wallets de usuarios.{" "}
                <a
                  href="https://cloud.walletconnect.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline inline-flex items-center gap-1"
                >
                  Obtener Project ID <ExternalLink className="h-3 w-3" />
                </a>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="walletConnectProjectId">Project ID</Label>
                <Input
                  id="walletConnectProjectId"
                  placeholder="Ej: abc123def456..."
                  value={blockchainForm.walletConnectProjectId}
                  onChange={(e) =>
                    setBlockchainForm({ ...blockchainForm, walletConnectProjectId: e.target.value })
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Requerido para que los usuarios puedan conectar sus wallets
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Smart Contracts */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileCode2 className="h-5 w-5" />
                Smart Contracts
              </CardTitle>
              <CardDescription>
                Direcciones de los contratos desplegados en la red
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="investmentContract">Contrato de Inversion</Label>
                  <Input
                    id="investmentContract"
                    placeholder="0x..."
                    value={blockchainForm.investmentContract}
                    onChange={(e) =>
                      setBlockchainForm({ ...blockchainForm, investmentContract: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="kycContract">Contrato de KYC</Label>
                  <Input
                    id="kycContract"
                    placeholder="0x..."
                    value={blockchainForm.kycContract}
                    onChange={(e) =>
                      setBlockchainForm({ ...blockchainForm, kycContract: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dividendsContract">Contrato de Dividendos</Label>
                  <Input
                    id="dividendsContract"
                    placeholder="0x..."
                    value={blockchainForm.dividendsContract}
                    onChange={(e) =>
                      setBlockchainForm({ ...blockchainForm, dividendsContract: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="tokenFactoryContract">Token Factory</Label>
                  <Input
                    id="tokenFactoryContract"
                    placeholder="0x..."
                    value={blockchainForm.tokenFactoryContract}
                    onChange={(e) =>
                      setBlockchainForm({ ...blockchainForm, tokenFactoryContract: e.target.value })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Network Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5" />
                Configuracion de Red
              </CardTitle>
              <CardDescription>Red por defecto y modo de operacion</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Red Principal</Label>
                  <Select
                    value={blockchainForm.defaultNetwork}
                    onValueChange={(value: "polygon" | "ethereum" | "arbitrum" | "base") =>
                      setBlockchainForm({ ...blockchainForm, defaultNetwork: value })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Seleccionar red" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="polygon">Polygon</SelectItem>
                      <SelectItem value="ethereum">Ethereum</SelectItem>
                      <SelectItem value="arbitrum">Arbitrum</SelectItem>
                      <SelectItem value="base">Base</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Modo de Red</Label>
                  <div className="flex items-center gap-4 h-10">
                    <span className={`text-sm ${!blockchainForm.isTestnet ? "font-medium" : "text-muted-foreground"}`}>
                      Mainnet
                    </span>
                    <Switch
                      checked={blockchainForm.isTestnet}
                      onCheckedChange={(checked) =>
                        setBlockchainForm({ ...blockchainForm, isTestnet: checked })
                      }
                    />
                    <span className={`text-sm ${blockchainForm.isTestnet ? "font-medium" : "text-muted-foreground"}`}>
                      Testnet
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* RPC URLs */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                RPC URLs
              </CardTitle>
              <CardDescription>
                URLs de los nodos RPC. Recomendado usar Infura o Alchemy para produccion.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="rpcPolygon">Polygon Mainnet</Label>
                  <Input
                    id="rpcPolygon"
                    placeholder="https://polygon-rpc.com"
                    value={blockchainForm.rpcUrls.polygon}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        rpcUrls: { ...blockchainForm.rpcUrls, polygon: e.target.value },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rpcPolygonAmoy">Polygon Amoy (Testnet)</Label>
                  <Input
                    id="rpcPolygonAmoy"
                    placeholder="https://rpc-amoy.polygon.technology"
                    value={blockchainForm.rpcUrls.polygonAmoy}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        rpcUrls: { ...blockchainForm.rpcUrls, polygonAmoy: e.target.value },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rpcEthereum">Ethereum Mainnet</Label>
                  <Input
                    id="rpcEthereum"
                    placeholder="https://eth.llamarpc.com"
                    value={blockchainForm.rpcUrls.ethereum}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        rpcUrls: { ...blockchainForm.rpcUrls, ethereum: e.target.value },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rpcSepolia">Sepolia (Testnet)</Label>
                  <Input
                    id="rpcSepolia"
                    placeholder="https://rpc.sepolia.org"
                    value={blockchainForm.rpcUrls.sepolia}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        rpcUrls: { ...blockchainForm.rpcUrls, sepolia: e.target.value },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rpcArbitrum">Arbitrum One</Label>
                  <Input
                    id="rpcArbitrum"
                    placeholder="https://arb1.arbitrum.io/rpc"
                    value={blockchainForm.rpcUrls.arbitrum}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        rpcUrls: { ...blockchainForm.rpcUrls, arbitrum: e.target.value },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rpcBase">Base</Label>
                  <Input
                    id="rpcBase"
                    placeholder="https://mainnet.base.org"
                    value={blockchainForm.rpcUrls.base}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        rpcUrls: { ...blockchainForm.rpcUrls, base: e.target.value },
                      })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Explorer API Keys */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                API Keys de Exploradores
              </CardTitle>
              <CardDescription>
                Claves API para verificar transacciones en exploradores de bloques
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="apiPolygonscan">Polygonscan API Key</Label>
                  <Input
                    id="apiPolygonscan"
                    type="password"
                    placeholder="Tu API Key..."
                    value={blockchainForm.explorerApiKeys.polygonscan}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        explorerApiKeys: {
                          ...blockchainForm.explorerApiKeys,
                          polygonscan: e.target.value,
                        },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="apiEtherscan">Etherscan API Key</Label>
                  <Input
                    id="apiEtherscan"
                    type="password"
                    placeholder="Tu API Key..."
                    value={blockchainForm.explorerApiKeys.etherscan}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        explorerApiKeys: {
                          ...blockchainForm.explorerApiKeys,
                          etherscan: e.target.value,
                        },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="apiArbiscan">Arbiscan API Key</Label>
                  <Input
                    id="apiArbiscan"
                    type="password"
                    placeholder="Tu API Key..."
                    value={blockchainForm.explorerApiKeys.arbiscan}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        explorerApiKeys: {
                          ...blockchainForm.explorerApiKeys,
                          arbiscan: e.target.value,
                        },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="apiBasescan">Basescan API Key</Label>
                  <Input
                    id="apiBasescan"
                    type="password"
                    placeholder="Tu API Key..."
                    value={blockchainForm.explorerApiKeys.basescan}
                    onChange={(e) =>
                      setBlockchainForm({
                        ...blockchainForm,
                        explorerApiKeys: {
                          ...blockchainForm.explorerApiKeys,
                          basescan: e.target.value,
                        },
                      })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ==================== AI TAB ==================== */}
        <TabsContent value="ai" className="space-y-6">
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
        </TabsContent>

        {/* ==================== SYSTEM TAB ==================== */}
        <TabsContent value="system" className="space-y-6">
          {/* General */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                General
              </CardTitle>
              <CardDescription>Configuracion general de la aplicacion</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="appName">Nombre de la Aplicacion</Label>
                  <Input
                    id="appName"
                    value={systemForm.appName}
                    onChange={(e) => setSystemForm({ ...systemForm, appName: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="appVersion">Version</Label>
                  <Input
                    id="appVersion"
                    value={systemForm.appVersion}
                    onChange={(e) => setSystemForm({ ...systemForm, appVersion: e.target.value })}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between p-4 rounded-lg border">
                <div>
                  <p className="font-medium">Modo Debug</p>
                  <p className="text-sm text-muted-foreground">
                    Habilita logs detallados y herramientas de desarrollo
                  </p>
                </div>
                <Switch
                  checked={systemForm.debugMode}
                  onCheckedChange={(checked) =>
                    setSystemForm({ ...systemForm, debugMode: checked })
                  }
                />
              </div>
            </CardContent>
          </Card>

          {/* API Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                API Backend
              </CardTitle>
              <CardDescription>Configuracion de conexion al servidor</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="apiUrl">URL del API</Label>
                  <Input
                    id="apiUrl"
                    value={systemForm.apiUrl}
                    onChange={(e) => setSystemForm({ ...systemForm, apiUrl: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="apiTimeout">Timeout (ms)</Label>
                  <Input
                    id="apiTimeout"
                    type="number"
                    value={systemForm.apiTimeout}
                    onChange={(e) =>
                      setSystemForm({ ...systemForm, apiTimeout: parseInt(e.target.value) || 30000 })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Limits */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Limites del Sistema
              </CardTitle>
              <CardDescription>Limites de carga y sesion</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="maxUploadSize">Tamano maximo de archivo (MB)</Label>
                  <Input
                    id="maxUploadSize"
                    type="number"
                    value={systemForm.maxUploadSize}
                    onChange={(e) =>
                      setSystemForm({ ...systemForm, maxUploadSize: parseInt(e.target.value) || 10 })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sessionTimeout">Timeout de sesion (minutos)</Label>
                  <Input
                    id="sessionTimeout"
                    type="number"
                    value={systemForm.sessionTimeout}
                    onChange={(e) =>
                      setSystemForm({
                        ...systemForm,
                        sessionTimeout: parseInt(e.target.value) || 480,
                      })
                    }
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Compliance */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Compliance e Inversiones
              </CardTitle>
              <CardDescription>Configuracion de KYC y limites de inversion</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg border">
                <div>
                  <p className="font-medium">KYC Obligatorio</p>
                  <p className="text-sm text-muted-foreground">
                    Requiere verificacion de identidad para invertir
                  </p>
                </div>
                <Switch
                  checked={systemForm.kycRequired}
                  onCheckedChange={(checked) =>
                    setSystemForm({ ...systemForm, kycRequired: checked })
                  }
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="minInvestment">Inversion Minima (MXN)</Label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="minInvestment"
                      type="number"
                      className="pl-10"
                      value={systemForm.minInvestment}
                      onChange={(e) =>
                        setSystemForm({
                          ...systemForm,
                          minInvestment: parseInt(e.target.value) || 1000,
                        })
                      }
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="maxInvestment">Inversion Maxima (MXN)</Label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="maxInvestment"
                      type="number"
                      className="pl-10"
                      value={systemForm.maxInvestment}
                      onChange={(e) =>
                        setSystemForm({
                          ...systemForm,
                          maxInvestment: parseInt(e.target.value) || 1000000,
                        })
                      }
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-4 border-t">
                <Button onClick={handleSaveBlockchain} disabled={saving}>
                  {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                  Guardar Configuracion del Sistema
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
