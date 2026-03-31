"use client";

import { useState } from "react";
import {
  FileText,
  Download,
  Search,
  AlertTriangle,
  CheckCircle,
  XCircle,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Calendar,
  RefreshCw,
} from "lucide-react";
import {
  useTaxReport,
  useDownloadTaxReport,
  useCheckSAT69B,
  TaxTransaction,
} from "@/features/support/hooks/use-support";
import { format } from "date-fns";
import { es } from "date-fns/locale";

const currentYear = new Date().getFullYear();
const availableYears = Array.from(
  { length: currentYear - 2019 },
  (_, i) => currentYear - i
);

export default function TaxCenterPage() {
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [rfcInput, setRfcInput] = useState("");

  const { data: taxReport, isLoading: isLoadingReport } = useTaxReport(selectedYear);
  const downloadMutation = useDownloadTaxReport();
  const checkSATMutation = useCheckSAT69B();

  const handleDownload = () => {
    downloadMutation.mutate(selectedYear);
  };

  const handleCheckRFC = () => {
    if (rfcInput.length >= 12) {
      checkSATMutation.mutate(rfcInput.toUpperCase());
    }
  };

  const formatCurrency = (amount: number, currency: string = "MXN") => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency,
    }).format(amount);
  };

  const transactionTypeLabels: Record<string, string> = {
    investment: "Inversión",
    dividend: "Dividendo",
    trade: "Operación",
    remittance: "Remesa",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Centro de Impuestos
          </h1>
          <p className="text-gray-600 mt-1">
            Reportes fiscales y verificación SAT
          </p>
        </div>
        <div className="flex items-center gap-4">
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(parseInt(e.target.value))}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
          >
            {availableYears.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
          <button
            onClick={handleDownload}
            disabled={downloadMutation.isPending || !taxReport}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            Descargar PDF
          </button>
        </div>
      </div>

      {/* SAT 69-B Verification */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Verificación SAT Lista 69-B
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          Verifica si un RFC está en la lista de contribuyentes con operaciones
          simuladas del SAT.
        </p>
        <div className="flex gap-4">
          <input
            type="text"
            value={rfcInput}
            onChange={(e) => setRfcInput(e.target.value.toUpperCase())}
            placeholder="RFC (12-13 caracteres)"
            maxLength={13}
            className="flex-1 max-w-xs px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent uppercase"
          />
          <button
            onClick={handleCheckRFC}
            disabled={rfcInput.length < 12 || checkSATMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition-colors disabled:opacity-50"
          >
            {checkSATMutation.isPending ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            Verificar
          </button>
        </div>

        {/* SAT Result */}
        {checkSATMutation.data && (
          <div
            className={`mt-4 p-4 rounded-lg ${
              checkSATMutation.data.is_listed
                ? "bg-red-50 border border-red-200"
                : "bg-green-50 border border-green-200"
            }`}
          >
            <div className="flex items-start gap-3">
              {checkSATMutation.data.is_listed ? (
                <XCircle className="w-6 h-6 text-red-500 flex-shrink-0" />
              ) : (
                <CheckCircle className="w-6 h-6 text-green-500 flex-shrink-0" />
              )}
              <div>
                <p className="font-medium">
                  {checkSATMutation.data.is_listed
                    ? "RFC encontrado en lista 69-B"
                    : "RFC no encontrado en lista 69-B"}
                </p>
                <p className="text-sm mt-1">
                  RFC: <span className="font-mono">{checkSATMutation.data.rfc}</span>
                </p>
                {checkSATMutation.data.is_listed && (
                  <>
                    <p className="text-sm mt-1">
                      Tipo de lista: {checkSATMutation.data.list_type}
                    </p>
                    <p className="text-sm">
                      Motivo: {checkSATMutation.data.reason}
                    </p>
                  </>
                )}
                <p className="text-xs text-gray-500 mt-2">
                  Verificado: {format(new Date(checkSATMutation.data.checked_at), "PPp", { locale: es })}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tax Summary */}
      {isLoadingReport ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600" />
        </div>
      ) : taxReport ? (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <DollarSign className="w-5 h-5 text-blue-600" />
                </div>
                <span className="text-sm text-gray-600">
                  Total Inversiones
                </span>
              </div>
              <p className="text-2xl font-bold text-gray-900">
                {formatCurrency(taxReport.summary.total_investments)}
              </p>
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <TrendingUp className="w-5 h-5 text-green-600" />
                </div>
                <span className="text-sm text-gray-600">
                  Ganancias Realizadas
                </span>
              </div>
              <p className="text-2xl font-bold text-green-600">
                {formatCurrency(taxReport.summary.realized_gains)}
              </p>
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-red-100 rounded-lg">
                  <TrendingDown className="w-5 h-5 text-red-600" />
                </div>
                <span className="text-sm text-gray-600">
                  Pérdidas Realizadas
                </span>
              </div>
              <p className="text-2xl font-bold text-red-600">
                {formatCurrency(taxReport.summary.realized_losses)}
              </p>
            </div>

            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <FileText className="w-5 h-5 text-purple-600" />
                </div>
                <span className="text-sm text-gray-600">P&L Neto</span>
              </div>
              <p
                className={`text-2xl font-bold ${
                  taxReport.summary.net_realized_pnl >= 0
                    ? "text-green-600"
                    : "text-red-600"
                }`}
              >
                {formatCurrency(taxReport.summary.net_realized_pnl)}
              </p>
            </div>
          </div>

          {/* Additional Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <span className="text-sm text-gray-600">Total Dividendos</span>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {formatCurrency(taxReport.summary.total_dividends)}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <span className="text-sm text-gray-600">Total Comisiones</span>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {formatCurrency(taxReport.summary.total_fees_paid)}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <span className="text-sm text-gray-600">Total Operaciones</span>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {taxReport.summary.total_trades}
              </p>
            </div>
          </div>

          {/* Remittances Summary */}
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Remesas del Año
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <span className="text-sm text-gray-600">
                  Total Enviado (USD)
                </span>
                <p className="text-xl font-bold text-gray-900 mt-1">
                  {formatCurrency(taxReport.summary.total_remittances_sent, "USD")}
                </p>
              </div>
              <div>
                <span className="text-sm text-gray-600">
                  Total Recibido (MXN)
                </span>
                <p className="text-xl font-bold text-gray-900 mt-1">
                  {formatCurrency(taxReport.summary.total_remittances_received)}
                </p>
              </div>
            </div>
          </div>

          {/* Transactions Table */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                Movimientos del Año
              </h3>
            </div>
            {taxReport.transactions.length === 0 ? (
              <div className="p-12 text-center">
                <Calendar className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500">
                  No hay movimientos registrados para {selectedYear}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Fecha
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Tipo
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                        Descripción
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                        Monto
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                        G/P
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {taxReport.transactions.slice(0, 50).map((tx, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm text-gray-600 whitespace-nowrap">
                          {format(new Date(tx.date), "dd/MM/yyyy")}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${
                              tx.type === "investment"
                                ? "bg-blue-100 text-blue-800"
                                : tx.type === "dividend"
                                  ? "bg-green-100 text-green-800"
                                  : tx.type === "trade"
                                    ? "bg-purple-100 text-purple-800"
                                    : "bg-orange-100 text-orange-800"
                            }`}
                          >
                            {transactionTypeLabels[tx.type] || tx.type}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          {tx.description}
                        </td>
                        <td
                          className={`px-6 py-4 text-sm text-right font-medium ${
                            tx.amount >= 0 ? "text-green-600" : "text-red-600"
                          }`}
                        >
                          {formatCurrency(Math.abs(tx.amount), tx.currency)}
                          {tx.amount < 0 && " (-)"}
                        </td>
                        <td
                          className={`px-6 py-4 text-sm text-right font-medium ${
                            tx.gain_loss
                              ? tx.gain_loss >= 0
                                ? "text-green-600"
                                : "text-red-600"
                              : "text-gray-400"
                          }`}
                        >
                          {tx.gain_loss
                            ? formatCurrency(tx.gain_loss)
                            : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {taxReport.transactions.length > 50 && (
                  <div className="px-6 py-4 text-center text-sm text-gray-500 border-t border-gray-100">
                    Mostrando 50 de {taxReport.transactions.length} movimientos.
                    Descarga el PDF para ver todos.
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Disclaimer */}
          <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-amber-800">
              <p className="font-medium">Aviso importante</p>
              <p className="mt-1">
                Este reporte es únicamente informativo y no constituye asesoría
                fiscal. Consulta con un contador certificado para tu declaración
                anual. Los cálculos de ganancia/pérdida son aproximados y pueden
                variar según tu situación fiscal particular.
              </p>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">
            No hay datos disponibles para {selectedYear}
          </p>
        </div>
      )}
    </div>
  );
}
