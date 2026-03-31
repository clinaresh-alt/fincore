"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// ==================== TYPES ====================

export interface MarketTokenInfo {
  listing_id: string;
  token_id: string;
  token_symbol: string;
  token_name: string;
  project_id: string;
  project_name: string;
  current_price: number;
  price_change_24h: number | null;
  price_change_percent_24h: number | null;
  volume_24h: number;
  volume_7d: number | null;
  market_cap: number;
  circulating_supply: number;
  total_supply: number;
  total_trades: number;
  status: string;
  best_bid: number | null;
  best_ask: number | null;
  spread: number | null;
}

export interface OrderBookEntry {
  price: number;
  amount: number;
  total: number;
  orders_count: number;
}

export interface OrderBook {
  listing_id: string;
  token_symbol: string;
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  spread: number | null;
  spread_percent: number | null;
  last_updated: string;
}

export interface Order {
  id: string;
  listing_id: string;
  user_id: string;
  wallet_id: string | null;
  side: "buy" | "sell";
  order_type: "limit" | "market";
  amount: number;
  filled_amount: number;
  remaining_amount: number;
  price: number | null;
  average_fill_price: number | null;
  status: "open" | "partially_filled" | "filled" | "cancelled" | "expired";
  estimated_fee: number;
  actual_fee: number;
  fill_percentage: number;
  total_value: number;
  expires_at: string | null;
  client_order_id: string | null;
  created_at: string;
  updated_at: string;
  filled_at: string | null;
  cancelled_at: string | null;
}

export interface Trade {
  id: string;
  listing_id: string;
  token_symbol: string;
  buyer_id: string | null;
  seller_id: string | null;
  amount: number;
  price: number;
  total_value: number;
  maker_fee: number;
  taker_fee: number;
  total_fee: number;
  is_settled_onchain: boolean;
  settlement_tx_hash: string | null;
  executed_at: string;
}

export interface RecentTrade {
  id: string;
  price: number;
  amount: number;
  side: "buy" | "sell";
  executed_at: string;
}

export interface OHLCVData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trades_count: number;
  vwap: number | null;
}

export interface TickerResponse {
  listing_id: string;
  token_symbol: string;
  token_name: string;
  last_price: number;
  bid: number | null;
  ask: number | null;
  price_change_24h: number;
  price_change_percent_24h: number;
  high_24h: number;
  low_24h: number;
  volume_24h: number;
  volume_quote_24h: number;
  trades_24h: number;
  timestamp: string;
}

export interface OrderCreateInput {
  listing_id: string;
  side: "buy" | "sell";
  order_type: "limit" | "market";
  amount: number;
  price?: number;
  wallet_id?: string;
  expires_at?: string;
}

export interface OrderExecutionResult {
  order: Order;
  trades: Trade[];
  message: string;
}

export interface UserPortfolioItem {
  token_id: string;
  listing_id: string | null;
  token_symbol: string;
  token_name: string;
  balance: number;
  available_balance: number;
  locked_balance: number;
  average_cost: number;
  current_price: number;
  current_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  is_tradeable: boolean;
}

export interface UserMarketplacePortfolio {
  total_value: number;
  total_unrealized_pnl: number;
  items: UserPortfolioItem[];
}

export interface TradingStats {
  user_id: string;
  total_trades: number;
  total_buy_volume: number;
  total_sell_volume: number;
  total_fees_paid: number;
  total_orders_placed: number;
  total_orders_filled: number;
  total_orders_cancelled: number;
  realized_pnl: number;
  first_trade_at: string | null;
  last_trade_at: string | null;
}

export interface MarketplaceSummary {
  total_listings: number;
  active_listings: number;
  total_volume_24h: number;
  total_trades_24h: number;
  total_volume_all_time: number;
  total_trades_all_time: number;
  top_gainers: MarketTokenInfo[];
  top_losers: MarketTokenInfo[];
  most_traded: MarketTokenInfo[];
  recently_listed: MarketTokenInfo[];
}

// ==================== QUERY KEYS ====================

export const marketplaceKeys = {
  all: ["marketplace"] as const,
  tokens: () => [...marketplaceKeys.all, "tokens"] as const,
  token: (listingId: string) => [...marketplaceKeys.all, "token", listingId] as const,
  ticker: (listingId: string) => [...marketplaceKeys.all, "ticker", listingId] as const,
  tickers: () => [...marketplaceKeys.all, "tickers"] as const,
  orderbook: (listingId: string) => [...marketplaceKeys.all, "orderbook", listingId] as const,
  recentTrades: (listingId: string) => [...marketplaceKeys.all, "recent-trades", listingId] as const,
  ohlcv: (listingId: string, interval: string) =>
    [...marketplaceKeys.all, "ohlcv", listingId, interval] as const,
  orders: (filters?: Record<string, unknown>) => [...marketplaceKeys.all, "orders", filters] as const,
  openOrders: () => [...marketplaceKeys.all, "open-orders"] as const,
  trades: (filters?: Record<string, unknown>) => [...marketplaceKeys.all, "trades", filters] as const,
  portfolio: () => [...marketplaceKeys.all, "portfolio"] as const,
  stats: () => [...marketplaceKeys.all, "stats"] as const,
  summary: () => [...marketplaceKeys.all, "summary"] as const,
};

// ==================== HOOKS ====================

// Obtener tokens del marketplace
export function useMarketTokens() {
  return useQuery({
    queryKey: marketplaceKeys.tokens(),
    queryFn: () => apiClient.get<MarketTokenInfo[]>("/marketplace/tokens"),
    staleTime: 30 * 1000, // 30 segundos
    refetchInterval: 60 * 1000, // Refetch cada minuto
  });
}

// Obtener info de un token
export function useMarketToken(listingId: string) {
  return useQuery({
    queryKey: marketplaceKeys.token(listingId),
    queryFn: () => apiClient.get<MarketTokenInfo>(`/marketplace/tokens/${listingId}`),
    enabled: !!listingId,
    staleTime: 30 * 1000,
  });
}

// Obtener ticker de un token
export function useTokenTicker(listingId: string) {
  return useQuery({
    queryKey: marketplaceKeys.ticker(listingId),
    queryFn: () => apiClient.get<TickerResponse>(`/marketplace/tokens/${listingId}/ticker`),
    enabled: !!listingId,
    staleTime: 10 * 1000, // 10 segundos
    refetchInterval: 15 * 1000, // Refetch cada 15 segundos
  });
}

// Obtener orderbook
export function useOrderbook(listingId: string, depth: number = 20) {
  return useQuery({
    queryKey: marketplaceKeys.orderbook(listingId),
    queryFn: () =>
      apiClient.get<OrderBook>(`/marketplace/tokens/${listingId}/orderbook`, { depth }),
    enabled: !!listingId,
    staleTime: 5 * 1000, // 5 segundos
    refetchInterval: 10 * 1000, // Refetch cada 10 segundos
  });
}

// Obtener trades recientes
export function useRecentTrades(listingId: string, limit: number = 50) {
  return useQuery({
    queryKey: marketplaceKeys.recentTrades(listingId),
    queryFn: () =>
      apiClient.get<RecentTrade[]>(`/marketplace/tokens/${listingId}/trades`, { limit }),
    enabled: !!listingId,
    staleTime: 5 * 1000,
    refetchInterval: 10 * 1000,
  });
}

// Obtener datos OHLCV para gráficos
export function useOHLCV(
  listingId: string,
  interval: string = "1h",
  limit: number = 100
) {
  return useQuery({
    queryKey: marketplaceKeys.ohlcv(listingId, interval),
    queryFn: () =>
      apiClient.get<{ listing_id: string; token_symbol: string; interval: string; data: OHLCVData[] }>(
        `/marketplace/tokens/${listingId}/ohlcv`,
        { interval, limit }
      ),
    enabled: !!listingId,
    staleTime: 60 * 1000,
  });
}

// Crear orden
export function useCreateOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (order: OrderCreateInput) =>
      apiClient.post<OrderExecutionResult>("/marketplace/orders", order),
    onSuccess: (data) => {
      // Invalidar queries relacionadas
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.orders() });
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.openOrders() });
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.portfolio() });
      queryClient.invalidateQueries({
        queryKey: marketplaceKeys.orderbook(data.order.listing_id),
      });
      if (data.trades.length > 0) {
        queryClient.invalidateQueries({ queryKey: marketplaceKeys.trades() });
        queryClient.invalidateQueries({ queryKey: marketplaceKeys.stats() });
      }
    },
  });
}

// Obtener mis órdenes
export function useMyOrders(options?: {
  status?: string;
  listing_id?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: marketplaceKeys.orders(options),
    queryFn: () =>
      apiClient.get<Order[]>("/marketplace/orders", {
        ...(options?.status && { status: options.status }),
        ...(options?.listing_id && { listing_id: options.listing_id }),
        limit: options?.limit || 50,
        offset: options?.offset || 0,
      }),
  });
}

// Obtener órdenes abiertas
export function useOpenOrders() {
  return useQuery({
    queryKey: marketplaceKeys.openOrders(),
    queryFn: () => apiClient.get<Order[]>("/marketplace/orders/open"),
    refetchInterval: 30 * 1000,
  });
}

// Cancelar orden
export function useCancelOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (orderId: string) =>
      apiClient.delete<{ success: boolean; order_id: string; status: string; message: string }>(
        `/marketplace/orders/${orderId}`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.orders() });
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.openOrders() });
      queryClient.invalidateQueries({ queryKey: marketplaceKeys.portfolio() });
    },
  });
}

// Obtener mis trades
export function useMyTrades(options?: { listing_id?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: marketplaceKeys.trades(options),
    queryFn: () =>
      apiClient.get<{ trades: Trade[]; total: number; page: number; page_size: number }>(
        "/marketplace/trades",
        {
          ...(options?.listing_id && { listing_id: options.listing_id }),
          limit: options?.limit || 50,
          offset: options?.offset || 0,
        }
      ),
  });
}

// Obtener portfolio para marketplace
export function useMarketplacePortfolio() {
  return useQuery({
    queryKey: marketplaceKeys.portfolio(),
    queryFn: () => apiClient.get<UserMarketplacePortfolio>("/marketplace/portfolio"),
    staleTime: 60 * 1000,
  });
}

// Obtener estadísticas de trading
export function useTradingStats() {
  return useQuery({
    queryKey: marketplaceKeys.stats(),
    queryFn: () => apiClient.get<TradingStats>("/marketplace/stats"),
    staleTime: 60 * 1000,
  });
}

// Obtener resumen del marketplace
export function useMarketplaceSummary() {
  return useQuery({
    queryKey: marketplaceKeys.summary(),
    queryFn: () => apiClient.get<MarketplaceSummary>("/marketplace/summary"),
    staleTime: 60 * 1000,
  });
}

// ==================== HELPERS ====================

// Formatear precio
export function formatPrice(price: number, decimals: number = 4): string {
  return price.toLocaleString("es-MX", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// Formatear cambio de precio
export function formatPriceChange(change: number | null, percent: number | null): string {
  if (change === null || percent === null) return "—";
  const sign = change >= 0 ? "+" : "";
  return `${sign}${formatPrice(change, 4)} (${sign}${percent.toFixed(2)}%)`;
}

// Color del cambio de precio
export function getPriceChangeColor(change: number | null): string {
  if (change === null) return "text-muted-foreground";
  if (change > 0) return "text-green-500";
  if (change < 0) return "text-red-500";
  return "text-muted-foreground";
}

// Formatear volumen
export function formatVolume(volume: number): string {
  if (volume >= 1_000_000) {
    return `${(volume / 1_000_000).toFixed(2)}M`;
  }
  if (volume >= 1_000) {
    return `${(volume / 1_000).toFixed(2)}K`;
  }
  return volume.toFixed(2);
}

// Color del lado de la orden
export function getOrderSideColor(side: "buy" | "sell"): string {
  return side === "buy" ? "text-green-500" : "text-red-500";
}

// Badge del estado de la orden
export function getOrderStatusVariant(
  status: Order["status"]
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "open":
      return "secondary";
    case "partially_filled":
      return "default";
    case "filled":
      return "default";
    case "cancelled":
      return "outline";
    case "expired":
      return "destructive";
    default:
      return "outline";
  }
}
