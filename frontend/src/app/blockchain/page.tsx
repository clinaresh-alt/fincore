"use client";

import { useEffect, useState } from "react";
import { useAccount, useChainId, useBalance, useSwitchChain, useSignMessage, useWriteContract, useWaitForTransactionReceipt } from "wagmi";
import { polygon, mainnet, arbitrum, base, sepolia, polygonAmoy } from "wagmi/chains";
import { blockchainAPI } from "@/lib/api-client";
import { ConnectWallet, useConnectedWallet } from "@/components/blockchain/connect-wallet";
import { USDC_ADDRESSES, USDC_ABI, CHAIN_TO_NETWORK, getExplorerUrl, formatAddress } from "@/lib/wagmi";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  UserWallet,
  ProjectToken,
  BlockchainTransaction,
  BlockchainPortfolio,
} from "@/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/page-header";
import { Progress } from "@/components/ui/progress";
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
  Shield,
  AlertTriangle,
  Zap,
  Link2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";

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

// Supported chains info
const SUPPORTED_CHAINS = [
  { chain: polygon, name: "Polygon", symbol: "MATIC", isTestnet: false },
  { chain: polygonAmoy, name: "Polygon Amoy", symbol: "MATIC", isTestnet: true },
  { chain: mainnet, name: "Ethereum", symbol: "ETH", isTestnet: false },
  { chain: sepolia, name: "Ethereum Sepolia", symbol: "ETH", isTestnet: true },
  { chain: arbitrum, name: "Arbitrum", symbol: "ETH", isTestnet: false },
  { chain: base, name: "Base", symbol: "ETH", isTestnet: false },
];

export default function BlockchainPage() {
  const { toast } = useToast();

  // Wallet state from wagmi
  const { address, isConnected } = useAccount();
  const chainId = useChainId();
  const { switchChain } = useSwitchChain();
  const { signMessageAsync } = useSignMessage();

  // Connected wallet hook with balances
  const {
    nativeBalance,
    nativeSymbol,
    usdcBalance,
    refetchBalances
  } = useConnectedWallet();

  // Backend data state
  const [networks, setNetworks] = useState<NetworkResponse[]>([]);
  const [wallets, setWallets] = useState<UserWallet[]>([]);
  const [tokens, setTokens] = useState<ProjectToken[]>([]);
  const [transactions, setTransactions] = useState<BlockchainTransaction[]>([]);
  const [portfolio, setPortfolio] = useState<BlockchainPortfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Dialog states
  const [linkWalletOpen, setLinkWalletOpen] = useState(false);
  const [linkingWallet, setLinkingWallet] = useState(false);
  const [purchaseTokenOpen, setPurchaseTokenOpen] = useState(false);
  const [selectedToken, setSelectedToken] = useState<ProjectToken | null>(null);
  const [purchaseAmount, setPurchaseAmount] = useState("");
  const [purchasing, setPurchasing] = useState(false);

  // Contract write for USDC approval
  const { writeContract, data: approvalHash, isPending: isApproving } = useWriteContract();
  const { isLoading: isApprovalConfirming, isSuccess: isApprovalConfirmed } = useWaitForTransactionReceipt({
    hash: approvalHash,
  });

  useEffect(() => {
    loadData();
  }, []);

  // Sync connected wallet with backend
  useEffect(() => {
    if (isConnected && address) {
      checkWalletLinked();
    }
  }, [isConnected, address]);

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
    await Promise.all([loadData(), refetchBalances()]);
    setRefreshing(false);
    toast({
      title: "Datos actualizados",
      description: "La informacion de blockchain se ha actualizado",
    });
  };

  const checkWalletLinked = async () => {
    if (!address) return;

    const isLinked = wallets.some(
      (w) => w.address.toLowerCase() === address.toLowerCase()
    );

    if (!isLinked && isConnected) {
      // Mostrar prompt para vincular
      setLinkWalletOpen(true);
    }
  };

  const handleLinkWallet = async () => {
    if (!address || !isConnected) return;

    setLinkingWallet(true);
    try {
      // Firma un mensaje para verificar propiedad
      const message = `Vincular wallet a FinCore\n\nDireccion: ${address}\nFecha: ${new Date().toISOString()}`;
      const signature = await signMessageAsync({ message });

      // Registrar en backend
      await blockchainAPI.createWallet({
        address,
        network: CHAIN_TO_NETWORK[chainId] || "polygon",
        label: "Mi Wallet Principal",
      });

      // Verificar con firma
      await blockchainAPI.verifyWallet({
        address,
        signature,
        message,
      });

      toast({
        title: "Wallet vinculada",
        description: "Tu wallet ha sido verificada y vinculada a tu cuenta",
      });

      setLinkWalletOpen(false);
      loadData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "No se pudo vincular la wallet",
        variant: "destructive",
      });
    } finally {
      setLinkingWallet(false);
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

  const handlePurchaseToken = async () => {
    if (!selectedToken || !purchaseAmount || !address) return;

    setPurchasing(true);
    try {
      const amount = parseFloat(purchaseAmount);
      const totalCost = amount * selectedToken.precio_por_token;
      const usdcAmount = BigInt(Math.floor(totalCost * 1e6)); // USDC tiene 6 decimales

      // 1. Aprobar USDC al contrato de inversion
      const contractAddress = process.env.NEXT_PUBLIC_INVESTMENT_CONTRACT as `0x${string}`;
      const usdcAddress = USDC_ADDRESSES[chainId];

      if (!contractAddress) {
        throw new Error("Contrato de inversion no configurado");
      }

      // Solicitar aprobacion de USDC
      writeContract({
        address: usdcAddress,
        abi: USDC_ABI,
        functionName: "approve",
        args: [contractAddress, usdcAmount],
      });

      toast({
        title: "Aprobacion solicitada",
        description: "Confirma la transaccion en tu wallet para aprobar el uso de USDC",
      });

    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "No se pudo iniciar la compra",
        variant: "destructive",
      });
      setPurchasing(false);
    }
  };

  // Efecto para completar compra despues de aprobacion
  useEffect(() => {
    if (isApprovalConfirmed && selectedToken && purchaseAmount) {
      completePurchase();
    }
  }, [isApprovalConfirmed]);

  const completePurchase = async () => {
    if (!selectedToken || !purchaseAmount) return;

    try {
      // Llamar al backend para registrar la compra
      await blockchainAPI.purchaseTokens({
        token_id: selectedToken.id,
        cantidad: parseFloat(purchaseAmount),
      });

      toast({
        title: "Compra exitosa",
        description: `Has adquirido ${purchaseAmount} tokens de ${selectedToken.simbolo}`,
      });

      setPurchaseTokenOpen(false);
      setSelectedToken(null);
      setPurchaseAmount("");
      loadData();
      refetchBalances();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "No se pudo completar la compra",
        variant: "destructive",
      });
    } finally {
      setPurchasing(false);
    }
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

  const getCurrentChainInfo = () => {
    return SUPPORTED_CHAINS.find((c) => c.chain.id === chainId);
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
  const currentChain = getCurrentChainInfo();
  const isWalletLinked = address && wallets.some(
    (w) => w.address.toLowerCase() === address.toLowerCase()
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Blockchain"
        description="Conecta tu wallet y gestiona inversiones on-chain"
        backHref="/dashboard"
        actions={
          <div className="flex items-center gap-3">
            <Button onClick={refreshData} variant="outline" disabled={refreshing}>
              <RefreshCw
                className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`}
              />
              Actualizar
            </Button>
            <ConnectWallet showBalance showNetwork />
          </div>
        }
      />

      {/* Connected Wallet Info Card */}
      {isConnected && (
        <Card className="border-primary/20 bg-gradient-to-r from-primary/5 to-transparent">
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <Wallet className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-lg font-semibold">
                      {formatAddress(address!)}
                    </span>
                    <button
                      onClick={() => copyToClipboard(address!)}
                      className="text-muted-foreground hover:text-primary"
                    >
                      <Copy className="h-4 w-4" />
                    </button>
                    <a
                      href={getExplorerUrl(chainId, "address", address!)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-primary"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                    {isWalletLinked ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                        <Shield className="h-3 w-3" />
                        Verificada
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">
                        <AlertTriangle className="h-3 w-3" />
                        No vinculada
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {currentChain?.name} ({currentChain?.isTestnet ? "Testnet" : "Mainnet"})
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-6">
                <div className="text-center">
                  <p className="text-sm text-muted-foreground">{nativeSymbol}</p>
                  <p className="text-xl font-bold">{nativeBalance.toFixed(4)}</p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-muted-foreground">USDC</p>
                  <p className="text-xl font-bold">${usdcBalance.toFixed(2)}</p>
                </div>
                {!isWalletLinked && (
                  <Button onClick={() => setLinkWalletOpen(true)}>
                    <Link2 className="h-4 w-4 mr-2" />
                    Vincular
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Not Connected Banner */}
      {!isConnected && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-yellow-100 flex items-center justify-center">
                <Wallet className="h-6 w-6 text-yellow-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-yellow-800">
                  Conecta tu Wallet
                </h3>
                <p className="text-sm text-yellow-700">
                  Para invertir en proyectos y gestionar tus tokens, necesitas conectar una wallet compatible (MetaMask, WalletConnect, etc.)
                </p>
              </div>
              <ConnectWallet />
            </div>
          </CardContent>
        </Card>
      )}

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
                <p className="text-sm text-muted-foreground">Wallets Vinculadas</p>
                <p className="text-2xl font-bold">{wallets.filter(w => w.is_verified).length}</p>
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
              <CardDescription>
                Redes soportadas por FinCore para inversiones tokenizadas
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {SUPPORTED_CHAINS.map((chainInfo) => {
                  const networkStatus = networks.find(
                    (n) => n.chain_id === chainInfo.chain.id
                  );
                  const isCurrentChain = chainId === chainInfo.chain.id;

                  return (
                    <div
                      key={chainInfo.chain.id}
                      className={`p-4 border rounded-lg space-y-3 ${
                        isCurrentChain ? "border-primary bg-primary/5" : ""
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div
                            className={`h-3 w-3 rounded-full ${
                              networkStatus?.is_connected
                                ? "bg-green-500"
                                : "bg-red-500"
                            }`}
                          />
                          <span className="font-medium">{chainInfo.name}</span>
                          {chainInfo.isTestnet && (
                            <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded">
                              Testnet
                            </span>
                          )}
                          {isCurrentChain && (
                            <span className="px-1.5 py-0.5 bg-primary/10 text-primary text-xs rounded">
                              Actual
                            </span>
                          )}
                        </div>
                        <a
                          href={chainInfo.chain.blockExplorers?.default.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-muted-foreground hover:text-primary"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </div>

                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Chain ID:</span>
                          <span className="font-mono">{chainInfo.chain.id}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Moneda:</span>
                          <span className="font-mono">{chainInfo.symbol}</span>
                        </div>
                        {networkStatus?.current_block && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Bloque:</span>
                            <span className="font-mono">
                              {networkStatus.current_block.toLocaleString()}
                            </span>
                          </div>
                        )}
                      </div>

                      {isConnected && !isCurrentChain && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full"
                          onClick={() => switchChain({ chainId: chainInfo.chain.id })}
                        >
                          <Zap className="h-4 w-4 mr-2" />
                          Cambiar a {chainInfo.name}
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Wallets Tab */}
        <TabsContent value="wallets">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Mis Wallets</CardTitle>
                <CardDescription>
                  Wallets vinculadas a tu cuenta de FinCore
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {wallets.length > 0 ? (
                <div className="space-y-3">
                  {wallets.map((wallet) => (
                    <div
                      key={wallet.id}
                      className={`flex items-center justify-between p-4 border rounded-lg hover:bg-slate-50 ${
                        address?.toLowerCase() === wallet.address.toLowerCase()
                          ? "border-primary bg-primary/5"
                          : ""
                      }`}
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
                            {address?.toLowerCase() === wallet.address.toLowerCase() && (
                              <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
                                Conectada
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <span className="font-mono">
                              {formatAddress(wallet.address)}
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
                        <span className="text-sm text-muted-foreground capitalize">
                          {wallet.network.replace("_", " ")}
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
                  <p className="text-muted-foreground mb-2">
                    No tienes wallets vinculadas
                  </p>
                  <p className="text-sm text-muted-foreground mb-4">
                    Conecta tu wallet y vinculala para invertir en proyectos
                  </p>
                  {!isConnected && <ConnectWallet />}
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
              <CardDescription>
                Tokens disponibles para inversion
              </CardDescription>
            </CardHeader>
            <CardContent>
              {tokens.length > 0 ? (
                <div className="space-y-3">
                  {tokens.map((token) => {
                    const progress = (token.supply_vendido / token.supply_total) * 100;

                    return (
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
                        <div className="flex items-center gap-4">
                          <div className="text-right">
                            <p className="font-medium">
                              {formatCurrency(token.precio_por_token)}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {token.supply_vendido.toLocaleString()} /{" "}
                              {token.supply_total.toLocaleString()}
                            </p>
                            <Progress value={progress} className="w-32 h-2 mt-1" />
                          </div>
                          {token.is_active && isConnected && isWalletLinked && (
                            <Button
                              size="sm"
                              onClick={() => {
                                setSelectedToken(token);
                                setPurchaseTokenOpen(true);
                              }}
                            >
                              Comprar
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
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
              <CardDescription>
                Transacciones on-chain de tu cuenta
              </CardDescription>
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
                                href={getExplorerUrl(
                                  SUPPORTED_CHAINS.find(
                                    (c) => CHAIN_TO_NETWORK[c.chain.id] === tx.network
                                  )?.chain.id || polygon.id,
                                  "tx",
                                  tx.tx_hash
                                )}
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

      {/* Link Wallet Dialog */}
      <AlertDialog open={linkWalletOpen} onOpenChange={setLinkWalletOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Vincular Wallet a FinCore</AlertDialogTitle>
            <AlertDialogDescription>
              Para invertir en proyectos, necesitas vincular tu wallet a tu cuenta.
              Esto requiere firmar un mensaje para verificar que eres el propietario.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <div className="flex items-center gap-3 p-3 bg-slate-100 rounded-lg">
              <Wallet className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm font-medium">Wallet Conectada</p>
                <p className="text-xs font-mono text-muted-foreground">
                  {address ? formatAddress(address) : "..."}
                </p>
              </div>
            </div>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={handleLinkWallet} disabled={linkingWallet}>
              {linkingWallet ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Firmando...
                </>
              ) : (
                <>
                  <Shield className="h-4 w-4 mr-2" />
                  Firmar y Vincular
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Purchase Token Dialog */}
      <Dialog open={purchaseTokenOpen} onOpenChange={setPurchaseTokenOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Comprar Tokens</DialogTitle>
            <DialogDescription>
              Adquiere tokens del proyecto {selectedToken?.nombre}
            </DialogDescription>
          </DialogHeader>
          {selectedToken && (
            <div className="space-y-4">
              <div className="p-4 bg-slate-100 rounded-lg">
                <div className="flex justify-between mb-2">
                  <span className="text-sm text-muted-foreground">Token</span>
                  <span className="font-medium">
                    {selectedToken.nombre} ({selectedToken.simbolo})
                  </span>
                </div>
                <div className="flex justify-between mb-2">
                  <span className="text-sm text-muted-foreground">
                    Precio por token
                  </span>
                  <span className="font-medium">
                    {formatCurrency(selectedToken.precio_por_token)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">
                    Tu balance USDC
                  </span>
                  <span className="font-medium">${usdcBalance.toFixed(2)}</span>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="amount">Cantidad de Tokens</Label>
                <Input
                  id="amount"
                  type="number"
                  placeholder="100"
                  value={purchaseAmount}
                  onChange={(e) => setPurchaseAmount(e.target.value)}
                  min="1"
                  max={selectedToken.supply_total - selectedToken.supply_vendido}
                />
                {purchaseAmount && (
                  <p className="text-sm text-muted-foreground">
                    Total:{" "}
                    <span className="font-medium">
                      {formatCurrency(
                        parseFloat(purchaseAmount) * selectedToken.precio_por_token
                      )}
                    </span>
                  </p>
                )}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setPurchaseTokenOpen(false);
                setSelectedToken(null);
                setPurchaseAmount("");
              }}
            >
              Cancelar
            </Button>
            <Button
              onClick={handlePurchaseToken}
              disabled={
                !purchaseAmount ||
                parseFloat(purchaseAmount) <= 0 ||
                purchasing ||
                isApproving ||
                isApprovalConfirming
              }
            >
              {isApproving || isApprovalConfirming ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  {isApproving ? "Aprobando..." : "Confirmando..."}
                </>
              ) : (
                <>
                  <Coins className="h-4 w-4 mr-2" />
                  Comprar Tokens
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
