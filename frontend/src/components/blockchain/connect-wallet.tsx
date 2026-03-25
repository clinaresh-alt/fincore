"use client";

import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount, useBalance, useChainId, useSwitchChain } from "wagmi";
import { polygon } from "wagmi/chains";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Wallet, ChevronDown, Copy, ExternalLink, LogOut } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { formatAddress, getExplorerUrl, USDC_ADDRESSES, USDC_ABI } from "@/lib/wagmi";
import { useReadContract } from "wagmi";

interface ConnectWalletProps {
  showBalance?: boolean;
  showNetwork?: boolean;
  variant?: "default" | "compact";
}

export function ConnectWallet({
  showBalance = true,
  showNetwork = true,
  variant = "default",
}: ConnectWalletProps) {
  // Si es default, usamos el boton de RainbowKit con customizacion
  if (variant === "default") {
    return (
      <ConnectButton.Custom>
        {({
          account,
          chain,
          openAccountModal,
          openChainModal,
          openConnectModal,
          mounted,
        }) => {
          const ready = mounted;
          const connected = ready && account && chain;

          return (
            <div
              {...(!ready && {
                "aria-hidden": true,
                style: {
                  opacity: 0,
                  pointerEvents: "none",
                  userSelect: "none",
                },
              })}
            >
              {(() => {
                if (!connected) {
                  return (
                    <Button onClick={openConnectModal}>
                      <Wallet className="h-4 w-4 mr-2" />
                      Conectar Wallet
                    </Button>
                  );
                }

                if (chain.unsupported) {
                  return (
                    <Button variant="destructive" onClick={openChainModal}>
                      Red no soportada
                    </Button>
                  );
                }

                return (
                  <div className="flex items-center gap-2">
                    {showNetwork && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={openChainModal}
                        className="hidden sm:flex"
                      >
                        {chain.hasIcon && chain.iconUrl && (
                          <img
                            src={chain.iconUrl}
                            alt={chain.name ?? "Chain icon"}
                            className="h-4 w-4 mr-2 rounded-full"
                          />
                        )}
                        {chain.name}
                        <ChevronDown className="h-3 w-3 ml-1" />
                      </Button>
                    )}

                    <Button onClick={openAccountModal}>
                      {showBalance && account.displayBalance && (
                        <span className="mr-2 hidden sm:inline">
                          {account.displayBalance}
                        </span>
                      )}
                      <Wallet className="h-4 w-4 mr-2 sm:mr-0 sm:hidden" />
                      <span>{account.displayName}</span>
                    </Button>
                  </div>
                );
              })()}
            </div>
          );
        }}
      </ConnectButton.Custom>
    );
  }

  // Variante compacta personalizada
  return <CompactWalletButton />;
}

// Componente compacto para mostrar en la barra lateral o header
function CompactWalletButton() {
  const { address, isConnected } = useAccount();
  const chainId = useChainId();
  const { toast } = useToast();

  // Balance nativo (ETH/MATIC)
  const { data: nativeBalance } = useBalance({
    address: address,
  });

  // Balance USDC
  const usdcAddress = USDC_ADDRESSES[chainId];
  const { data: usdcBalance } = useReadContract({
    address: usdcAddress,
    abi: USDC_ABI,
    functionName: "balanceOf",
    args: address ? [address] : undefined,
  });

  const copyAddress = () => {
    if (address) {
      navigator.clipboard.writeText(address);
      toast({
        title: "Direccion copiada",
        description: "La direccion de tu wallet ha sido copiada al portapapeles",
      });
    }
  };

  const viewOnExplorer = () => {
    if (address) {
      window.open(getExplorerUrl(chainId, "address", address), "_blank");
    }
  };

  if (!isConnected) {
    return (
      <ConnectButton.Custom>
        {({ openConnectModal, mounted }) => (
          <Button
            onClick={openConnectModal}
            disabled={!mounted}
            size="sm"
            className="w-full"
          >
            <Wallet className="h-4 w-4 mr-2" />
            Conectar
          </Button>
        )}
      </ConnectButton.Custom>
    );
  }

  const formattedUsdcBalance = usdcBalance
    ? (Number(usdcBalance) / 1e6).toFixed(2)
    : "0.00";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="w-full justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span className="font-mono text-xs">
              {address ? formatAddress(address) : "..."}
            </span>
          </div>
          <ChevronDown className="h-3 w-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Mi Wallet</DropdownMenuLabel>
        <DropdownMenuSeparator />

        <div className="px-2 py-2 space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">
              {nativeBalance?.symbol || "ETH"}
            </span>
            <span className="font-mono">
              {nativeBalance
                ? parseFloat(nativeBalance.formatted).toFixed(4)
                : "0.0000"}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">USDC</span>
            <span className="font-mono">${formattedUsdcBalance}</span>
          </div>
        </div>

        <DropdownMenuSeparator />

        <DropdownMenuItem onClick={copyAddress}>
          <Copy className="h-4 w-4 mr-2" />
          Copiar direccion
        </DropdownMenuItem>

        <DropdownMenuItem onClick={viewOnExplorer}>
          <ExternalLink className="h-4 w-4 mr-2" />
          Ver en explorador
        </DropdownMenuItem>

        <DropdownMenuSeparator />

        <ConnectButton.Custom>
          {({ openAccountModal }) => (
            <DropdownMenuItem onClick={openAccountModal}>
              <LogOut className="h-4 w-4 mr-2" />
              Desconectar
            </DropdownMenuItem>
          )}
        </ConnectButton.Custom>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// Hook para usar la wallet conectada en otros componentes
export function useConnectedWallet() {
  const { address, isConnected, isConnecting, isDisconnected } = useAccount();
  const chainId = useChainId();
  const { switchChain } = useSwitchChain();

  const { data: nativeBalance, refetch: refetchNativeBalance } = useBalance({
    address: address,
  });

  const usdcAddress = USDC_ADDRESSES[chainId];
  const { data: usdcBalance, refetch: refetchUsdcBalance } = useReadContract({
    address: usdcAddress,
    abi: USDC_ABI,
    functionName: "balanceOf",
    args: address ? [address] : undefined,
  });

  const refetchBalances = async () => {
    await Promise.all([refetchNativeBalance(), refetchUsdcBalance()]);
  };

  const switchToPolygon = () => {
    switchChain({ chainId: polygon.id });
  };

  return {
    address,
    isConnected,
    isConnecting,
    isDisconnected,
    chainId,
    nativeBalance: nativeBalance
      ? parseFloat(nativeBalance.formatted)
      : 0,
    nativeSymbol: nativeBalance?.symbol || "ETH",
    usdcBalance: usdcBalance ? Number(usdcBalance) / 1e6 : 0,
    refetchBalances,
    switchChain,
    switchToPolygon,
  };
}
