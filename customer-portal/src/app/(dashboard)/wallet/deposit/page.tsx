"use client";

import { useState } from "react";
import {
  ArrowDownLeft,
  Copy,
  Check,
  AlertTriangle,
  RefreshCw,
  Clock,
  CheckCircle2,
  ExternalLink,
  QrCode,
  Info,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  useDepositAddress,
  useDepositHistory,
  useNetworks,
  formatAddress,
  getExplorerLink,
  type DepositHistoryItem,
} from "@/features/wallet/hooks/use-wallet";
import { cn, formatCurrency } from "@/lib/utils";

const NETWORK_OPTIONS = [
  { value: "polygon", label: "Polygon", symbol: "MATIC" },
  { value: "ethereum", label: "Ethereum", symbol: "ETH" },
  { value: "arbitrum", label: "Arbitrum", symbol: "ETH" },
  { value: "base", label: "Base", symbol: "ETH" },
];

export default function DepositPage() {
  const [selectedNetwork, setSelectedNetwork] = useState("polygon");
  const [copiedAddress, setCopiedAddress] = useState(false);

  const { data: depositAddress, isLoading: addressLoading, refetch } = useDepositAddress(selectedNetwork);
  const { data: history, isLoading: historyLoading } = useDepositHistory({ limit: 10 });
  const { data: networks = [] } = useNetworks();

  const selectedNetworkInfo = NETWORK_OPTIONS.find((n) => n.value === selectedNetwork);

  const handleCopyAddress = async () => {
    if (!depositAddress?.address) return;
    await navigator.clipboard.writeText(depositAddress.address);
    setCopiedAddress(true);
    toast.success("Direccion copiada al portapapeles");
    setTimeout(() => setCopiedAddress(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ArrowDownLeft className="h-6 w-6" />
            Depositar Crypto
          </h1>
          <p className="text-muted-foreground">
            Deposita criptomonedas a tu wallet FinCore
          </p>
        </div>
        <Link href="/wallet">
          <Button variant="outline">Volver a Wallet</Button>
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Direccion de deposito */}
        <Card>
          <CardHeader>
            <CardTitle>Direccion de Deposito</CardTitle>
            <CardDescription>
              Envia criptomonedas a esta direccion
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Selector de red */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Red</label>
              <Select value={selectedNetwork} onValueChange={setSelectedNetwork}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecciona una red" />
                </SelectTrigger>
                <SelectContent>
                  {NETWORK_OPTIONS.map((network) => (
                    <SelectItem key={network.value} value={network.value}>
                      <div className="flex items-center gap-2">
                        <span>{network.label}</span>
                        <Badge variant="outline" className="text-xs">
                          {network.symbol}
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Advertencia */}
            {depositAddress?.warning && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{depositAddress.warning}</AlertDescription>
              </Alert>
            )}

            {/* QR y direccion */}
            {addressLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-48 w-48 mx-auto" />
                <Skeleton className="h-12" />
              </div>
            ) : depositAddress ? (
              <div className="space-y-4">
                {/* QR Code */}
                <div className="flex justify-center p-4 bg-white rounded-lg">
                  {depositAddress.qr_code_base64 ? (
                    <Image
                      src={`data:image/png;base64,${depositAddress.qr_code_base64}`}
                      alt="QR Code"
                      width={192}
                      height={192}
                      className="h-48 w-48"
                    />
                  ) : (
                    <div className="h-48 w-48 flex items-center justify-center bg-muted rounded">
                      <QrCode className="h-12 w-12 text-muted-foreground" />
                    </div>
                  )}
                </div>

                {/* Direccion */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Direccion</label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 p-3 bg-muted rounded-lg text-sm font-mono break-all">
                      {depositAddress.address}
                    </code>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleCopyAddress}
                      className="shrink-0"
                    >
                      {copiedAddress ? (
                        <Check className="h-4 w-4 text-green-500" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Info */}
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between p-2 bg-muted/50 rounded">
                    <span className="text-muted-foreground">Deposito minimo</span>
                    <span className="font-medium">
                      {depositAddress.minimum_deposit} {depositAddress.currency_symbol}
                    </span>
                  </div>
                  <div className="flex justify-between p-2 bg-muted/50 rounded">
                    <span className="text-muted-foreground">Confirmaciones requeridas</span>
                    <span className="font-medium">{depositAddress.confirmations_required}</span>
                  </div>
                </div>

                {/* Refresh */}
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => refetch()}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Actualizar
                </Button>
              </div>
            ) : (
              <div className="text-center py-8">
                <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">
                  Error al cargar direccion de deposito
                </p>
                <Button variant="outline" className="mt-4" onClick={() => refetch()}>
                  Reintentar
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Instrucciones e historial */}
        <div className="space-y-6">
          {/* Instrucciones */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Info className="h-5 w-5" />
                Como depositar
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="space-y-3 text-sm">
                <li className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
                    1
                  </span>
                  <span>
                    Selecciona la red que deseas usar (asegurate de que coincida con
                    la red de envio)
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
                    2
                  </span>
                  <span>Copia la direccion de deposito o escanea el codigo QR</span>
                </li>
                <li className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
                    3
                  </span>
                  <span>
                    Envia tus criptomonedas desde tu wallet externa o exchange
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
                    4
                  </span>
                  <span>
                    Espera las confirmaciones necesarias. Tu balance se actualizara
                    automaticamente
                  </span>
                </li>
              </ol>

              <Alert className="mt-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Solo envia <strong>{selectedNetworkInfo?.symbol}</strong> y tokens compatibles
                  en la red <strong>{selectedNetworkInfo?.label}</strong>. Enviar otros activos
                  puede resultar en perdida permanente.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>

          {/* Historial */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg">Depositos Recientes</CardTitle>
                {history && (
                  <CardDescription>
                    Total depositado: {formatCurrency(history.total_deposited_usd, "USD")}
                  </CardDescription>
                )}
              </div>
              {history && history.pending_count > 0 && (
                <Badge variant="secondary">
                  {history.pending_count} pendiente{history.pending_count > 1 ? "s" : ""}
                </Badge>
              )}
            </CardHeader>
            <CardContent>
              {historyLoading ? (
                <div className="space-y-3">
                  {[...Array(3)].map((_, i) => (
                    <Skeleton key={i} className="h-16" />
                  ))}
                </div>
              ) : !history || history.deposits.length === 0 ? (
                <div className="text-center py-8">
                  <Clock className="h-10 w-10 text-muted-foreground mx-auto mb-2" />
                  <p className="text-muted-foreground">No hay depositos recientes</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {history.deposits.map((deposit) => (
                    <DepositRow key={deposit.id} deposit={deposit} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// Componente de fila de deposito
interface DepositRowProps {
  deposit: DepositHistoryItem;
}

function DepositRow({ deposit }: DepositRowProps) {
  const isPending = deposit.status === "pending";
  const isConfirmed = deposit.status === "confirmed";

  return (
    <div className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50 transition-colors">
      <div className="flex items-center gap-3">
        <div
          className={cn(
            "h-10 w-10 rounded-full flex items-center justify-center",
            isConfirmed
              ? "bg-green-100 dark:bg-green-900/30"
              : "bg-yellow-100 dark:bg-yellow-900/30"
          )}
        >
          {isConfirmed ? (
            <CheckCircle2 className="h-5 w-5 text-green-600" />
          ) : (
            <Clock className="h-5 w-5 text-yellow-600" />
          )}
        </div>
        <div>
          <p className="font-medium">
            +{deposit.amount} {deposit.token_symbol}
          </p>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <a
              href={getExplorerLink(deposit.tx_hash, deposit.network)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:text-primary"
            >
              {formatAddress(deposit.tx_hash, 6)}
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>

      <div className="text-right">
        <Badge
          variant={isConfirmed ? "default" : isPending ? "secondary" : "destructive"}
          className="capitalize"
        >
          {deposit.status}
        </Badge>
        <p className="text-xs text-muted-foreground mt-1">
          {deposit.confirmations}/{deposit.confirmations_required} confirmaciones
        </p>
      </div>
    </div>
  );
}
