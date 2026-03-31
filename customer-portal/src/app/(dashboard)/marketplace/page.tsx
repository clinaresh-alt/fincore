"use client";

import { useState } from "react";
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Search,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Coins,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useMarketTokens,
  useMarketplaceSummary,
  formatPrice,
  formatPriceChange,
  formatVolume,
  getPriceChangeColor,
  type MarketTokenInfo,
} from "@/features/marketplace/hooks/use-marketplace";
import { cn, formatCurrency } from "@/lib/utils";

export default function MarketplacePage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("all");

  const { data: tokens = [], isLoading: tokensLoading } = useMarketTokens();
  const { data: summary, isLoading: summaryLoading } = useMarketplaceSummary();

  // Filtrar tokens por búsqueda
  const filteredTokens = tokens.filter(
    (token) =>
      token.token_symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
      token.token_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      token.project_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Ordenar según tab activo
  const sortedTokens = [...filteredTokens].sort((a, b) => {
    switch (activeTab) {
      case "gainers":
        return (b.price_change_percent_24h || 0) - (a.price_change_percent_24h || 0);
      case "losers":
        return (a.price_change_percent_24h || 0) - (b.price_change_percent_24h || 0);
      case "volume":
        return (b.volume_24h || 0) - (a.volume_24h || 0);
      default:
        return (b.market_cap || 0) - (a.market_cap || 0);
    }
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />
            Marketplace
          </h1>
          <p className="text-muted-foreground">
            Compra y vende tokens de inversión
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/marketplace/portfolio">
            <Button variant="outline">Mi Portfolio</Button>
          </Link>
          <Link href="/marketplace/orders">
            <Button variant="outline">Mis Ordenes</Button>
          </Link>
        </div>
      </div>

      {/* Stats Summary */}
      {summaryLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : summary ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Tokens Listados</p>
                  <p className="text-2xl font-bold">{summary.active_listings}</p>
                </div>
                <Coins className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Volumen 24h</p>
                  <p className="text-2xl font-bold">{formatVolume(summary.total_volume_24h)}</p>
                </div>
                <Activity className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Trades 24h</p>
                  <p className="text-2xl font-bold">{summary.total_trades_24h}</p>
                </div>
                <BarChart3 className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Top Gainer</p>
                  {summary.top_gainers[0] ? (
                    <div className="flex items-center gap-2">
                      <span className="font-bold">{summary.top_gainers[0].token_symbol}</span>
                      <span className="text-green-500 text-sm">
                        +{summary.top_gainers[0].price_change_percent_24h?.toFixed(2)}%
                      </span>
                    </div>
                  ) : (
                    <p className="text-muted-foreground">—</p>
                  )}
                </div>
                <TrendingUp className="h-8 w-8 text-green-500" />
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por nombre, símbolo o proyecto..."
            className="pl-10"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Token List */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="all">Todos</TabsTrigger>
          <TabsTrigger value="gainers">
            <TrendingUp className="h-4 w-4 mr-1" />
            Gainers
          </TabsTrigger>
          <TabsTrigger value="losers">
            <TrendingDown className="h-4 w-4 mr-1" />
            Losers
          </TabsTrigger>
          <TabsTrigger value="volume">
            <Activity className="h-4 w-4 mr-1" />
            Volumen
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="mt-4">
          {tokensLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-20" />
              ))}
            </div>
          ) : sortedTokens.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <BarChart3 className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium mb-2">No hay tokens</h3>
                <p className="text-muted-foreground">
                  {searchQuery
                    ? "No se encontraron tokens con esa búsqueda"
                    : "Aún no hay tokens listados en el marketplace"}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {/* Header */}
              <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-2 text-sm text-muted-foreground">
                <div className="col-span-3">Token</div>
                <div className="col-span-2 text-right">Precio</div>
                <div className="col-span-2 text-right">Cambio 24h</div>
                <div className="col-span-2 text-right">Volumen 24h</div>
                <div className="col-span-2 text-right">Market Cap</div>
                <div className="col-span-1"></div>
              </div>

              {/* Token Rows */}
              {sortedTokens.map((token) => (
                <TokenRow key={token.listing_id} token={token} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Quick Links */}
      {summary && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Top Gainers */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-green-500" />
                Top Gainers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {summary.top_gainers.slice(0, 5).map((token, index) => (
                  <Link
                    key={token.listing_id}
                    href={`/marketplace/${token.listing_id}`}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-muted-foreground w-4">
                        {index + 1}
                      </span>
                      <div>
                        <p className="font-medium">{token.token_symbol}</p>
                        <p className="text-xs text-muted-foreground">
                          {token.token_name}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">${formatPrice(token.current_price)}</p>
                      <p className="text-xs text-green-500">
                        +{token.price_change_percent_24h?.toFixed(2)}%
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Top Losers */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingDown className="h-5 w-5 text-red-500" />
                Top Losers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {summary.top_losers.slice(0, 5).map((token, index) => (
                  <Link
                    key={token.listing_id}
                    href={`/marketplace/${token.listing_id}`}
                    className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-muted-foreground w-4">
                        {index + 1}
                      </span>
                      <div>
                        <p className="font-medium">{token.token_symbol}</p>
                        <p className="text-xs text-muted-foreground">
                          {token.token_name}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">${formatPrice(token.current_price)}</p>
                      <p className="text-xs text-red-500">
                        {token.price_change_percent_24h?.toFixed(2)}%
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

// Componente de fila de token
function TokenRow({ token }: { token: MarketTokenInfo }) {
  const priceChangeColor = getPriceChangeColor(token.price_change_24h);
  const isPositive = (token.price_change_24h || 0) >= 0;

  return (
    <Link href={`/marketplace/${token.listing_id}`}>
      <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
        <CardContent className="p-4">
          <div className="grid grid-cols-12 gap-4 items-center">
            {/* Token Info */}
            <div className="col-span-12 md:col-span-3 flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="font-bold text-primary text-sm">
                  {token.token_symbol.slice(0, 2)}
                </span>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">{token.token_symbol}</p>
                  <Badge variant="outline" className="text-[10px]">
                    {token.status}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">{token.token_name}</p>
              </div>
            </div>

            {/* Price */}
            <div className="col-span-6 md:col-span-2 text-right">
              <p className="font-medium">${formatPrice(token.current_price)}</p>
            </div>

            {/* 24h Change */}
            <div className={cn("col-span-6 md:col-span-2 text-right", priceChangeColor)}>
              <div className="flex items-center justify-end gap-1">
                {isPositive ? (
                  <ArrowUpRight className="h-4 w-4" />
                ) : (
                  <ArrowDownRight className="h-4 w-4" />
                )}
                <span>
                  {isPositive ? "+" : ""}
                  {token.price_change_percent_24h?.toFixed(2) || "0.00"}%
                </span>
              </div>
            </div>

            {/* Volume */}
            <div className="hidden md:block col-span-2 text-right">
              <p className="font-medium">{formatVolume(token.volume_24h)}</p>
              <p className="text-xs text-muted-foreground">tokens</p>
            </div>

            {/* Market Cap */}
            <div className="hidden md:block col-span-2 text-right">
              <p className="font-medium">{formatCurrency(token.market_cap, "USD")}</p>
            </div>

            {/* Action */}
            <div className="hidden md:flex col-span-1 justify-end">
              <Button size="sm" variant="ghost">
                Trade
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
