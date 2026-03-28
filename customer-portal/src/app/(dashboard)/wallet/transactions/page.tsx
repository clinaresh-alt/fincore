"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  ArrowDownLeft,
  ExternalLink,
  Clock,
  AlertCircle,
  CheckCircle2,
  Filter,
  RefreshCw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useBlockchainTransactions,
  formatAddress,
  getExplorerLink,
  getTransactionStatusColor,
  type BlockchainTransaction,
} from "@/features/wallet/hooks/use-wallet";
import { cn, formatCurrency } from "@/lib/utils";

const STATUS_FILTERS = [
  { value: "", label: "Todos" },
  { value: "pending", label: "Pendientes" },
  { value: "processing", label: "Procesando" },
  { value: "confirmed", label: "Confirmados" },
  { value: "failed", label: "Fallidos" },
];

export default function TransactionsPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const {
    data: transactions = [],
    isLoading,
    refetch,
    isFetching,
  } = useBlockchainTransactions({
    limit: pageSize,
    offset: page * pageSize,
    status: statusFilter || undefined,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/wallet">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Historial de Transacciones</h1>
          <p className="text-muted-foreground">
            Todas tus transacciones blockchain
          </p>
        </div>
      </div>

      {/* Filtros */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Estado:</span>
              <div className="flex gap-1">
                {STATUS_FILTERS.map((filter) => (
                  <Button
                    key={filter.value}
                    variant={statusFilter === filter.value ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setStatusFilter(filter.value);
                      setPage(0);
                    }}
                  >
                    {filter.label}
                  </Button>
                ))}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={cn("h-4 w-4 mr-2", isFetching && "animate-spin")} />
              Actualizar
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Lista de transacciones */}
      <Card>
        <CardHeader>
          <CardTitle>Transacciones</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-20" />
              ))}
            </div>
          ) : transactions.length === 0 ? (
            <div className="text-center py-12">
              <Clock className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-1">Sin transacciones</h3>
              <p className="text-muted-foreground">
                {statusFilter
                  ? "No hay transacciones con este filtro"
                  : "Aún no tienes transacciones blockchain"}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {transactions.map((tx) => (
                <TransactionDetailRow key={tx.id} transaction={tx} />
              ))}
            </div>
          )}

          {/* Paginación */}
          {transactions.length > 0 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t">
              <Button
                variant="outline"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Anterior
              </Button>
              <span className="text-sm text-muted-foreground">
                Página {page + 1}
              </span>
              <Button
                variant="outline"
                disabled={transactions.length < pageSize}
                onClick={() => setPage((p) => p + 1)}
              >
                Siguiente
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

interface TransactionDetailRowProps {
  transaction: BlockchainTransaction;
}

function TransactionDetailRow({ transaction }: TransactionDetailRowProps) {
  const isIncoming = transaction.tx_type === "receive" || transaction.tx_type === "dividend";
  const statusColor = getTransactionStatusColor(transaction.status);

  const StatusIcon =
    transaction.status === "confirmed"
      ? CheckCircle2
      : transaction.status === "failed"
      ? AlertCircle
      : Clock;

  const txTypeLabels: Record<string, string> = {
    send: "Envío",
    receive: "Recibido",
    purchase: "Compra de tokens",
    transfer: "Transferencia",
    dividend: "Dividendos",
    claim: "Reclamación",
  };

  return (
    <div className="flex items-center justify-between p-4 rounded-lg border hover:bg-muted/50 transition-colors">
      <div className="flex items-center gap-4">
        <div
          className={cn(
            "h-12 w-12 rounded-full flex items-center justify-center shrink-0",
            isIncoming ? "bg-green-100 dark:bg-green-900/30" : "bg-blue-100 dark:bg-blue-900/30"
          )}
        >
          {isIncoming ? (
            <ArrowDownLeft className="h-6 w-6 text-green-600" />
          ) : (
            <ArrowUpRight className="h-6 w-6 text-blue-600" />
          )}
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <p className="font-semibold">
              {txTypeLabels[transaction.tx_type] || transaction.tx_type}
            </p>
            <Badge variant="outline" className="text-xs">
              {transaction.network}
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            {transaction.tx_hash && (
              <a
                href={getExplorerLink(transaction.tx_hash, transaction.network)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 hover:text-primary"
              >
                TX: {formatAddress(transaction.tx_hash, 6)}
                <ExternalLink className="h-3 w-3" />
              </a>
            )}

            {transaction.from_address && (
              <span>De: {formatAddress(transaction.from_address, 4)}</span>
            )}

            {transaction.to_address && (
              <span>A: {formatAddress(transaction.to_address, 4)}</span>
            )}
          </div>

          <p className="text-xs text-muted-foreground">
            {new Date(transaction.created_at).toLocaleString()}
            {transaction.confirmed_at && (
              <> • Confirmado: {new Date(transaction.confirmed_at).toLocaleString()}</>
            )}
          </p>
        </div>
      </div>

      <div className="text-right space-y-1">
        <p className={cn("text-lg font-semibold", isIncoming ? "text-green-600" : "")}>
          {isIncoming ? "+" : "-"}
          {transaction.amount} {transaction.token_symbol || "MATIC"}
        </p>

        <div className={cn("flex items-center justify-end gap-1 text-sm", statusColor)}>
          <StatusIcon className="h-4 w-4" />
          <span className="capitalize">{transaction.status}</span>
        </div>

        {transaction.gas_used && transaction.gas_price && (
          <p className="text-xs text-muted-foreground">
            Gas: {(transaction.gas_used * transaction.gas_price / 1e9).toFixed(6)} MATIC
          </p>
        )}

        {transaction.error_message && (
          <p className="text-xs text-destructive truncate max-w-[200px]">
            {transaction.error_message}
          </p>
        )}
      </div>
    </div>
  );
}
