"use client";

import { useState } from "react";
import {
  Shield,
  Fingerprint,
  KeyRound,
  User,
  Building2,
  ArrowRight,
  Clock,
  Check,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/lib/utils";
import type {
  RemittanceQuote,
  RecipientInfo,
  PaymentMethod,
  DisbursementMethod,
} from "@/types";

interface ConfirmationStepProps {
  quote: RemittanceQuote;
  beneficiary: RecipientInfo;
  paymentMethod: PaymentMethod;
  disbursementMethod: DisbursementMethod;
  onConfirm: (signature: string) => Promise<void>;
  onBack: () => void;
}

type AuthMethod = "biometric" | "totp";

const paymentLabels: Record<PaymentMethod, string> = {
  spei: "Transferencia SPEI",
  wire_transfer: "Transferencia bancaria",
  card: "Tarjeta de débito",
  crypto: "Wallet crypto",
};

const disbursementLabels: Record<DisbursementMethod, string> = {
  bank_transfer: "Depósito bancario",
  mobile_wallet: "Wallet móvil",
  cash_pickup: "Retiro en efectivo",
  home_delivery: "Entrega a domicilio",
};

export function ConfirmationStep({
  quote,
  beneficiary,
  paymentMethod,
  disbursementMethod,
  onConfirm,
  onBack,
}: ConfirmationStepProps) {
  const [authMethod, setAuthMethod] = useState<AuthMethod>("biometric");
  const [totpCode, setTotpCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isVerified, setIsVerified] = useState(false);

  const handleBiometricAuth = async () => {
    try {
      // TODO: Implementar WebAuthn real
      // const credential = await navigator.credentials.get({...});

      // Simulación de autenticación biométrica
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setIsVerified(true);
      toast.success("Identidad verificada");
    } catch (error) {
      toast.error("Error al verificar biometría");
    }
  };

  const handleTotpVerify = () => {
    if (totpCode.length !== 6) {
      toast.error("Ingresa el código de 6 dígitos");
      return;
    }

    // TODO: Verificar código TOTP con backend
    setIsVerified(true);
    toast.success("Código verificado");
  };

  const handleConfirm = async () => {
    if (!isVerified) {
      toast.error("Verifica tu identidad primero");
      return;
    }

    setIsSubmitting(true);
    try {
      // Generar firma (en producción sería la firma WebAuthn o HMAC del TOTP)
      const signature = `verified_${Date.now()}`;
      await onConfirm(signature);
    } catch (error) {
      toast.error("Error al crear la remesa");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Resumen del envío</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Amount */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Tú envías</p>
              <p className="text-2xl font-bold">
                {formatCurrency(quote.total_to_pay, quote.currency_source)}
              </p>
            </div>
            <ArrowRight className="h-5 w-5 text-muted-foreground" />
            <div className="text-right">
              <p className="text-sm text-muted-foreground">Recibe</p>
              <p className="text-2xl font-bold text-primary">
                {formatCurrency(quote.amount_destination, quote.currency_destination)}
              </p>
            </div>
          </div>

          <Separator />

          {/* Beneficiary */}
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
              <User className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1">
              <p className="font-medium">{beneficiary.name}</p>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Building2 className="h-3 w-3" />
                {beneficiary.bank_name} • ****{beneficiary.clabe?.slice(-4)}
              </div>
            </div>
          </div>

          <Separator />

          {/* Details */}
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Método de pago</span>
              <span className="font-medium">{paymentLabels[paymentMethod]}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Entrega</span>
              <span className="font-medium">{disbursementLabels[disbursementMethod]}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Tasa de cambio</span>
              <span className="font-medium">
                1 {quote.currency_source} = {quote.exchange_rate_source_usd.toFixed(4)}{" "}
                {quote.currency_destination}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Comisiones</span>
              <span className="font-medium text-green-600">
                {formatCurrency(quote.total_fees, quote.currency_source)}
              </span>
            </div>
          </div>

          <Separator />

          {/* Delivery time */}
          <div className="flex items-center gap-2 text-sm">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Entrega estimada:</span>
            <Badge variant="secondary">{quote.estimated_delivery}</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Security Verification */}
      <Card className="border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="h-4 w-4 text-amber-600" />
            Verificación de seguridad
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Para proteger tu cuenta, confirma tu identidad antes de enviar{" "}
            <strong>{formatCurrency(quote.total_to_pay, quote.currency_source)}</strong>
          </p>

          {!isVerified ? (
            <>
              {/* Auth Method Selection */}
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setAuthMethod("biometric")}
                  className={`p-4 rounded-lg border-2 text-center transition-colors ${
                    authMethod === "biometric"
                      ? "border-primary bg-primary/5"
                      : "border-transparent bg-background hover:bg-muted"
                  }`}
                >
                  <Fingerprint className="h-6 w-6 mx-auto mb-2" />
                  <p className="text-sm font-medium">Biometría</p>
                  <p className="text-xs text-muted-foreground">FaceID / Huella</p>
                </button>
                <button
                  onClick={() => setAuthMethod("totp")}
                  className={`p-4 rounded-lg border-2 text-center transition-colors ${
                    authMethod === "totp"
                      ? "border-primary bg-primary/5"
                      : "border-transparent bg-background hover:bg-muted"
                  }`}
                >
                  <KeyRound className="h-6 w-6 mx-auto mb-2" />
                  <p className="text-sm font-medium">Autenticador</p>
                  <p className="text-xs text-muted-foreground">Código 6 dígitos</p>
                </button>
              </div>

              {/* Biometric Button */}
              {authMethod === "biometric" && (
                <Button
                  className="w-full h-12"
                  variant="secondary"
                  onClick={handleBiometricAuth}
                >
                  <Fingerprint className="h-5 w-5 mr-2" />
                  Usar biometría
                </Button>
              )}

              {/* TOTP Input */}
              {authMethod === "totp" && (
                <div className="space-y-3">
                  <Label>Código de autenticador</Label>
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      placeholder="000000"
                      value={totpCode}
                      onChange={(e) =>
                        setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                      }
                      className="text-center text-2xl tracking-widest font-mono"
                    />
                    <Button onClick={handleTotpVerify} disabled={totpCode.length !== 6}>
                      Verificar
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center gap-3 p-4 rounded-lg bg-green-100 dark:bg-green-900/30">
              <div className="h-8 w-8 rounded-full bg-green-500 flex items-center justify-center">
                <Check className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="font-medium text-green-800 dark:text-green-200">
                  Identidad verificada
                </p>
                <p className="text-xs text-green-600 dark:text-green-400">
                  Puedes confirmar el envío
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Warning */}
      <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/50">
        <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-muted-foreground">
          Al confirmar, aceptas que la información proporcionada es correcta.
          Las remesas no pueden ser revertidas una vez procesadas. Si hay un
          error en los datos del beneficiario, el dinero podría perderse.
        </p>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="outline" className="flex-1" onClick={onBack}>
          Volver
        </Button>
        <Button
          className="flex-1 h-12"
          onClick={handleConfirm}
          disabled={!isVerified || isSubmitting}
          isLoading={isSubmitting}
        >
          <Shield className="h-4 w-4 mr-2" />
          Confirmar y enviar
        </Button>
      </div>
    </div>
  );
}
