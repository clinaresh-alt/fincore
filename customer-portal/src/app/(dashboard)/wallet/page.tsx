"use client";

import { useState } from "react";
import {
  Wallet as WalletIcon,
  Plus,
  Copy,
  Check,
  ExternalLink,
  RefreshCw,
  Trash2,
  Shield,
  TrendingUp,
  ArrowUpRight,
  ArrowDownLeft,
  Clock,
  AlertCircle,
  CheckCircle2,
  Coins,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useWallets,
  useWalletBalance,
  usePortfolio,
  useBlockchainTransactions,
  useCreateCustodialWallet,
  formatAddress,
  getExplorerLink,
  getTransactionStatusColor,
  type Wallet,
  type BlockchainTransaction,
} from "@/features/wallet/hooks/use-wallet";
import { cn, formatCurrency } from "@/lib/utils";

export default function WalletPage() {
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null);
  const [selectedWalletId, setSelectedWalletId] = useState<string | null>(null);

  const { data: wallets = [], isLoading: walletsLoading } = useWallets();
  const { data: portfolio = [], isLoading: portfolioLoading } = usePortfolio();
  const { data: transactions = [], isLoading: txLoading } = useBlockchainTransactions({ limit: 10 });
  const createWalletMutation = useCreateCustodialWallet();

  // Seleccionar la primera wallet por defecto
  const activeWallet = selectedWalletId
    ? wallets.find((w) => w.id === selectedWalletId)
    : wallets.find((w) => w.is_primary) || wallets[0];

  const { data: balance, isLoading: balanceLoading } = useWalletBalance(
    activeWallet?.id || "",
    activeWallet?.preferred_network || "polygon"
  );

  // Calcular valor total del portfolio
  const totalPortfolioValue = portfolio.reduce((sum, t) => sum + (t.value_usd || 0), 0);
  const totalPendingDividends = portfolio.reduce((sum, t) => sum + (t.pending_dividends || 0), 0);

  const handleCopyAddress = async (address: string) => {
    await navigator.clipboard.writeText(address);
    setCopiedAddress(address);
    toast.success("Dirección copiada");
    setTimeout(() => setCopiedAddress(null), 2000);
  };

  const handleCreateWallet = async () => {
    try {
      await createWalletMutation.mutateAsync({
        preferred_network: "polygon",
        label: "Mi Wallet FinCore",
      });
      toast.success("Wallet creada exitosamente");
    } catch {
      toast.error("Error al crear wallet");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <WalletIcon className="h-6 w-6" />
            Mi Wallet
          </h1>
          <p className="text-muted-foreground">
            Gestiona tus wallets y tokens
          </p>
        </div>
        <Button onClick={handleCreateWallet} disabled={createWalletMutation.isPending}>
          <Plus className="h-4 w-4 mr-2" />
          Nueva wallet
        </Button>
      </div>

      {/* Wallets Grid */}
      {walletsLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(2)].map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : wallets.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <WalletIcon className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">Sin wallets</h3>
            <p className="text-muted-foreground mb-4">
              Crea tu primera wallet para empezar a operar con crypto
            </p>
            <Button onClick={handleCreateWallet} disabled={createWalletMutation.isPending}>
              <Plus className="h-4 w-4 mr-2" />
              Crear wallet custodial
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {wallets.map((wallet) => (
            <WalletCard
              key={wallet.id}
              wallet={wallet}
              isSelected={activeWallet?.id === wallet.id}
              onSelect={() => setSelectedWalletId(wallet.id)}
              onCopy={handleCopyAddress}
              copiedAddress={copiedAddress}
            />
          ))}
        </div>
      )}

      {/* Balance y Portfolio */}
      {activeWallet && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Balance de Wallet Activa */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-lg">Balance</CardTitle>
              <Badge variant="outline">{activeWallet.preferred_network}</Badge>
            </CardHeader>
            <CardContent>
              {balanceLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-10 w-32" />
                  <Skeleton className="h-20" />
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Balance nativo */}
                  <div>
                    <p className="text-3xl font-bold">
                      {balance?.native_balance?.toFixed(6) || "0.00"}{" "}
                      <span className="text-lg text-muted-foreground">MATIC</span>
                    </p>
                  </div>

                  {/* Tokens */}
                  {balance?.tokens && balance.tokens.length > 0 ? (
                    <div className="space-y-2">
                      <p className="text-sm text-muted-foreground">Tokens</p>
                      {balance.tokens.map((token) => (
                        <div
                          key={token.symbol}
                          className="flex items-center justify-between p-2 rounded-lg bg-muted/50"
                        >
                          <div className="flex items-center gap-2">
                            <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                              <Coins className="h-4 w-4 text-primary" />
                            </div>
                            <div>
                              <p className="font-medium">{token.symbol}</p>
                              <p className="text-xs text-muted-foreground">{token.name}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="font-medium">{token.balance.toFixed(2)}</p>
                            <p className="text-xs text-muted-foreground">
                              {formatCurrency(token.value_usd, "USD")}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No tienes tokens en esta wallet
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Portfolio de inversiones */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-lg">Portfolio de Inversiones</CardTitle>
              <TrendingUp className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {portfolioLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-10 w-32" />
                  <Skeleton className="h-16" />
                </div>
              ) : portfolio.length === 0 ? (
                <div className="text-center py-6">
                  <Coins className="h-10 w-10 text-muted-foreground mx-auto mb-2" />
                  <p className="text-muted-foreground">
                    Aún no tienes inversiones tokenizadas
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Resumen */}
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="text-2xl font-bold">
                        {formatCurrency(totalPortfolioValue, "USD")}
                      </p>
                      <p className="text-sm text-muted-foreground">Valor total</p>
                    </div>
                    {totalPendingDividends > 0 && (
                      <div className="text-right">
                        <p className="text-lg font-semibold text-green-600">
                          +{formatCurrency(totalPendingDividends, "USD")}
                        </p>
                        <p className="text-xs text-muted-foreground">Dividendos pendientes</p>
                      </div>
                    )}
                  </div>

                  {/* Lista de tokens */}
                  <div className="space-y-2">
                    {portfolio.slice(0, 5).map((token) => (
                      <div
                        key={token.token_id}
                        className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50"
                      >
                        <div className="flex items-center gap-2">
                          <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-xs font-bold text-primary">
                            {token.token_symbol.slice(0, 2)}
                          </div>
                          <div>
                            <p className="font-medium">{token.token_name}</p>
                            <p className="text-xs text-muted-foreground">
                              {token.balance.toFixed(2)} {token.token_symbol}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="font-medium">{formatCurrency(token.value_usd, "USD")}</p>
                          {token.pending_dividends > 0 && (
                            <p className="text-xs text-green-600">
                              +{formatCurrency(token.pending_dividends, "USD")}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Historial de transacciones */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Transacciones Recientes</CardTitle>
          <Link href="/wallet/transactions">
            <Button variant="ghost" size="sm">
              Ver todas
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {txLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-16" />
              ))}
            </div>
          ) : transactions.length === 0 ? (
            <div className="text-center py-8">
              <Clock className="h-10 w-10 text-muted-foreground mx-auto mb-2" />
              <p className="text-muted-foreground">
                No hay transacciones recientes
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {transactions.map((tx) => (
                <TransactionRow key={tx.id} transaction={tx} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Componente de tarjeta de wallet
interface WalletCardProps {
  wallet: Wallet;
  isSelected: boolean;
  onSelect: () => void;
  onCopy: (address: string) => void;
  copiedAddress: string | null;
}

function WalletCard({
  wallet,
  isSelected,
  onSelect,
  onCopy,
  copiedAddress,
}: WalletCardProps) {
  return (
    <Card
      className={cn(
        "cursor-pointer transition-all hover:shadow-md",
        isSelected && "ring-2 ring-primary"
      )}
      onClick={onSelect}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <WalletIcon className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="font-medium">{wallet.label || "Mi Wallet"}</p>
              <div className="flex items-center gap-1">
                {wallet.is_primary && (
                  <Badge variant="secondary" className="text-[10px] px-1">
                    Principal
                  </Badge>
                )}
                {wallet.is_custodial && (
                  <Badge variant="outline" className="text-[10px] px-1">
                    <Shield className="h-2.5 w-2.5 mr-0.5" />
                    Custodial
                  </Badge>
                )}
              </div>
            </div>
          </div>
          {wallet.is_verified && (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          )}
        </div>

        <div className="flex items-center justify-between">
          <code className="text-sm text-muted-foreground font-mono">
            {formatAddress(wallet.address)}
          </code>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={(e) => {
              e.stopPropagation();
              onCopy(wallet.address);
            }}
          >
            {copiedAddress === wallet.address ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </Button>
        </div>

        <div className="flex items-center justify-between mt-3 pt-3 border-t">
          <Badge variant="outline" className="text-xs">
            {wallet.preferred_network}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {new Date(wallet.created_at).toLocaleDateString()}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

// Componente de fila de transacción
interface TransactionRowProps {
  transaction: BlockchainTransaction;
}

function TransactionRow({ transaction }: TransactionRowProps) {
  const isIncoming = transaction.tx_type === "receive" || transaction.tx_type === "dividend";
  const statusColor = getTransactionStatusColor(transaction.status);

  const StatusIcon =
    transaction.status === "confirmed"
      ? CheckCircle2
      : transaction.status === "failed"
      ? AlertCircle
      : Clock;

  return (
    <div className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50 transition-colors">
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "h-10 w-10 rounded-full flex items-center justify-center",
            isIncoming ? "bg-green-100 dark:bg-green-900/30" : "bg-blue-100 dark:bg-blue-900/30"
          )}
        >
          {isIncoming ? (
            <ArrowDownLeft className="h-5 w-5 text-green-600" />
          ) : (
            <ArrowUpRight className="h-5 w-5 text-blue-600" />
          )}
        </div>
        <div>
          <p className="font-medium capitalize">{transaction.tx_type.replace("_", " ")}</p>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {transaction.tx_hash && (
              <a
                href={getExplorerLink(transaction.tx_hash, transaction.network)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 hover:text-primary"
                onClick={(e) => e.stopPropagation()}
              >
                {formatAddress(transaction.tx_hash, 4)}
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
            <span>{new Date(transaction.created_at).toLocaleString()}</span>
          </div>
        </div>
      </div>

      <div className="text-right">
        <p className={cn("font-medium", isIncoming ? "text-green-600" : "")}>
          {isIncoming ? "+" : "-"}
          {transaction.amount} {transaction.token_symbol || "MATIC"}
        </p>
        <div className={cn("flex items-center gap-1 text-xs", statusColor)}>
          <StatusIcon className="h-3 w-3" />
          <span className="capitalize">{transaction.status}</span>
        </div>
      </div>
    </div>
  );
}
