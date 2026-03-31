"use client";

import { useState, useEffect, useMemo } from "react";
import {
  ArrowUpRight,
  AlertTriangle,
  Shield,
  Clock,
  Plus,
  Trash2,
  CheckCircle2,
  Loader2,
  Info,
  Lock,
  Wallet as WalletIcon,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  useWallets,
  useConsolidatedBalances,
  useWithdrawalFeeEstimate,
  useWithdraw,
  formatAddress,
  type WithdrawalRequest,
} from "@/features/wallet/hooks/use-wallet";
import {
  useWhitelistAddresses,
  useAddWhitelistAddress,
  useDeleteWhitelistAddress,
  useSecuritySummary,
  type WithdrawalWhitelistAddress,
} from "@/features/security/hooks/use-security";
import { cn, formatCurrency } from "@/lib/utils";

const NETWORK_OPTIONS = [
  { value: "polygon", label: "Polygon", symbol: "MATIC" },
  { value: "ethereum", label: "Ethereum", symbol: "ETH" },
  { value: "arbitrum", label: "Arbitrum", symbol: "ETH" },
  { value: "base", label: "Base", symbol: "ETH" },
];

const MFA_THRESHOLD_USD = 100;

export default function WithdrawPage() {
  const [selectedNetwork, setSelectedNetwork] = useState("polygon");
  const [selectedWalletId, setSelectedWalletId] = useState<string>("");
  const [selectedAddressId, setSelectedAddressId] = useState<string>("");
  const [amount, setAmount] = useState<string>("");
  const [mfaCode, setMfaCode] = useState<string>("");
  const [showMfaInput, setShowMfaInput] = useState(false);
  const [showAddAddressDialog, setShowAddAddressDialog] = useState(false);

  // Queries
  const { data: wallets = [] } = useWallets();
  const { data: balances } = useConsolidatedBalances();
  const { data: whitelist } = useWhitelistAddresses();
  const { data: securitySummary } = useSecuritySummary();

  // Mutations
  const withdrawMutation = useWithdraw();
  const addAddressMutation = useAddWhitelistAddress();
  const deleteAddressMutation = useDeleteWhitelistAddress();

  // Filtrar wallets custodiales
  const custodialWallets = useMemo(
    () => wallets.filter((w) => w.is_custodial),
    [wallets]
  );

  // Filtrar direcciones activas de la whitelist para la red seleccionada
  const activeAddresses = useMemo(
    () =>
      whitelist?.addresses.filter(
        (a) =>
          a.network === selectedNetwork &&
          a.status === "active" &&
          !a.is_in_quarantine
      ) || [],
    [whitelist, selectedNetwork]
  );

  // Direcciones en cuarentena
  const quarantineAddresses = useMemo(
    () =>
      whitelist?.addresses.filter(
        (a) => a.network === selectedNetwork && a.is_in_quarantine
      ) || [],
    [whitelist, selectedNetwork]
  );

  // Obtener balance de la wallet seleccionada
  const selectedWalletBalance = useMemo(() => {
    if (!selectedWalletId || !balances) return null;
    return balances.wallets.find((w) => w.wallet_id === selectedWalletId);
  }, [selectedWalletId, balances]);

  // Monto numerico
  const numericAmount = parseFloat(amount) || 0;

  // Estimar fees
  const { data: feeEstimate, isLoading: feeLoading } = useWithdrawalFeeEstimate({
    network: selectedNetwork,
    amount: numericAmount,
  });

  // Verificar si necesita MFA
  const requiresMfa = useMemo(() => {
    if (!feeEstimate) return false;
    return feeEstimate.estimated_usd >= MFA_THRESHOLD_USD;
  }, [feeEstimate]);

  // Validar formulario
  const isFormValid = useMemo(() => {
    if (!selectedWalletId) return false;
    if (!selectedAddressId) return false;
    if (numericAmount <= 0) return false;
    if (!selectedWalletBalance) return false;
    if (numericAmount > selectedWalletBalance.native_balance) return false;
    if (requiresMfa && mfaCode.length !== 6) return false;
    return true;
  }, [
    selectedWalletId,
    selectedAddressId,
    numericAmount,
    selectedWalletBalance,
    requiresMfa,
    mfaCode,
  ]);

  // Seleccionar primera wallet custodial por defecto
  useEffect(() => {
    if (custodialWallets.length > 0 && !selectedWalletId) {
      setSelectedWalletId(custodialWallets[0].id);
    }
  }, [custodialWallets, selectedWalletId]);

  // Mostrar input MFA si es necesario
  useEffect(() => {
    setShowMfaInput(requiresMfa);
  }, [requiresMfa]);

  const handleWithdraw = async () => {
    const selectedAddress = activeAddresses.find((a) => a.id === selectedAddressId);
    if (!selectedAddress) return;

    const request: WithdrawalRequest = {
      wallet_id: selectedWalletId,
      to_address: selectedAddress.address,
      amount: numericAmount,
      network: selectedNetwork,
      ...(requiresMfa && { mfa_code: mfaCode }),
    };

    try {
      const result = await withdrawMutation.mutateAsync(request);
      if (result.success) {
        toast.success("Retiro iniciado correctamente", {
          description: `TX: ${result.tx_hash?.slice(0, 16)}...`,
        });
        // Reset form
        setAmount("");
        setMfaCode("");
        setSelectedAddressId("");
      } else {
        toast.error(result.error || "Error al procesar el retiro");
      }
    } catch {
      toast.error("Error al procesar el retiro");
    }
  };

  const selectedNetworkInfo = NETWORK_OPTIONS.find((n) => n.value === selectedNetwork);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ArrowUpRight className="h-6 w-6" />
            Retirar Crypto
          </h1>
          <p className="text-muted-foreground">
            Retira criptomonedas a direcciones verificadas
          </p>
        </div>
        <Link href="/wallet">
          <Button variant="outline">Volver a Wallet</Button>
        </Link>
      </div>

      {/* Alerta de cuenta congelada */}
      {securitySummary?.is_frozen && (
        <Alert variant="destructive">
          <Lock className="h-4 w-4" />
          <AlertTitle>Cuenta congelada</AlertTitle>
          <AlertDescription>
            Tu cuenta esta congelada. Los retiros estan deshabilitados hasta que
            desbloquees tu cuenta desde la seccion de seguridad.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Formulario de retiro */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Detalles del Retiro</CardTitle>
              <CardDescription>
                Selecciona la wallet origen y la direccion de destino
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Red */}
              <div className="space-y-2">
                <Label>Red</Label>
                <Select value={selectedNetwork} onValueChange={(v) => {
                  setSelectedNetwork(v);
                  setSelectedAddressId("");
                }}>
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

              {/* Wallet origen */}
              <div className="space-y-2">
                <Label>Wallet origen</Label>
                {custodialWallets.length === 0 ? (
                  <Alert>
                    <WalletIcon className="h-4 w-4" />
                    <AlertDescription>
                      No tienes wallets custodiales. Crea una desde la pagina de Wallet.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Select value={selectedWalletId} onValueChange={setSelectedWalletId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Selecciona una wallet" />
                    </SelectTrigger>
                    <SelectContent>
                      {custodialWallets.map((wallet) => {
                        const balance = balances?.wallets.find(
                          (w) => w.wallet_id === wallet.id
                        );
                        return (
                          <SelectItem key={wallet.id} value={wallet.id}>
                            <div className="flex items-center justify-between gap-4 w-full">
                              <span>{wallet.label || formatAddress(wallet.address)}</span>
                              <span className="text-muted-foreground">
                                {balance?.native_balance.toFixed(4) || "0"}{" "}
                                {selectedNetworkInfo?.symbol}
                              </span>
                            </div>
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                )}
                {selectedWalletBalance && (
                  <p className="text-sm text-muted-foreground">
                    Balance disponible:{" "}
                    <strong>
                      {selectedWalletBalance.native_balance.toFixed(6)}{" "}
                      {selectedNetworkInfo?.symbol}
                    </strong>
                  </p>
                )}
              </div>

              {/* Direccion destino (whitelist) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Direccion destino</Label>
                  <Dialog open={showAddAddressDialog} onOpenChange={setShowAddAddressDialog}>
                    <DialogTrigger asChild>
                      <Button variant="ghost" size="sm">
                        <Plus className="h-4 w-4 mr-1" />
                        Nueva direccion
                      </Button>
                    </DialogTrigger>
                    <AddAddressDialog
                      network={selectedNetwork}
                      onAdd={async (data) => {
                        try {
                          await addAddressMutation.mutateAsync(data);
                          toast.success("Direccion agregada", {
                            description: "Estara disponible en 24 horas",
                          });
                          setShowAddAddressDialog(false);
                        } catch {
                          toast.error("Error al agregar direccion");
                        }
                      }}
                      isLoading={addAddressMutation.isPending}
                    />
                  </Dialog>
                </div>

                {activeAddresses.length === 0 ? (
                  <Alert>
                    <Shield className="h-4 w-4" />
                    <AlertDescription>
                      No tienes direcciones verificadas para esta red.
                      {quarantineAddresses.length > 0 && (
                        <span className="block mt-1">
                          Tienes {quarantineAddresses.length} direccion(es) en periodo de
                          cuarentena (24h).
                        </span>
                      )}
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Select value={selectedAddressId} onValueChange={setSelectedAddressId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Selecciona una direccion" />
                    </SelectTrigger>
                    <SelectContent>
                      {activeAddresses.map((addr) => (
                        <SelectItem key={addr.id} value={addr.id}>
                          <div className="flex flex-col">
                            <span className="font-medium">{addr.label || "Sin etiqueta"}</span>
                            <code className="text-xs text-muted-foreground">
                              {formatAddress(addr.address, 8)}
                            </code>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              {/* Monto */}
              <div className="space-y-2">
                <Label>Monto a retirar</Label>
                <div className="relative">
                  <Input
                    type="number"
                    step="0.000001"
                    min="0"
                    placeholder="0.00"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="pr-16"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    {selectedNetworkInfo?.symbol}
                  </span>
                </div>
                {selectedWalletBalance && numericAmount > selectedWalletBalance.native_balance && (
                  <p className="text-sm text-destructive">Balance insuficiente</p>
                )}
                {selectedWalletBalance && (
                  <Button
                    variant="link"
                    size="sm"
                    className="px-0 h-auto text-xs"
                    onClick={() =>
                      setAmount(selectedWalletBalance.native_balance.toString())
                    }
                  >
                    Usar maximo
                  </Button>
                )}
              </div>

              {/* Estimacion de fees */}
              {numericAmount > 0 && (
                <div className="p-4 rounded-lg bg-muted space-y-2 text-sm">
                  {feeLoading ? (
                    <div className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Calculando fees...</span>
                    </div>
                  ) : feeEstimate ? (
                    <>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Fee de red</span>
                        <span>
                          {feeEstimate.network_fee.toFixed(6)} {feeEstimate.fee_currency}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Fee de plataforma (0.1%)</span>
                        <span>
                          {feeEstimate.platform_fee.toFixed(6)} {feeEstimate.fee_currency}
                        </span>
                      </div>
                      <div className="flex justify-between border-t pt-2">
                        <span className="font-medium">Total fees</span>
                        <span className="font-medium">
                          {feeEstimate.total_fee.toFixed(6)} {feeEstimate.fee_currency}
                        </span>
                      </div>
                      <div className="flex justify-between text-green-600">
                        <span>Recibiras</span>
                        <span className="font-medium">
                          {feeEstimate.net_amount.toFixed(6)} {feeEstimate.fee_currency}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground pt-2">
                        Valor estimado: {formatCurrency(feeEstimate.estimated_usd, "USD")}
                      </p>
                    </>
                  ) : null}
                </div>
              )}

              {/* MFA si es requerido */}
              {showMfaInput && (
                <div className="space-y-2">
                  <Label className="flex items-center gap-2">
                    <Shield className="h-4 w-4" />
                    Codigo MFA (requerido para retiros &gt; $100 USD)
                  </Label>
                  <Input
                    type="text"
                    maxLength={6}
                    placeholder="000000"
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ""))}
                    className="font-mono text-center text-lg tracking-widest"
                  />
                </div>
              )}

              {/* Boton de retiro */}
              <Button
                className="w-full"
                size="lg"
                onClick={handleWithdraw}
                disabled={
                  !isFormValid ||
                  withdrawMutation.isPending ||
                  securitySummary?.is_frozen
                }
              >
                {withdrawMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Procesando...
                  </>
                ) : (
                  <>
                    <ArrowUpRight className="h-4 w-4 mr-2" />
                    Retirar {numericAmount > 0 ? `${numericAmount} ${selectedNetworkInfo?.symbol}` : ""}
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Panel lateral - Whitelist */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Direcciones Verificadas
              </CardTitle>
              <CardDescription>
                Solo puedes retirar a direcciones en tu whitelist
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Direcciones activas */}
              {activeAddresses.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-green-600 flex items-center gap-1">
                    <CheckCircle2 className="h-4 w-4" />
                    Activas ({activeAddresses.length})
                  </h4>
                  {activeAddresses.map((addr) => (
                    <WhitelistAddressCard
                      key={addr.id}
                      address={addr}
                      onDelete={() => deleteAddressMutation.mutate(addr.id)}
                      isDeleting={deleteAddressMutation.isPending}
                    />
                  ))}
                </div>
              )}

              {/* Direcciones en cuarentena */}
              {quarantineAddresses.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-yellow-600 flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    En cuarentena ({quarantineAddresses.length})
                  </h4>
                  {quarantineAddresses.map((addr) => (
                    <WhitelistAddressCard
                      key={addr.id}
                      address={addr}
                      onDelete={() => deleteAddressMutation.mutate(addr.id)}
                      isDeleting={deleteAddressMutation.isPending}
                    />
                  ))}
                </div>
              )}

              {activeAddresses.length === 0 && quarantineAddresses.length === 0 && (
                <div className="text-center py-6">
                  <Shield className="h-10 w-10 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">
                    No hay direcciones para esta red
                  </p>
                </div>
              )}

              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription className="text-xs">
                  Las nuevas direcciones tienen un periodo de cuarentena de 24 horas
                  antes de poder usarlas. Esta es una medida de seguridad para
                  proteger tus fondos.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// Componente de tarjeta de direccion whitelist
interface WhitelistAddressCardProps {
  address: WithdrawalWhitelistAddress;
  onDelete: () => void;
  isDeleting: boolean;
}

function WhitelistAddressCard({ address, onDelete, isDeleting }: WhitelistAddressCardProps) {
  const timeRemaining = useMemo(() => {
    if (!address.quarantine_ends_at) return null;
    const end = new Date(address.quarantine_ends_at);
    const now = new Date();
    const diff = end.getTime() - now.getTime();
    if (diff <= 0) return null;
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${minutes}m`;
  }, [address.quarantine_ends_at]);

  return (
    <div className="p-3 rounded-lg border bg-card">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-sm truncate">
            {address.label || "Sin etiqueta"}
          </p>
          <code className="text-xs text-muted-foreground break-all">
            {formatAddress(address.address, 8)}
          </code>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-destructive hover:text-destructive"
          onClick={onDelete}
          disabled={isDeleting}
        >
          {isDeleting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
        </Button>
      </div>
      {address.is_in_quarantine && timeRemaining && (
        <div className="mt-2 flex items-center gap-1 text-xs text-yellow-600">
          <Clock className="h-3 w-3" />
          Disponible en {timeRemaining}
        </div>
      )}
    </div>
  );
}

// Dialog para agregar nueva direccion
interface AddAddressDialogProps {
  network: string;
  onAdd: (data: { address: string; network: string; label?: string }) => Promise<void>;
  isLoading: boolean;
}

function AddAddressDialog({ network, onAdd, isLoading }: AddAddressDialogProps) {
  const [address, setAddress] = useState("");
  const [label, setLabel] = useState("");

  const isValidAddress = /^0x[a-fA-F0-9]{40}$/.test(address);

  const handleSubmit = async () => {
    await onAdd({
      address: address.toLowerCase(),
      network,
      label: label || undefined,
    });
    setAddress("");
    setLabel("");
  };

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Agregar direccion a whitelist</DialogTitle>
        <DialogDescription>
          La direccion tendra un periodo de cuarentena de 24 horas antes de poder
          usarla para retiros.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label>Direccion</Label>
          <Input
            placeholder="0x..."
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="font-mono"
          />
          {address && !isValidAddress && (
            <p className="text-sm text-destructive">Direccion invalida</p>
          )}
        </div>

        <div className="space-y-2">
          <Label>Etiqueta (opcional)</Label>
          <Input
            placeholder="Mi wallet personal"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>

        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Red seleccionada:{" "}
            <strong>{NETWORK_OPTIONS.find((n) => n.value === network)?.label}</strong>.
            Asegurate de que la direccion sea compatible con esta red.
          </AlertDescription>
        </Alert>
      </div>

      <DialogFooter>
        <Button
          onClick={handleSubmit}
          disabled={!isValidAddress || isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Agregando...
            </>
          ) : (
            "Agregar direccion"
          )}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
