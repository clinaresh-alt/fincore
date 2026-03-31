"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import {
  ArrowUpRight,
  ArrowDownRight,
  TrendingUp,
  Activity,
  Clock,
  Loader2,
  ChevronLeft,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useMarketToken,
  useTokenTicker,
  useOrderbook,
  useRecentTrades,
  useCreateOrder,
  useMarketplacePortfolio,
  formatPrice,
  getPriceChangeColor,
  formatVolume,
  type OrderCreateInput,
} from "@/features/marketplace/hooks/use-marketplace";
import { cn, formatCurrency } from "@/lib/utils";

export default function TradingPage() {
  const params = useParams();
  const listingId = params.listingId as string;

  const [orderSide, setOrderSide] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<"limit" | "market">("limit");
  const [amount, setAmount] = useState("");
  const [price, setPrice] = useState("");

  const { data: token, isLoading: tokenLoading } = useMarketToken(listingId);
  const { data: ticker } = useTokenTicker(listingId);
  const { data: orderbook, isLoading: orderbookLoading } = useOrderbook(listingId, 15);
  const { data: recentTrades, isLoading: tradesLoading } = useRecentTrades(listingId, 30);
  const { data: portfolio } = useMarketplacePortfolio();

  const createOrderMutation = useCreateOrder();

  // Obtener balance disponible del token
  const availableBalance = useMemo(() => {
    if (!portfolio || !token) return 0;
    const item = portfolio.items.find((i) => i.token_id === token.token_id);
    return item?.available_balance || 0;
  }, [portfolio, token]);

  // Calcular total de la orden
  const orderTotal = useMemo(() => {
    const amt = parseFloat(amount) || 0;
    const prc = orderType === "market" ? (ticker?.last_price || 0) : (parseFloat(price) || 0);
    return amt * prc;
  }, [amount, price, orderType, ticker]);

  // Validar formulario
  const isFormValid = useMemo(() => {
    const amt = parseFloat(amount);
    if (!amt || amt <= 0) return false;
    if (orderType === "limit") {
      const prc = parseFloat(price);
      if (!prc || prc <= 0) return false;
    }
    if (orderSide === "sell" && amt > availableBalance) return false;
    return true;
  }, [amount, price, orderType, orderSide, availableBalance]);

  const handleSubmitOrder = async () => {
    const orderData: OrderCreateInput = {
      listing_id: listingId,
      side: orderSide,
      order_type: orderType,
      amount: parseFloat(amount),
      ...(orderType === "limit" && { price: parseFloat(price) }),
    };

    try {
      const result = await createOrderMutation.mutateAsync(orderData);
      toast.success(result.message, {
        description: `Orden ${orderSide === "buy" ? "de compra" : "de venta"} ${
          result.trades.length > 0 ? "ejecutada" : "creada"
        }`,
      });
      setAmount("");
      setPrice("");
    } catch {
      toast.error("Error al crear la orden");
    }
  };

  const handleSetPrice = (p: number) => {
    setPrice(p.toString());
  };

  if (tokenLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-96 lg:col-span-2" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <h2 className="text-xl font-bold mb-2">Token no encontrado</h2>
        <Link href="/marketplace">
          <Button variant="outline">
            <ChevronLeft className="h-4 w-4 mr-2" />
            Volver al Marketplace
          </Button>
        </Link>
      </div>
    );
  }

  const priceChangeColor = getPriceChangeColor(token.price_change_24h);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/marketplace">
            <Button variant="ghost" size="icon">
              <ChevronLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
              <span className="font-bold text-primary">{token.token_symbol.slice(0, 2)}</span>
            </div>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                {token.token_symbol}
                <span className="text-muted-foreground font-normal text-lg">
                  / USD
                </span>
              </h1>
              <p className="text-muted-foreground">{token.token_name}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {ticker && (
            <div className="text-right">
              <p className="text-2xl font-bold">${formatPrice(ticker.last_price)}</p>
              <p className={cn("text-sm flex items-center gap-1 justify-end", priceChangeColor)}>
                {token.price_change_24h && token.price_change_24h >= 0 ? (
                  <ArrowUpRight className="h-4 w-4" />
                ) : (
                  <ArrowDownRight className="h-4 w-4" />
                )}
                {token.price_change_24h && token.price_change_24h >= 0 ? "+" : ""}
                {token.price_change_percent_24h?.toFixed(2)}%
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Stats Bar */}
      {ticker && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">24h High</p>
              <p className="text-lg font-bold">${formatPrice(ticker.high_24h)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">24h Low</p>
              <p className="text-lg font-bold">${formatPrice(ticker.low_24h)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">24h Volume</p>
              <p className="text-lg font-bold">{formatVolume(ticker.volume_24h)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">24h Trades</p>
              <p className="text-lg font-bold">{ticker.trades_24h}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Trading Area */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Orderbook + Trades */}
        <div className="lg:col-span-2 space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Orderbook */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Activity className="h-5 w-5" />
                  Orderbook
                </CardTitle>
              </CardHeader>
              <CardContent>
                {orderbookLoading ? (
                  <div className="space-y-2">
                    {[...Array(10)].map((_, i) => (
                      <Skeleton key={i} className="h-6" />
                    ))}
                  </div>
                ) : orderbook ? (
                  <div className="space-y-2">
                    {/* Asks (ventas) - invertido para mostrar menor precio abajo */}
                    <div className="space-y-1">
                      {[...orderbook.asks].reverse().slice(0, 8).map((ask, i) => (
                        <div
                          key={i}
                          className="grid grid-cols-3 text-sm cursor-pointer hover:bg-muted/50 px-2 py-1 rounded"
                          onClick={() => handleSetPrice(ask.price)}
                        >
                          <span className="text-red-500">{formatPrice(ask.price)}</span>
                          <span className="text-right">{formatPrice(ask.amount, 2)}</span>
                          <span className="text-right text-muted-foreground">
                            {formatPrice(ask.total, 2)}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Spread */}
                    <div className="py-2 px-2 bg-muted/50 rounded text-center text-sm">
                      Spread: ${formatPrice(orderbook.spread || 0)} (
                      {orderbook.spread_percent?.toFixed(2) || 0}%)
                    </div>

                    {/* Bids (compras) */}
                    <div className="space-y-1">
                      {orderbook.bids.slice(0, 8).map((bid, i) => (
                        <div
                          key={i}
                          className="grid grid-cols-3 text-sm cursor-pointer hover:bg-muted/50 px-2 py-1 rounded"
                          onClick={() => handleSetPrice(bid.price)}
                        >
                          <span className="text-green-500">{formatPrice(bid.price)}</span>
                          <span className="text-right">{formatPrice(bid.amount, 2)}</span>
                          <span className="text-right text-muted-foreground">
                            {formatPrice(bid.total, 2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-center text-muted-foreground py-8">
                    No hay órdenes en el orderbook
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Recent Trades */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Clock className="h-5 w-5" />
                  Trades Recientes
                </CardTitle>
              </CardHeader>
              <CardContent>
                {tradesLoading ? (
                  <div className="space-y-2">
                    {[...Array(10)].map((_, i) => (
                      <Skeleton key={i} className="h-6" />
                    ))}
                  </div>
                ) : recentTrades && recentTrades.length > 0 ? (
                  <div className="space-y-1 max-h-[400px] overflow-y-auto">
                    {/* Header */}
                    <div className="grid grid-cols-3 text-xs text-muted-foreground px-2 pb-2">
                      <span>Precio</span>
                      <span className="text-right">Cantidad</span>
                      <span className="text-right">Hora</span>
                    </div>
                    {recentTrades.map((trade) => (
                      <div
                        key={trade.id}
                        className="grid grid-cols-3 text-sm px-2 py-1"
                      >
                        <span className={trade.side === "buy" ? "text-green-500" : "text-red-500"}>
                          {formatPrice(trade.price)}
                        </span>
                        <span className="text-right">{formatPrice(trade.amount, 2)}</span>
                        <span className="text-right text-muted-foreground">
                          {new Date(trade.executed_at).toLocaleTimeString("es-MX", {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-center text-muted-foreground py-8">
                    No hay trades recientes
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Market Info */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Información del Token</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Market Cap</p>
                  <p className="font-medium">{formatCurrency(token.market_cap, "USD")}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Supply Circulante</p>
                  <p className="font-medium">{formatVolume(token.circulating_supply)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Supply Total</p>
                  <p className="font-medium">{formatVolume(token.total_supply)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Total Trades</p>
                  <p className="font-medium">{token.total_trades}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Order Form */}
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-lg">Crear Orden</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Buy/Sell Tabs */}
            <Tabs
              value={orderSide}
              onValueChange={(v) => setOrderSide(v as "buy" | "sell")}
            >
              <TabsList className="grid grid-cols-2 w-full">
                <TabsTrigger
                  value="buy"
                  className="data-[state=active]:bg-green-500 data-[state=active]:text-white"
                >
                  Comprar
                </TabsTrigger>
                <TabsTrigger
                  value="sell"
                  className="data-[state=active]:bg-red-500 data-[state=active]:text-white"
                >
                  Vender
                </TabsTrigger>
              </TabsList>
            </Tabs>

            {/* Order Type */}
            <div className="space-y-2">
              <Label>Tipo de Orden</Label>
              <Select
                value={orderType}
                onValueChange={(v) => setOrderType(v as "limit" | "market")}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="limit">Limit</SelectItem>
                  <SelectItem value="market">Market</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Price (for limit orders) */}
            {orderType === "limit" && (
              <div className="space-y-2">
                <Label>Precio</Label>
                <div className="relative">
                  <Input
                    type="number"
                    step="0.0001"
                    placeholder="0.00"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    className="pr-12"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    USD
                  </span>
                </div>
              </div>
            )}

            {/* Amount */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Cantidad</Label>
                {orderSide === "sell" && (
                  <span className="text-xs text-muted-foreground">
                    Disponible: {formatPrice(availableBalance, 4)}
                  </span>
                )}
              </div>
              <div className="relative">
                <Input
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="pr-16"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                  {token.token_symbol}
                </span>
              </div>
              {orderSide === "sell" && (
                <div className="flex gap-2">
                  {[25, 50, 75, 100].map((pct) => (
                    <Button
                      key={pct}
                      variant="outline"
                      size="sm"
                      className="flex-1 text-xs"
                      onClick={() => setAmount(((availableBalance * pct) / 100).toString())}
                    >
                      {pct}%
                    </Button>
                  ))}
                </div>
              )}
            </div>

            {/* Order Summary */}
            <div className="p-3 rounded-lg bg-muted/50 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Precio</span>
                <span>
                  {orderType === "market"
                    ? `~$${formatPrice(ticker?.last_price || 0)} (market)`
                    : price
                    ? `$${formatPrice(parseFloat(price))}`
                    : "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Cantidad</span>
                <span>
                  {amount ? `${formatPrice(parseFloat(amount), 4)} ${token.token_symbol}` : "—"}
                </span>
              </div>
              <div className="flex justify-between border-t pt-2">
                <span className="font-medium">Total</span>
                <span className="font-medium">
                  {orderTotal > 0 ? formatCurrency(orderTotal, "USD") : "—"}
                </span>
              </div>
            </div>

            {/* Submit Button */}
            <Button
              className={cn(
                "w-full",
                orderSide === "buy"
                  ? "bg-green-500 hover:bg-green-600"
                  : "bg-red-500 hover:bg-red-600"
              )}
              size="lg"
              onClick={handleSubmitOrder}
              disabled={!isFormValid || createOrderMutation.isPending}
            >
              {createOrderMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Procesando...
                </>
              ) : (
                <>
                  {orderSide === "buy" ? "Comprar" : "Vender"} {token.token_symbol}
                </>
              )}
            </Button>

            {/* Warnings */}
            {orderSide === "sell" && parseFloat(amount) > availableBalance && (
              <p className="text-sm text-destructive text-center">
                Balance insuficiente
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
