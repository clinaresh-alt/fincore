"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// Types
export interface Wallet {
  id: string;
  user_id: string;
  address: string;
  wallet_type: string;
  label: string;
  preferred_network: string;
  is_primary: boolean;
  is_verified: boolean;
  is_custodial: boolean;
  verified_at: string | null;
  created_at: string;
}

export interface TokenBalance {
  symbol: string;
  name: string;
  balance: number;
  value_usd: number;
}

export interface WalletBalance {
  address: string;
  native_balance: number;
  network: string;
  tokens: TokenBalance[];
}

export interface PortfolioToken {
  token_id: string;
  token_name: string;
  token_symbol: string;
  project_id: string;
  balance: number;
  value_usd: number;
  pending_dividends: number;
  last_dividend_at: string | null;
}

export interface BlockchainTransaction {
  id: string;
  tx_hash: string | null;
  tx_type: string;
  status: string;
  from_address: string | null;
  to_address: string | null;
  amount: number;
  token_symbol: string | null;
  network: string;
  gas_used: number | null;
  gas_price: number | null;
  error_message: string | null;
  created_at: string;
  confirmed_at: string | null;
}

export interface NetworkInfo {
  network: string;
  name: string;
  chain_id: number;
  currency_symbol: string;
  block_explorer: string;
  is_testnet: boolean;
  is_connected: boolean;
  current_block: number | null;
}

export interface CreateCustodialWalletInput {
  label?: string;
  preferred_network: string;
}

// ==================== DEPOSIT TYPES ====================

export interface DepositAddress {
  address: string;
  network: string;
  currency_symbol: string;
  qr_code_base64: string | null;
  minimum_deposit: number;
  confirmations_required: number;
  warning: string | null;
}

export interface DepositHistoryItem {
  id: string;
  tx_hash: string;
  amount: number;
  token_symbol: string;
  token_address: string | null;
  network: string;
  status: string;
  confirmations: number;
  confirmations_required: number;
  from_address: string;
  created_at: string;
  confirmed_at: string | null;
}

export interface DepositHistory {
  deposits: DepositHistoryItem[];
  total: number;
  pending_count: number;
  total_deposited_usd: number;
}

// ==================== WITHDRAWAL TYPES ====================

export interface WithdrawalFeeEstimate {
  network_fee: number;
  platform_fee: number;
  total_fee: number;
  net_amount: number;
  fee_currency: string;
  estimated_usd: number;
}

export interface WithdrawalRequest {
  wallet_id: string;
  to_address: string;
  amount: number;
  token_address?: string;
  network: string;
  mfa_code?: string;
}

export interface WithdrawalResponse {
  success: boolean;
  transaction_id: string | null;
  tx_hash: string | null;
  status: string;
  amount: number;
  fee: number;
  net_amount: number;
  to_address: string;
  estimated_confirmation_time: string | null;
  message: string | null;
  error: string | null;
}

// ==================== CONSOLIDATED BALANCE TYPES ====================

export interface ConsolidatedTokenBalance {
  symbol: string;
  name: string;
  contract_address: string | null;
  balance: number;
  balance_usd: number;
  price_usd: number;
  change_24h: number | null;
  logo_url: string | null;
}

export interface WalletConsolidatedBalance {
  wallet_id: string;
  wallet_address: string;
  wallet_label: string | null;
  is_custodial: boolean;
  network: string;
  native_balance: number;
  native_balance_usd: number;
  tokens: ConsolidatedTokenBalance[];
  total_balance_usd: number;
}

export interface ConsolidatedBalance {
  total_balance_usd: number;
  change_24h_usd: number | null;
  change_24h_percent: number | null;
  wallets: WalletConsolidatedBalance[];
  top_assets: ConsolidatedTokenBalance[];
  last_updated: string;
}

// Query keys
export const walletKeys = {
  all: ["wallet"] as const,
  wallets: () => [...walletKeys.all, "list"] as const,
  wallet: (id: string) => [...walletKeys.all, "detail", id] as const,
  balance: (id: string, network: string) => [...walletKeys.all, "balance", id, network] as const,
  portfolio: () => [...walletKeys.all, "portfolio"] as const,
  transactions: (filters?: Record<string, unknown>) => [...walletKeys.all, "transactions", filters] as const,
  networks: () => [...walletKeys.all, "networks"] as const,
  // New keys for deposits/withdrawals
  depositAddress: (network: string) => [...walletKeys.all, "deposit-address", network] as const,
  depositHistory: (filters?: Record<string, unknown>) => [...walletKeys.all, "deposit-history", filters] as const,
  consolidatedBalances: () => [...walletKeys.all, "consolidated-balances"] as const,
  withdrawalFeeEstimate: (params: { network: string; amount: number; token_address?: string }) =>
    [...walletKeys.all, "withdrawal-fee", params] as const,
};

// Hooks

// Lista de wallets del usuario
export function useWallets() {
  return useQuery({
    queryKey: walletKeys.wallets(),
    queryFn: () => apiClient.get<Wallet[]>("/blockchain/wallets"),
  });
}

// Balance de una wallet
export function useWalletBalance(walletId: string, network: string = "polygon") {
  return useQuery({
    queryKey: walletKeys.balance(walletId, network),
    queryFn: () =>
      apiClient.get<WalletBalance>(`/blockchain/wallets/${walletId}/balance`, {
        network,
      }),
    enabled: !!walletId,
  });
}

// Portfolio de tokens
export function usePortfolio() {
  return useQuery({
    queryKey: walletKeys.portfolio(),
    queryFn: () => apiClient.get<PortfolioToken[]>("/blockchain/portfolio"),
  });
}

// Transacciones blockchain
export function useBlockchainTransactions(options?: {
  limit?: number;
  offset?: number;
  status?: string;
}) {
  return useQuery({
    queryKey: walletKeys.transactions(options),
    queryFn: () =>
      apiClient.get<BlockchainTransaction[]>("/blockchain/transactions", {
        limit: options?.limit || 50,
        offset: options?.offset || 0,
        ...(options?.status && { status_filter: options.status }),
      }),
  });
}

// Redes disponibles
export function useNetworks() {
  return useQuery({
    queryKey: walletKeys.networks(),
    queryFn: () => apiClient.get<NetworkInfo[]>("/blockchain/networks"),
    staleTime: 60 * 1000, // 1 minuto
  });
}

// Crear wallet custodial
export function useCreateCustodialWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateCustodialWalletInput) =>
      apiClient.post<Wallet>("/blockchain/wallets/custodial", input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: walletKeys.wallets() });
    },
  });
}

// Eliminar wallet
export function useDeleteWallet() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (walletId: string) =>
      apiClient.delete<void>(`/blockchain/wallets/${walletId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: walletKeys.wallets() });
    },
  });
}

// ==================== DEPOSIT HOOKS ====================

// Obtener dirección de depósito con QR
export function useDepositAddress(network: string = "polygon") {
  return useQuery({
    queryKey: walletKeys.depositAddress(network),
    queryFn: () =>
      apiClient.get<DepositAddress>("/blockchain/deposit/address", { network }),
    staleTime: 5 * 60 * 1000, // 5 minutos
  });
}

// Historial de depósitos
export function useDepositHistory(options?: {
  limit?: number;
  offset?: number;
  status?: string;
}) {
  return useQuery({
    queryKey: walletKeys.depositHistory(options),
    queryFn: () =>
      apiClient.get<DepositHistory>("/blockchain/deposit/history", {
        limit: options?.limit || 20,
        offset: options?.offset || 0,
        ...(options?.status && { status: options.status }),
      }),
  });
}

// ==================== WITHDRAWAL HOOKS ====================

// Estimar fees de retiro
export function useWithdrawalFeeEstimate(params: {
  network: string;
  amount: number;
  token_address?: string;
}) {
  return useQuery({
    queryKey: walletKeys.withdrawalFeeEstimate(params),
    queryFn: () =>
      apiClient.get<WithdrawalFeeEstimate>("/blockchain/withdraw/fee-estimate", {
        network: params.network,
        amount: params.amount,
        ...(params.token_address && { token_address: params.token_address }),
      }),
    enabled: params.amount > 0,
    staleTime: 30 * 1000, // 30 segundos (gas prices cambian)
  });
}

// Ejecutar retiro
export function useWithdraw() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: WithdrawalRequest) =>
      apiClient.post<WithdrawalResponse>("/blockchain/withdraw", request),
    onSuccess: () => {
      // Invalidar balances y transacciones
      queryClient.invalidateQueries({ queryKey: walletKeys.consolidatedBalances() });
      queryClient.invalidateQueries({ queryKey: walletKeys.transactions() });
      queryClient.invalidateQueries({ queryKey: walletKeys.portfolio() });
    },
  });
}

// ==================== CONSOLIDATED BALANCE HOOKS ====================

// Balances consolidados de todas las wallets
export function useConsolidatedBalances() {
  return useQuery({
    queryKey: walletKeys.consolidatedBalances(),
    queryFn: () => apiClient.get<ConsolidatedBalance>("/blockchain/balances"),
    staleTime: 60 * 1000, // 1 minuto
    refetchInterval: 2 * 60 * 1000, // Refetch cada 2 minutos
  });
}

// Helper para formatear dirección
export function formatAddress(address: string, chars: number = 6): string {
  if (!address || address.length < chars * 2) return address;
  return `${address.slice(0, chars)}...${address.slice(-chars)}`;
}

// Helper para obtener link del explorador
export function getExplorerLink(
  txHash: string,
  network: string = "polygon"
): string {
  const explorers: Record<string, string> = {
    polygon: "https://polygonscan.com/tx/",
    ethereum: "https://etherscan.io/tx/",
    arbitrum: "https://arbiscan.io/tx/",
    base: "https://basescan.org/tx/",
  };
  return `${explorers[network] || explorers.polygon}${txHash}`;
}

// Helper para obtener color de estado de transacción
export function getTransactionStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: "text-yellow-500",
    processing: "text-blue-500",
    confirmed: "text-green-500",
    failed: "text-red-500",
  };
  return colors[status] || "text-muted-foreground";
}
