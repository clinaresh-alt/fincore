"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Calculator,
  User,
  CreditCard,
  CheckCircle,
  Clock,
  AlertCircle,
  Building2,
  Smartphone,
  Banknote,
  Truck,
  RefreshCw,
  Info,
  Shield,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { remittancesAPI } from "@/lib/api-client";
import { RemittanceQuote, PaymentMethod, DisbursementMethod, RemittanceCurrency } from "@/types";
import { formatCurrency } from "@/lib/utils";

const CURRENCIES: { value: RemittanceCurrency; label: string; flag: string }[] = [
  { value: "USD", label: "Dolar (USD)", flag: "US" },
  { value: "MXN", label: "Peso Mexicano (MXN)", flag: "MX" },
  { value: "EUR", label: "Euro (EUR)", flag: "EU" },
  { value: "CLP", label: "Peso Chileno (CLP)", flag: "CL" },
  { value: "COP", label: "Peso Colombiano (COP)", flag: "CO" },
  { value: "PEN", label: "Sol Peruano (PEN)", flag: "PE" },
  { value: "BRL", label: "Real Brasileno (BRL)", flag: "BR" },
  { value: "ARS", label: "Peso Argentino (ARS)", flag: "AR" },
];

const PAYMENT_METHODS: { value: PaymentMethod; label: string; icon: React.ElementType }[] = [
  { value: "spei", label: "SPEI", icon: Building2 },
  { value: "wire_transfer", label: "Transferencia Bancaria", icon: Building2 },
  { value: "card", label: "Tarjeta", icon: CreditCard },
  { value: "crypto", label: "Cripto (USDC)", icon: Shield },
];

const DISBURSEMENT_METHODS: { value: DisbursementMethod; label: string; icon: React.ElementType; description: string }[] = [
  { value: "bank_transfer", label: "Transferencia Bancaria", icon: Building2, description: "Deposito directo a cuenta" },
  { value: "mobile_wallet", label: "Billetera Movil", icon: Smartphone, description: "Envio a wallet digital" },
  { value: "cash_pickup", label: "Retiro en Efectivo", icon: Banknote, description: "Cobro en sucursal" },
  { value: "home_delivery", label: "Entrega a Domicilio", icon: Truck, description: "Efectivo en casa" },
];

const COUNTRIES = [
  { value: "MX", label: "Mexico" },
  { value: "US", label: "Estados Unidos" },
  { value: "CL", label: "Chile" },
  { value: "CO", label: "Colombia" },
  { value: "PE", label: "Peru" },
  { value: "BR", label: "Brasil" },
  { value: "AR", label: "Argentina" },
  { value: "ES", label: "Espana" },
];

type Step = "amount" | "recipient" | "payment" | "review";

export default function NewRemittancePage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("amount");
  const [loading, setLoading] = useState(false);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<RemittanceQuote | null>(null);

  // Form data
  const [formData, setFormData] = useState({
    // Amount step
    amount_source: "",
    currency_source: "USD" as RemittanceCurrency,
    currency_destination: "MXN" as RemittanceCurrency,
    // Recipient step
    recipient_name: "",
    recipient_email: "",
    recipient_phone: "",
    recipient_country: "MX",
    bank_name: "",
    bank_account: "",
    clabe: "",
    // Payment step
    payment_method: "spei" as PaymentMethod,
    disbursement_method: "bank_transfer" as DisbursementMethod,
    notes: "",
  });

  const updateForm = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear quote when amount changes
    if (field === "amount_source" || field === "currency_source" || field === "currency_destination") {
      setQuote(null);
    }
  };

  const getQuote = async () => {
    if (!formData.amount_source || parseFloat(formData.amount_source) <= 0) {
      setError("Ingresa un monto valido");
      return;
    }

    setQuoteLoading(true);
    setError(null);
    try {
      const quoteData = await remittancesAPI.getQuote({
        amount_source: parseFloat(formData.amount_source),
        currency_source: formData.currency_source,
        currency_destination: formData.currency_destination,
      });
      setQuote(quoteData);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al obtener cotizacion");
    } finally {
      setQuoteLoading(false);
    }
  };

  const validateStep = (): boolean => {
    setError(null);

    switch (step) {
      case "amount":
        if (!quote) {
          setError("Obtén una cotización primero");
          return false;
        }
        return true;

      case "recipient":
        if (!formData.recipient_name.trim()) {
          setError("El nombre del beneficiario es requerido");
          return false;
        }
        if (formData.disbursement_method === "bank_transfer") {
          if (formData.recipient_country === "MX" && !formData.clabe) {
            setError("La CLABE es requerida para transferencias en Mexico");
            return false;
          }
          if (formData.recipient_country !== "MX" && !formData.bank_account) {
            setError("El número de cuenta es requerido");
            return false;
          }
        }
        return true;

      case "payment":
        return true;

      default:
        return true;
    }
  };

  const nextStep = () => {
    if (!validateStep()) return;

    const steps: Step[] = ["amount", "recipient", "payment", "review"];
    const currentIndex = steps.indexOf(step);
    if (currentIndex < steps.length - 1) {
      setStep(steps[currentIndex + 1]);
    }
  };

  const prevStep = () => {
    const steps: Step[] = ["amount", "recipient", "payment", "review"];
    const currentIndex = steps.indexOf(step);
    if (currentIndex > 0) {
      setStep(steps[currentIndex - 1]);
    }
  };

  const submitRemittance = async () => {
    if (!quote) return;

    setLoading(true);
    setError(null);
    try {
      const result = await remittancesAPI.create({
        amount_fiat_source: parseFloat(formData.amount_source),
        currency_source: formData.currency_source,
        currency_destination: formData.currency_destination,
        recipient_info: {
          full_name: formData.recipient_name,
          email: formData.recipient_email || undefined,
          phone: formData.recipient_phone || undefined,
          country: formData.recipient_country,
          bank_name: formData.bank_name || undefined,
          bank_account: formData.bank_account || undefined,
          clabe: formData.clabe || undefined,
        },
        payment_method: formData.payment_method,
        disbursement_method: formData.disbursement_method,
        notes: formData.notes || undefined,
      });

      // Redirect to detail page
      router.push(`/remittances/${result.remittance?.id || result.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al crear la remesa");
    } finally {
      setLoading(false);
    }
  };

  const steps: { key: Step; label: string; icon: React.ElementType }[] = [
    { key: "amount", label: "Monto", icon: Calculator },
    { key: "recipient", label: "Beneficiario", icon: User },
    { key: "payment", label: "Pago", icon: CreditCard },
    { key: "review", label: "Confirmar", icon: CheckCircle },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/remittances">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Nueva Remesa</h1>
          <p className="text-muted-foreground">
            Envia dinero de forma segura con blockchain
          </p>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-between">
        {steps.map((s, index) => {
          const Icon = s.icon;
          const isActive = s.key === step;
          const isPast = steps.findIndex((x) => x.key === step) > index;

          return (
            <div key={s.key} className="flex items-center">
              <div
                className={`flex items-center gap-2 px-4 py-2 rounded-full transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : isPast
                    ? "bg-green-100 text-green-700"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {isPast ? (
                  <CheckCircle className="h-4 w-4" />
                ) : (
                  <Icon className="h-4 w-4" />
                )}
                <span className="text-sm font-medium hidden sm:inline">{s.label}</span>
              </div>
              {index < steps.length - 1 && (
                <div className={`h-0.5 w-8 mx-2 ${isPast ? "bg-green-500" : "bg-muted"}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertCircle className="h-5 w-5" />
          {error}
        </div>
      )}

      {/* Step Content */}
      <Card>
        {/* STEP 1: Amount */}
        {step === "amount" && (
          <>
            <CardHeader>
              <CardTitle>Monto a Enviar</CardTitle>
              <CardDescription>
                Selecciona las monedas y el monto de tu transferencia
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Envias</Label>
                  <div className="flex gap-2">
                    <Input
                      type="number"
                      placeholder="0.00"
                      value={formData.amount_source}
                      onChange={(e) => updateForm("amount_source", e.target.value)}
                      className="flex-1"
                    />
                    <Select
                      value={formData.currency_source}
                      onValueChange={(v) => updateForm("currency_source", v)}
                    >
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CURRENCIES.map((c) => (
                          <SelectItem key={c.value} value={c.value}>
                            {c.value}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Recibe</Label>
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      readOnly
                      value={quote ? formatCurrency(quote.recipient_receives, formData.currency_destination) : "-"}
                      className="flex-1 bg-muted"
                    />
                    <Select
                      value={formData.currency_destination}
                      onValueChange={(v) => updateForm("currency_destination", v)}
                    >
                      <SelectTrigger className="w-32">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {CURRENCIES.map((c) => (
                          <SelectItem key={c.value} value={c.value}>
                            {c.value}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <Button
                onClick={getQuote}
                disabled={quoteLoading || !formData.amount_source}
                className="w-full"
                variant="outline"
              >
                {quoteLoading ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Calculator className="h-4 w-4 mr-2" />
                )}
                Obtener Cotizacion
              </Button>

              {quote && (
                <div className="bg-muted/50 rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Tipo de cambio</span>
                    <span className="font-medium">
                      1 {formData.currency_source} = {quote.exchange_rate_usd_destination.toFixed(4)} {formData.currency_destination}
                    </span>
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Comision FinCore (1.5%)</span>
                    <span>{formatCurrency(quote.platform_fee, formData.currency_source)}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Costo de red (est.)</span>
                    <span>{formatCurrency(quote.network_fee_estimate, "USD")}</span>
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between font-medium">
                    <span>Total a pagar</span>
                    <span className="text-lg">{formatCurrency(quote.total_to_pay, formData.currency_source)}</span>
                  </div>
                  <div className="flex items-center justify-between font-medium text-green-600">
                    <span>Beneficiario recibe</span>
                    <span className="text-lg">{formatCurrency(quote.recipient_receives, formData.currency_destination)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground mt-2">
                    <Clock className="h-3 w-3" />
                    Cotizacion valida por 15 minutos
                  </div>
                </div>
              )}
            </CardContent>
          </>
        )}

        {/* STEP 2: Recipient */}
        {step === "recipient" && (
          <>
            <CardHeader>
              <CardTitle>Datos del Beneficiario</CardTitle>
              <CardDescription>
                Informacion de quien recibira el dinero
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2 md:col-span-2">
                  <Label>Nombre Completo *</Label>
                  <Input
                    placeholder="Nombre del beneficiario"
                    value={formData.recipient_name}
                    onChange={(e) => updateForm("recipient_name", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input
                    type="email"
                    placeholder="correo@ejemplo.com"
                    value={formData.recipient_email}
                    onChange={(e) => updateForm("recipient_email", e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Telefono</Label>
                  <Input
                    type="tel"
                    placeholder="+52 555 123 4567"
                    value={formData.recipient_phone}
                    onChange={(e) => updateForm("recipient_phone", e.target.value)}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label>Pais *</Label>
                  <Select
                    value={formData.recipient_country}
                    onValueChange={(v) => updateForm("recipient_country", v)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {COUNTRIES.map((c) => (
                        <SelectItem key={c.value} value={c.value}>
                          {c.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Separator />

              <div className="space-y-2">
                <Label>Metodo de Desembolso</Label>
                <div className="grid gap-3 md:grid-cols-2">
                  {DISBURSEMENT_METHODS.map((method) => {
                    const Icon = method.icon;
                    const isSelected = formData.disbursement_method === method.value;
                    return (
                      <div
                        key={method.value}
                        onClick={() => updateForm("disbursement_method", method.value)}
                        className={`p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                          isSelected
                            ? "border-primary bg-primary/5"
                            : "border-muted hover:border-muted-foreground/50"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <Icon className={`h-5 w-5 ${isSelected ? "text-primary" : "text-muted-foreground"}`} />
                          <div>
                            <div className="font-medium">{method.label}</div>
                            <div className="text-xs text-muted-foreground">{method.description}</div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {formData.disbursement_method === "bank_transfer" && (
                <div className="space-y-4 pt-4">
                  <div className="space-y-2">
                    <Label>Banco</Label>
                    <Input
                      placeholder="Nombre del banco"
                      value={formData.bank_name}
                      onChange={(e) => updateForm("bank_name", e.target.value)}
                    />
                  </div>
                  {formData.recipient_country === "MX" ? (
                    <div className="space-y-2">
                      <Label>CLABE *</Label>
                      <Input
                        placeholder="18 digitos"
                        maxLength={18}
                        value={formData.clabe}
                        onChange={(e) => updateForm("clabe", e.target.value)}
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label>Numero de Cuenta *</Label>
                      <Input
                        placeholder="Numero de cuenta bancaria"
                        value={formData.bank_account}
                        onChange={(e) => updateForm("bank_account", e.target.value)}
                      />
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </>
        )}

        {/* STEP 3: Payment */}
        {step === "payment" && (
          <>
            <CardHeader>
              <CardTitle>Metodo de Pago</CardTitle>
              <CardDescription>
                Como deseas depositar los fondos
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-3">
                {PAYMENT_METHODS.map((method) => {
                  const Icon = method.icon;
                  const isSelected = formData.payment_method === method.value;
                  return (
                    <div
                      key={method.value}
                      onClick={() => updateForm("payment_method", method.value)}
                      className={`p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "border-muted hover:border-muted-foreground/50"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className={`h-5 w-5 ${isSelected ? "text-primary" : "text-muted-foreground"}`} />
                        <div className="font-medium">{method.label}</div>
                        {method.value === "crypto" && (
                          <Badge variant="secondary" className="ml-auto">
                            Sin comision adicional
                          </Badge>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="space-y-2">
                <Label>Notas (opcional)</Label>
                <Textarea
                  placeholder="Concepto o mensaje para el beneficiario"
                  value={formData.notes}
                  onChange={(e) => updateForm("notes", e.target.value)}
                  rows={3}
                />
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex gap-3">
                <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-blue-700">
                  <p className="font-medium">Escrow Blockchain</p>
                  <p className="mt-1">
                    Tus fondos seran bloqueados en un contrato inteligente por 48 horas.
                    Si el desembolso no se completa, recibiras un reembolso automatico.
                  </p>
                </div>
              </div>
            </CardContent>
          </>
        )}

        {/* STEP 4: Review */}
        {step === "review" && quote && (
          <>
            <CardHeader>
              <CardTitle>Confirmar Remesa</CardTitle>
              <CardDescription>
                Revisa los detalles antes de enviar
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Transfer Summary */}
              <div className="bg-gradient-to-r from-primary/10 to-primary/5 rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <div className="text-sm text-muted-foreground">Envias</div>
                    <div className="text-2xl font-bold">
                      {formatCurrency(quote.total_to_pay, formData.currency_source)}
                    </div>
                  </div>
                  <ArrowRight className="h-6 w-6 text-muted-foreground" />
                  <div className="text-right">
                    <div className="text-sm text-muted-foreground">Recibe</div>
                    <div className="text-2xl font-bold text-green-600">
                      {formatCurrency(quote.recipient_receives, formData.currency_destination)}
                    </div>
                  </div>
                </div>
                <Separator />
                <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Tipo de cambio</span>
                    <div className="font-medium">
                      1 {formData.currency_source} = {quote.exchange_rate_usd_destination.toFixed(4)} {formData.currency_destination}
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Comisiones</span>
                    <div className="font-medium">{formatCurrency(quote.total_fees, formData.currency_source)}</div>
                  </div>
                </div>
              </div>

              {/* Recipient */}
              <div className="space-y-3">
                <h4 className="font-medium flex items-center gap-2">
                  <User className="h-4 w-4" /> Beneficiario
                </h4>
                <div className="bg-muted/50 rounded-lg p-4 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Nombre</span>
                    <span className="font-medium">{formData.recipient_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Pais</span>
                    <span>{COUNTRIES.find(c => c.value === formData.recipient_country)?.label}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Metodo</span>
                    <span>{DISBURSEMENT_METHODS.find(m => m.value === formData.disbursement_method)?.label}</span>
                  </div>
                  {formData.clabe && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">CLABE</span>
                      <span className="font-mono">{formData.clabe}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Payment */}
              <div className="space-y-3">
                <h4 className="font-medium flex items-center gap-2">
                  <CreditCard className="h-4 w-4" /> Pago
                </h4>
                <div className="bg-muted/50 rounded-lg p-4 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Metodo</span>
                    <span className="font-medium">
                      {PAYMENT_METHODS.find(m => m.value === formData.payment_method)?.label}
                    </span>
                  </div>
                </div>
              </div>

              {/* Warning */}
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex gap-3">
                <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-amber-700">
                  <p>
                    Al confirmar, aceptas los terminos del servicio. Los fondos seran
                    bloqueados en escrow por 48 horas maximo.
                  </p>
                </div>
              </div>
            </CardContent>
          </>
        )}

        {/* Footer with navigation */}
        <CardFooter className="flex justify-between">
          {step !== "amount" ? (
            <Button variant="outline" onClick={prevStep}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Atras
            </Button>
          ) : (
            <div />
          )}

          {step !== "review" ? (
            <Button onClick={nextStep} disabled={step === "amount" && !quote}>
              Continuar
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button onClick={submitRemittance} disabled={loading}>
              {loading ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <CheckCircle className="h-4 w-4 mr-2" />
              )}
              Confirmar Remesa
            </Button>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}
