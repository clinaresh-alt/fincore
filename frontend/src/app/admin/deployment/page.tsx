"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Rocket,
  CheckCircle,
  AlertCircle,
  Clock,
  ExternalLink,
  Copy,
  RefreshCw,
  Server,
  Coins
} from "lucide-react";

// Tipos para contratos desplegados
interface DeployedContract {
  name: string;
  address: string;
  network: string;
  chainId: number;
  deployedAt: string;
  verified: boolean;
  explorerUrl?: string;
}

interface DeploymentStatus {
  network: string;
  chainId: number;
  contracts: DeployedContract[];
  lastDeployment?: string;
}

// Redes soportadas
const NETWORKS = [
  { id: "polygonAmoy", name: "Polygon Amoy (Testnet)", chainId: 80002, isTestnet: true },
  { id: "sepolia", name: "Sepolia (Testnet)", chainId: 11155111, isTestnet: true },
  { id: "polygon", name: "Polygon", chainId: 137, isTestnet: false },
  { id: "arbitrum", name: "Arbitrum One", chainId: 42161, isTestnet: false },
  { id: "base", name: "Base", chainId: 8453, isTestnet: false },
];

// URLs de exploradores
const EXPLORER_URLS: Record<string, string> = {
  polygon: "https://polygonscan.com",
  polygonAmoy: "https://amoy.polygonscan.com",
  sepolia: "https://sepolia.etherscan.io",
  arbitrum: "https://arbiscan.io",
  base: "https://basescan.org",
};

export default function DeploymentPage() {
  const [deployments, setDeployments] = useState<DeploymentStatus[]>([]);
  const [selectedNetwork, setSelectedNetwork] = useState("polygonAmoy");
  const [isDeploying, setIsDeploying] = useState(false);
  const [deploymentLog, setDeploymentLog] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // Estado para deploy de token
  const [tokenForm, setTokenForm] = useState({
    projectName: "",
    projectSymbol: "",
    totalSupply: "1000000",
    projectUri: "",
  });

  useEffect(() => {
    fetchDeployments();
  }, []);

  const fetchDeployments = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/admin/deployments");
      if (response.ok) {
        const data = await response.json();
        setDeployments(data);
      }
    } catch (error) {
      console.error("Error fetching deployments:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeployInfrastructure = async () => {
    setIsDeploying(true);
    setDeploymentLog([]);

    try {
      const response = await fetch("/api/admin/deployments/infrastructure", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ network: selectedNetwork }),
      });

      if (response.ok) {
        const result = await response.json();
        setDeploymentLog([
          "Deployment iniciado...",
          `Red: ${selectedNetwork}`,
          `FinCoreKYC: ${result.contracts?.FinCoreKYC?.address || "Pendiente"}`,
          `FinCoreInvestment: ${result.contracts?.FinCoreInvestment?.address || "Pendiente"}`,
          `FinCoreDividends: ${result.contracts?.FinCoreDividends?.address || "Pendiente"}`,
          "Deployment completado!",
        ]);
        fetchDeployments();
      } else {
        const error = await response.json();
        setDeploymentLog([`Error: ${error.message}`]);
      }
    } catch (error) {
      setDeploymentLog([`Error: ${error}`]);
    } finally {
      setIsDeploying(false);
    }
  };

  const handleDeployToken = async () => {
    if (!tokenForm.projectName || !tokenForm.projectSymbol || !tokenForm.totalSupply) {
      return;
    }

    setIsDeploying(true);
    setDeploymentLog([]);

    try {
      const response = await fetch("/api/admin/deployments/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          network: selectedNetwork,
          ...tokenForm,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        setDeploymentLog([
          "Deployment de token iniciado...",
          `Token: ${tokenForm.projectName} (${tokenForm.projectSymbol})`,
          `Supply: ${parseInt(tokenForm.totalSupply).toLocaleString()}`,
          `Direccion: ${result.address}`,
          "Token desplegado exitosamente!",
        ]);
        setTokenForm({
          projectName: "",
          projectSymbol: "",
          totalSupply: "1000000",
          projectUri: "",
        });
        fetchDeployments();
      } else {
        const error = await response.json();
        setDeploymentLog([`Error: ${error.message}`]);
      }
    } catch (error) {
      setDeploymentLog([`Error: ${error}`]);
    } finally {
      setIsDeploying(false);
    }
  };

  const handleVerifyContracts = async () => {
    setIsDeploying(true);
    setDeploymentLog(["Verificando contratos..."]);

    try {
      const response = await fetch("/api/admin/deployments/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ network: selectedNetwork }),
      });

      if (response.ok) {
        const result = await response.json();
        setDeploymentLog([
          "Verificacion completada",
          ...result.results.map((r: { name: string; verified: boolean }) =>
            `${r.name}: ${r.verified ? "Verificado" : "Error"}`
          ),
        ]);
        fetchDeployments();
      }
    } catch (error) {
      setDeploymentLog([`Error: ${error}`]);
    } finally {
      setIsDeploying(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const getNetworkDeployment = (networkId: string) => {
    return deployments.find((d) => d.network === networkId);
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">Smart Contracts Deployment</h1>
          <p className="text-muted-foreground">
            Gestiona el deployment y verificacion de contratos inteligentes
          </p>
        </div>
        <Button variant="outline" onClick={fetchDeployments}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Actualizar
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-3 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Contratos Desplegados</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {deployments.reduce((acc, d) => acc + d.contracts.length, 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              En {deployments.length} redes
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Contratos Verificados</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {deployments.reduce(
                (acc, d) => acc + d.contracts.filter((c) => c.verified).length,
                0
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Codigo fuente publico
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ultimo Deployment</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {deployments[0]?.lastDeployment
                ? new Date(deployments[0].lastDeployment).toLocaleDateString()
                : "-"}
            </div>
            <p className="text-xs text-muted-foreground">
              {deployments[0]?.network || "Sin deployments"}
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="deploy" className="space-y-6">
        <TabsList>
          <TabsTrigger value="deploy">Deployment</TabsTrigger>
          <TabsTrigger value="token">Token de Proyecto</TabsTrigger>
          <TabsTrigger value="status">Estado Actual</TabsTrigger>
        </TabsList>

        <TabsContent value="deploy" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Rocket className="h-5 w-5" />
                Deploy Infraestructura
              </CardTitle>
              <CardDescription>
                Despliega los contratos base: KYC, Investment y Dividends
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Red de Deployment</Label>
                  <Select value={selectedNetwork} onValueChange={setSelectedNetwork}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {NETWORKS.map((net) => (
                        <SelectItem key={net.id} value={net.id}>
                          <span className="flex items-center gap-2">
                            {net.name}
                            {net.isTestnet && (
                              <Badge variant="secondary" className="text-xs">
                                Testnet
                              </Badge>
                            )}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Chain ID</Label>
                  <Input
                    value={NETWORKS.find((n) => n.id === selectedNetwork)?.chainId || ""}
                    disabled
                  />
                </div>
              </div>

              <div className="flex gap-4">
                <Button
                  onClick={handleDeployInfrastructure}
                  disabled={isDeploying}
                  className="flex-1"
                >
                  {isDeploying ? (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      Desplegando...
                    </>
                  ) : (
                    <>
                      <Rocket className="mr-2 h-4 w-4" />
                      Deploy Contratos Base
                    </>
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={handleVerifyContracts}
                  disabled={isDeploying}
                >
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Verificar
                </Button>
              </div>

              {deploymentLog.length > 0 && (
                <div className="mt-4 p-4 bg-muted rounded-lg font-mono text-sm">
                  {deploymentLog.map((log, i) => (
                    <div key={i} className="py-1">
                      {log}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Comandos de Terminal</CardTitle>
              <CardDescription>
                Para deployment manual desde la terminal
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 font-mono text-sm">
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-muted-foreground mb-2"># Deploy en testnet (Polygon Amoy)</p>
                  <code>npm run deploy:amoy</code>
                </div>
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-muted-foreground mb-2"># Deploy en mainnet (Polygon)</p>
                  <code>npm run deploy:polygon</code>
                </div>
                <div className="p-3 bg-muted rounded-lg">
                  <p className="text-muted-foreground mb-2"># Verificar contratos</p>
                  <code>npm run verify:polygon</code>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="token" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Coins className="h-5 w-5" />
                Deploy Token de Proyecto
              </CardTitle>
              <CardDescription>
                Crea un nuevo token ERC20 para tokenizar un proyecto de inversion
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Nombre del Proyecto *</Label>
                  <Input
                    placeholder="Edificio Centro Historico"
                    value={tokenForm.projectName}
                    onChange={(e) =>
                      setTokenForm({ ...tokenForm, projectName: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label>Simbolo del Token *</Label>
                  <Input
                    placeholder="EDCH"
                    maxLength={5}
                    value={tokenForm.projectSymbol}
                    onChange={(e) =>
                      setTokenForm({
                        ...tokenForm,
                        projectSymbol: e.target.value.toUpperCase(),
                      })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label>Supply Total *</Label>
                  <Input
                    type="number"
                    placeholder="1000000"
                    value={tokenForm.totalSupply}
                    onChange={(e) =>
                      setTokenForm({ ...tokenForm, totalSupply: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label>URI de Metadata (opcional)</Label>
                  <Input
                    placeholder="https://..."
                    value={tokenForm.projectUri}
                    onChange={(e) =>
                      setTokenForm({ ...tokenForm, projectUri: e.target.value })
                    }
                  />
                </div>
              </div>

              <div className="flex gap-4">
                <Select value={selectedNetwork} onValueChange={setSelectedNetwork}>
                  <SelectTrigger className="w-[200px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {NETWORKS.map((net) => (
                      <SelectItem key={net.id} value={net.id}>
                        {net.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Button
                  onClick={handleDeployToken}
                  disabled={
                    isDeploying ||
                    !tokenForm.projectName ||
                    !tokenForm.projectSymbol ||
                    !tokenForm.totalSupply
                  }
                  className="flex-1"
                >
                  {isDeploying ? (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      Desplegando Token...
                    </>
                  ) : (
                    <>
                      <Coins className="mr-2 h-4 w-4" />
                      Deploy Token
                    </>
                  )}
                </Button>
              </div>

              {deploymentLog.length > 0 && (
                <div className="mt-4 p-4 bg-muted rounded-lg font-mono text-sm">
                  {deploymentLog.map((log, i) => (
                    <div key={i} className="py-1">
                      {log}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="status" className="space-y-6">
          {loading ? (
            <Card>
              <CardContent className="py-8 text-center">
                <RefreshCw className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
                <p className="mt-2 text-muted-foreground">Cargando deployments...</p>
              </CardContent>
            </Card>
          ) : deployments.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <AlertCircle className="h-8 w-8 mx-auto text-muted-foreground" />
                <p className="mt-2 text-muted-foreground">
                  No hay contratos desplegados aun
                </p>
              </CardContent>
            </Card>
          ) : (
            NETWORKS.map((network) => {
              const deployment = getNetworkDeployment(network.id);
              if (!deployment) return null;

              return (
                <Card key={network.id}>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        {network.name}
                        {network.isTestnet && (
                          <Badge variant="secondary">Testnet</Badge>
                        )}
                      </span>
                      <span className="text-sm font-normal text-muted-foreground">
                        Chain ID: {network.chainId}
                      </span>
                    </CardTitle>
                    {deployment.lastDeployment && (
                      <CardDescription>
                        Ultimo deployment:{" "}
                        {new Date(deployment.lastDeployment).toLocaleString()}
                      </CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {deployment.contracts.map((contract) => (
                        <div
                          key={contract.address}
                          className="flex items-center justify-between p-4 border rounded-lg"
                        >
                          <div>
                            <p className="font-medium">{contract.name}</p>
                            <p className="text-sm text-muted-foreground font-mono">
                              {contract.address}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {contract.verified ? (
                              <Badge variant="default" className="bg-green-600">
                                <CheckCircle className="mr-1 h-3 w-3" />
                                Verificado
                              </Badge>
                            ) : (
                              <Badge variant="secondary">
                                <Clock className="mr-1 h-3 w-3" />
                                Sin verificar
                              </Badge>
                            )}
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => copyToClipboard(contract.address)}
                            >
                              <Copy className="h-4 w-4" />
                            </Button>
                            {EXPLORER_URLS[network.id] && (
                              <Button
                                variant="ghost"
                                size="icon"
                                asChild
                              >
                                <a
                                  href={`${EXPLORER_URLS[network.id]}/address/${contract.address}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  <ExternalLink className="h-4 w-4" />
                                </a>
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
