"use client";

import { useEffect, useState } from "react";
import { blockchainAPI } from "@/lib/api-client";
import {
  UserWallet,
  ProjectToken,
  BlockchainTransaction,
  BlockchainPortfolio,
} from "@/types";

// Network response type from API
interface NetworkResponse {
  network: string;
  name: string;
  chain_id: number;
  currency_symbol: string;
  block_explorer: string;
  is_testnet: boolean;
  is_connected: boolean;
  current_block: number | null;
}
import { formatCurrency, formatDate } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/page-header";
import {
  Wallet,
  Network,
  Coins,
  ArrowRightLeft,
  Plus,
  RefreshCw,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  Copy,
  Trash2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

// Network display names
const NETWORK_NAMES: Record<string, string> = {
  polygon: "Polygon",
  polygon_mumbai: "Polygon Mumbai",
  ethereum: "Ethereum",
  ethereum_sepolia: "Ethereum Sepolia",
  arbitrum: "Arbitrum",
  base: "Base",
};

// Explorer URLs
const EXPLORER_URLS: Record<string, string> = {
  polygon: "https://polygonscan.com",
  polygon_mumbai: "https://mumbai.polygonscan.com",
  ethereum: "https://etherscan.io",
  ethereum_sepolia: "https://sepolia.etherscan.io",
  arbitrum: "https://arbiscan.io",
  base: "https://basescan.org",
};

export default function BlockchainPage() {
  const [networks, setNetworks] = useState<NetworkResponse[]>([]);
  const [wallets, setWallets] = useState<UserWallet[]>([]);
  const [tokens, setTokens] = useState<ProjectToken[]>([]);
  const [transactions, setTransactions] = useState<BlockchainTransaction[]>([]);
  const [portfolio, setPortfolio] = useState<BlockchainPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Dialog states
  const [addWalletOpen, setAddWalletOpen] = useState(false);
  const [newWalletAddress, setNewWalletAddress] = useState("");
  const [newWalletNetwork, setNewWalletNetwork] = useState("polygon");
  const [newWalletLabel, setNewWalletLabel] = useState("");

  const { toast } = useToast();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [networksData, walletsData, tokensData, txData, portfolioData] =
        await Promise.all([
          blockchainAPI.getNetworks().catch(() => []),
          blockchainAPI.listWallets().catch(() => []),
          blockchainAPI.listTokens().catch(() => []),
          blockchainAPI.listTransactions({ limit: 10 }).catch(() => []),
          blockchainAPI.getPortfolio().catch(() => null),
        ]);

      setNetworks(networksData || []);
      setWallets(walletsData || []);
      setTokens(tokensData || []);
      setTransactions(txData || []);
      setPortfolio(portfolioData);
    } catch (error) {
      console.error("Error loading blockchain data:", error);
    } finally {
      setLoading(false);
    }
  };

  const refreshData = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
    toast({
      title: "Datos actualizados",
      description: "La informacion de blockchain se ha actualizado",
    });
  };

  const handleAddWallet = async () => {
    try {
      await blockchainAPI.createWallet({
        address: newWalletAddress,
        network: newWalletNetwork,
        label: newWalletLabel || undefined,
      });
      toast({
        title: "Wallet agregada",
        description: "La wallet se ha registrado correctamente",
      });
      setAddWalletOpen(false);
      setNewWalletAddress("");
      setNewWalletLabel("");
      loadData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "No se pudo agregar la wallet",
        variant: "destructive",
      });
    }
  };

  const handleDeleteWallet = async (walletId: string) => {
    try {
      await blockchainAPI.deleteWallet(walletId);
      toast({
        title: "Wallet eliminada",
        description: "La wallet se ha eliminado correctamente",
      });
      loadData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "No se pudo eliminar la wallet",
        variant: "destructive",
      });
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast({
      title: "Copiado",
      description: "Direccion copiada al portapapeles",
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "confirmed":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "pending":
      case "submitted":
        return <Clock className="h-4 w-4 text-yellow-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (connected: boolean) => {
    return connected ? "bg-green-500" : "bg-red-500";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  const connectedNetworks = networks.filter((n) => n.is_connected).length;
  const totalNetworks = networks.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Blockchain"
        description="Gestiona tus wallets, tokens e inversiones on-chain"
        backHref="/dashboard"
        actions={
          <Button onClick={refreshData} variant="outline" disabled={refreshing}>
            <RefreshCw
              className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`}
            />
            Actualizar
          </Button>
        }
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center">
                <Network className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Redes Activas</p>
                <p className="text-2xl font-bold">
                  {connectedNetworks}/{totalNetworks}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                <Wallet className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Wallets</p>
                <p className="text-2xl font-bold">{wallets.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <Coins className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Valor Portfolio</p>
                <p className="text-2xl font-bold">
                  {portfolio
                    ? formatCurrency(portfolio.total_value_usd)
                    : "$0.00"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-orange-100 flex items-center justify-center">
                <TrendingUp className="h-6 w-6 text-orange-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Ganancia/Perdida</p>
                <p
                  className={`text-2xl font-bold ${
                    portfolio && portfolio.total_gain_loss >= 0
                      ? "text-green-600"
                      : "text-red-600"
                  }`}
                >
                  {portfolio
                    ? `${portfolio.total_gain_loss >= 0 ? "+" : ""}${formatCurrency(
                        portfolio.total_gain_loss
                      )}`
                    : "$0.00"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="networks" className="space-y-4">
        <TabsList>
          <TabsTrigger value="networks">
            <Network className="h-4 w-4 mr-2" />
            Redes
          </TabsTrigger>
          <TabsTrigger value="wallets">
            <Wallet className="h-4 w-4 mr-2" />
            Wallets
          </TabsTrigger>
          <TabsTrigger value="tokens">
            <Coins className="h-4 w-4 mr-2" />
            Tokens
          </TabsTrigger>
          <TabsTrigger value="transactions">
            <ArrowRightLeft className="h-4 w-4 mr-2" />
            Transacciones
          </TabsTrigger>
        </TabsList>

        {/* Networks Tab */}
        <TabsContent value="networks">
          <Card>
            <CardHeader>
              <CardTitle>Estado de Redes Blockchain</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {networks.map((network) => (
                  <div
                    key={network.network}
                    className="p-4 border rounded-lg space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className={`h-3 w-3 rounded-full ${getStatusColor(
                            network.is_connected
                          )}`}
                        />
                        <span className="font-medium">
                          {network.name}
                        </span>
                        {network.is_testnet && (
                          <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded">
                            Testnet
                          </span>
                        )}
                      </div>
                      <a
                        href={network.block_explorer}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-primary"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </div>

                    {network.is_connected ? (
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Bloque:</span>
                          <span className="font-mono">
                            {network.current_block?.toLocaleString() || "..."}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Chain ID:</span>
                          <span className="font-mono">{network.chain_id}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Moneda:</span>
                          <span className="font-mono">{network.currency_symbol}</span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-red-500">No conectado</p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Wallets Tab */}
        <TabsContent value="wallets">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Mis Wallets</CardTitle>
              <Dialog open={addWalletOpen} onOpenChange={setAddWalletOpen}>
                <DialogTrigger asChild>
                  <Button>
                    <Plus className="h-4 w-4 mr-2" />
                    Agregar Wallet
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Agregar Nueva Wallet</DialogTitle>
                    <DialogDescription>
                      Registra una wallet existente para recibir tokens e
                      inversiones.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="address">Direccion de Wallet</Label>
                      <Input
                        id="address"
                        placeholder="0x..."
                        value={newWalletAddress}
                        onChange={(e) => setNewWalletAddress(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="network">Red</Label>
                      <Select
                        value={newWalletNetwork}
                        onValueChange={setNewWalletNetwork}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(NETWORK_NAMES).map(([key, name]) => (
                            <SelectItem key={key} value={key}>
                              {name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="label">Etiqueta (opcional)</Label>
                      <Input
                        id="label"
                        placeholder="Mi wallet principal"
                        value={newWalletLabel}
                        onChange={(e) => setNewWalletLabel(e.target.value)}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setAddWalletOpen(false)}
                    >
                      Cancelar
                    </Button>
                    <Button onClick={handleAddWallet}>Agregar</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              {wallets.length > 0 ? (
                <div className="space-y-3">
                  {wallets.map((wallet) => (
                    <div
                      key={wallet.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-slate-50"
                    >
                      <div className="flex items-center gap-4">
                        <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                          <Wallet className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">
                              {wallet.label || "Wallet"}
                            </span>
                            {wallet.is_primary && (
                              <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
                                Principal
                              </span>
                            )}
                            {wallet.is_verified && (
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <span className="font-mono">
                              {wallet.address.slice(0, 6)}...
                              {wallet.address.slice(-4)}
                            </span>
                            <button
                              onClick={() => copyToClipboard(wallet.address)}
                              className="hover:text-primary"
                            >
                              <Copy className="h-3 w-3" />
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-sm text-muted-foreground">
                          {NETWORK_NAMES[wallet.network]}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteWallet(wallet.id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Wallet className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="text-muted-foreground">
                    No tienes wallets registradas
                  </p>
                  <Button
                    className="mt-4"
                    onClick={() => setAddWalletOpen(true)}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Agregar tu primera wallet
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tokens Tab */}
        <TabsContent value="tokens">
          <Card>
            <CardHeader>
              <CardTitle>Tokens de Proyectos</CardTitle>
            </CardHeader>
            <CardContent>
              {tokens.length > 0 ? (
                <div className="space-y-3">
                  {tokens.map((token) => (
                    <div
                      key={token.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-slate-50"
                    >
                      <div className="flex items-center gap-4">
                        <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
                          <Coins className="h-5 w-5 text-green-600" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{token.nombre}</span>
                            <span className="text-muted-foreground">
                              ({token.simbolo})
                            </span>
                            {token.is_active ? (
                              <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                                Activo
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">
                                Pendiente
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {token.proyecto_nombre ||
                              `Proyecto: ${token.proyecto_id.slice(0, 8)}`}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-medium">
                          {formatCurrency(token.precio_por_token)}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {token.supply_vendido.toLocaleString()} /{" "}
                          {token.supply_total.toLocaleString()} tokens
                        </p>
                        <div className="w-32 h-2 bg-gray-200 rounded-full mt-1">
                          <div
                            className="h-full bg-green-500 rounded-full"
                            style={{
                              width: `${Math.min(
                                (token.supply_vendido / token.supply_total) *
                                  100,
                                100
                              )}%`,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Coins className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="text-muted-foreground">
                    No hay tokens disponibles
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Los tokens aparecen cuando los proyectos son tokenizados
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Transactions Tab */}
        <TabsContent value="transactions">
          <Card>
            <CardHeader>
              <CardTitle>Historial de Transacciones</CardTitle>
            </CardHeader>
            <CardContent>
              {transactions.length > 0 ? (
                <div className="space-y-3">
                  {transactions.map((tx) => (
                    <div
                      key={tx.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-slate-50"
                    >
                      <div className="flex items-center gap-4">
                        {getStatusIcon(tx.status)}
                        <div>
                          <p className="font-medium capitalize">
                            {tx.tipo.replace(/_/g, " ")}
                          </p>
                          {tx.tx_hash && (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                              <span className="font-mono">
                                {tx.tx_hash.slice(0, 10)}...
                                {tx.tx_hash.slice(-8)}
                              </span>
                              <a
                                href={`${EXPLORER_URLS[tx.network]}/tx/${tx.tx_hash}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="hover:text-primary"
                              >
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        {tx.monto && (
                          <p className="font-medium">
                            {formatCurrency(tx.monto)}
                          </p>
                        )}
                        <p className="text-sm text-muted-foreground">
                          {formatDate(tx.created_at)}
                        </p>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full ${
                            tx.status === "confirmed"
                              ? "bg-green-100 text-green-700"
                              : tx.status === "failed"
                              ? "bg-red-100 text-red-700"
                              : "bg-yellow-100 text-yellow-700"
                          }`}
                        >
                          {tx.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <ArrowRightLeft className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="text-muted-foreground">
                    No hay transacciones registradas
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
