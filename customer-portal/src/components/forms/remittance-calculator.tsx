"use client";

import { useEffect, useState, useCallback } from "react";
import { ArrowDown, Clock, Info, RefreshCw, Zap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatNumber, debounce } from "@/lib/utils";
import { useRemittanceQuote } from "@/features/remittances/hooks/use-remittances";
import type { RemittanceCurrency, RemittanceQuote, QuoteRequest } from "@/types";

interface RemittanceCalculatorProps {
  onQuoteChange?: (quote: RemittanceQuote | null) => void;
  defaultAmount?: number;
  sourceCurrency?: RemittanceCurrency;
  destinationCurrency?: RemittanceCurrency;
}

const currencyOptions: { value: RemittanceCurrency; label: string; flag: string }[] = [
  { value: "USD", label: "Dólares", flag: "🇺🇸" },
  { value: "MXN", label: "Pesos MX", flag: "🇲🇽" },
  { value: "EUR", label: "Euros", flag: "🇪🇺" },
  { value: "COP", label: "Pesos CO", flag: "🇨🇴" },
  { value: "PEN", label: "Soles", flag: "🇵🇪" },
];

export function RemittanceCalculator({
  onQuoteChange,
  defaultAmount = 200,
  sourceCurrency = "USD",
  destinationCurrency = "MXN",
}: RemittanceCalculatorProps) {
  const [amount, setAmount] = useState(defaultAmount);
  const [source, setSource] = useState<RemittanceCurrency>(sourceCurrency);
  const [destination, setDestination] = useState<RemittanceCurrency>(destinationCurrency);
  const [quoteParams, setQuoteParams] = useState<QuoteRequest | null>(null);

  // Debounced quote request
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedSetParams = useCallback(
    debounce((params: QuoteRequest) => {
      setQuoteParams(params);
    }, 500),
    []
  );

  useEffect(() => {
    if (amount > 0) {
      debouncedSetParams({
        amount_source: amount,
        currency_source: source,
        currency_destination: destination,
      });
    } else {
      setQuoteParams(null);
    }
  }, [amount, source, destination, debouncedSetParams]);

  const { data: quote, isLoading, isError, refetch } = useRemittanceQuote(quoteParams);

  useEffect(() => {
    onQuoteChange?.(quote ?? null);
  }, [quote, onQuoteChange]);

  const handleAmountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value) || 0;
    setAmount(value);
  };

  // Tiempo restante de validez del quote
  const getQuoteTimeRemaining = () => {
    if (!quote?.quote_expires_at) return null;
    const expires = new Date(quote.quote_expires_at);
    const now = new Date();
    const diffMs = expires.getTime() - now.getTime();
    if (diffMs <= 0) return "Expirado";
    const minutes = Math.floor(diffMs / 60000);
    const seconds = Math.floor((diffMs % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
  };

  return (
    <Card>
      <CardContent className="p-6 space-y-6">
        {/* Input: Monto a enviar */}
        <div className="space-y-2">
          <Label className="text-base font-medium">Tú envías</Label>
          <div className="relative">
            <Input
              type="number"
              value={amount || ""}
              onChange={handleAmountChange}
              placeholder="0.00"
              className="text-3xl h-16 font-semibold pr-24 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              min={10}
              max={10000}
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <select
                value={source}
                onChange={(e) => setSource(e.target.value as RemittanceCurrency)}
                className="bg-muted px-3 py-1.5 rounded-lg text-sm font-medium border-0 cursor-pointer"
              >
                {currencyOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.flag} {opt.value}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Exchange Rate & Fees */}
        <div className="relative">
          <div className="absolute left-6 top-0 bottom-0 w-px bg-border" />

          <div className="space-y-3 py-2">
            {/* Tasa de cambio */}
            <div className="flex items-center gap-3 pl-12 relative">
              <div className="absolute left-4 h-6 w-6 rounded-full bg-muted flex items-center justify-center">
                <RefreshCw className="h-3 w-3 text-muted-foreground" />
              </div>
              <div className="flex-1 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Tasa de cambio</span>
                {isLoading ? (
                  <Skeleton className="h-5 w-32" />
                ) : quote ? (
                  <span className="font-medium">
                    1 {source} = {formatNumber(quote.exchange_rate_source_usd * (quote.exchange_rate_usd_destination ?? 1), 4)} {destination}
                  </span>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </div>
            </div>

            {/* Comisión plataforma */}
            <div className="flex items-center gap-3 pl-12 relative">
              <div className="absolute left-4 h-6 w-6 rounded-full bg-muted flex items-center justify-center">
                <Zap className="h-3 w-3 text-muted-foreground" />
              </div>
              <div className="flex-1 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Comisión FinCore
                  <Badge variant="secondary" className="ml-2 text-[10px]">
                    1.5%
                  </Badge>
                </span>
                {isLoading ? (
                  <Skeleton className="h-5 w-20" />
                ) : quote ? (
                  <span className="font-medium text-green-600">
                    -{formatCurrency(quote.platform_fee, source)}
                  </span>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </div>
            </div>

            {/* Fee de red */}
            <div className="flex items-center gap-3 pl-12 relative">
              <div className="absolute left-4 h-6 w-6 rounded-full bg-muted flex items-center justify-center">
                <Info className="h-3 w-3 text-muted-foreground" />
              </div>
              <div className="flex-1 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Gas blockchain
                </span>
                {isLoading ? (
                  <Skeleton className="h-5 w-16" />
                ) : quote ? (
                  <span className="font-medium">
                    ~{formatCurrency(quote.network_fee, source)}
                  </span>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </div>
            </div>

            {/* Total a pagar */}
            <div className="flex items-center gap-3 pl-12 relative">
              <div className="absolute left-4 h-6 w-6 rounded-full bg-primary flex items-center justify-center">
                <span className="text-[10px] text-primary-foreground font-bold">=</span>
              </div>
              <div className="flex-1 flex items-center justify-between">
                <span className="text-sm font-medium">Total a pagar</span>
                {isLoading ? (
                  <Skeleton className="h-6 w-28" />
                ) : quote ? (
                  <span className="text-lg font-bold">
                    {formatCurrency(quote.total_to_pay, source)}
                  </span>
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Arrow */}
        <div className="flex justify-center">
          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
            <ArrowDown className="h-5 w-5 text-primary" />
          </div>
        </div>

        {/* Output: Beneficiario recibe */}
        <div className="space-y-2">
          <Label className="text-base font-medium">Beneficiario recibe</Label>
          <div className="relative">
            {isLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : (
              <div className="h-16 px-4 rounded-lg border bg-muted/30 flex items-center justify-between">
                <span className="text-3xl font-semibold text-primary">
                  {quote
                    ? formatNumber(quote.amount_destination, 2)
                    : "0.00"}
                </span>
                <select
                  value={destination}
                  onChange={(e) => setDestination(e.target.value as RemittanceCurrency)}
                  className="bg-primary/10 text-primary px-3 py-1.5 rounded-lg text-sm font-medium border-0 cursor-pointer"
                >
                  {currencyOptions
                    .filter((opt) => opt.value !== source)
                    .map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.flag} {opt.value}
                      </option>
                    ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* Tiempo estimado y validez */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>
              Entrega estimada:{" "}
              {isLoading ? (
                <Skeleton className="h-4 w-20 inline-block" />
              ) : quote ? (
                <span className="font-medium text-foreground">
                  {quote.estimated_delivery}
                </span>
              ) : (
                "-"
              )}
            </span>
          </div>

          {quote && (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">
                Cotización válida: {getQuoteTimeRemaining()}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => refetch()}
                disabled={isLoading}
              >
                <RefreshCw className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
              </Button>
            </div>
          )}
        </div>

        {/* Error state */}
        {isError && (
          <div className="text-sm text-destructive text-center">
            Error al obtener cotización. Por favor, intenta de nuevo.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
