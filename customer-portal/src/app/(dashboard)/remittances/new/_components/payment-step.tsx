"use client";

import { useState } from "react";
import { Building2, CreditCard, Wallet, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCurrency } from "@/lib/utils";
import type { PaymentMethod, DisbursementMethod, RemittanceCurrency } from "@/types";

interface PaymentStepProps {
  onSelect: (payment: PaymentMethod, disbursement: DisbursementMethod) => void;
  onBack: () => void;
  amount: number;
  currency: RemittanceCurrency;
}

interface PaymentOption {
  id: PaymentMethod;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  fee: string;
  time: string;
  recommended?: boolean;
}

interface DisbursementOption {
  id: DisbursementMethod;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const paymentOptions: PaymentOption[] = [
  {
    id: "spei",
    name: "Transferencia SPEI",
    description: "Desde tu banca en línea",
    icon: Building2,
    fee: "Sin comisión",
    time: "Inmediato",
    recommended: true,
  },
  {
    id: "card",
    name: "Tarjeta de débito",
    description: "Visa, Mastercard",
    icon: CreditCard,
    fee: "+2.5%",
    time: "Inmediato",
  },
  {
    id: "crypto",
    name: "Desde wallet crypto",
    description: "USDC, USDT",
    icon: Wallet,
    fee: "Solo gas",
    time: "~5 min",
  },
];

const disbursementOptions: DisbursementOption[] = [
  {
    id: "bank_transfer",
    name: "Transferencia bancaria",
    description: "Depósito directo a cuenta",
    icon: Building2,
  },
  {
    id: "mobile_wallet",
    name: "Wallet móvil",
    description: "Mercado Pago, etc.",
    icon: Wallet,
  },
  {
    id: "cash_pickup",
    name: "Retiro en efectivo",
    description: "En sucursal autorizada",
    icon: CreditCard,
  },
];

export function PaymentStep({ onSelect, onBack, amount, currency }: PaymentStepProps) {
  const [selectedPayment, setSelectedPayment] = useState<PaymentMethod>("spei");
  const [selectedDisbursement, setSelectedDisbursement] = useState<DisbursementMethod>("bank_transfer");

  const handleContinue = () => {
    onSelect(selectedPayment, selectedDisbursement);
  };

  return (
    <div className="space-y-6">
      {/* Payment Method */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">¿Cómo quieres pagar?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {paymentOptions.map((option) => {
            const isSelected = selectedPayment === option.id;
            const Icon = option.icon;

            return (
              <button
                key={option.id}
                onClick={() => setSelectedPayment(option.id)}
                className={`w-full flex items-center gap-3 p-4 rounded-lg border-2 transition-colors text-left ${
                  isSelected
                    ? "border-primary bg-primary/5"
                    : "border-transparent bg-muted/50 hover:bg-muted"
                }`}
              >
                <div
                  className={`h-10 w-10 rounded-lg flex items-center justify-center ${
                    isSelected ? "bg-primary/10 text-primary" : "bg-background"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{option.name}</p>
                    {option.recommended && (
                      <Badge variant="secondary" className="text-[10px]">
                        Recomendado
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {option.description}
                  </p>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-medium ${
                    option.fee === "Sin comisión" ? "text-green-600" : ""
                  }`}>
                    {option.fee}
                  </p>
                  <p className="text-xs text-muted-foreground">{option.time}</p>
                </div>
                {isSelected && (
                  <div className="h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                    <Check className="h-3 w-3 text-primary-foreground" />
                  </div>
                )}
              </button>
            );
          })}
        </CardContent>
      </Card>

      {/* Disbursement Method */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">¿Cómo recibirá el dinero?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {disbursementOptions.map((option) => {
            const isSelected = selectedDisbursement === option.id;
            const Icon = option.icon;

            return (
              <button
                key={option.id}
                onClick={() => setSelectedDisbursement(option.id)}
                className={`w-full flex items-center gap-3 p-3 rounded-lg border-2 transition-colors text-left ${
                  isSelected
                    ? "border-primary bg-primary/5"
                    : "border-transparent bg-muted/50 hover:bg-muted"
                }`}
              >
                <div
                  className={`h-8 w-8 rounded-lg flex items-center justify-center ${
                    isSelected ? "bg-primary/10 text-primary" : "bg-background"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-sm">{option.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {option.description}
                  </p>
                </div>
                {isSelected && (
                  <div className="h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                    <Check className="h-3 w-3 text-primary-foreground" />
                  </div>
                )}
              </button>
            );
          })}
        </CardContent>
      </Card>

      {/* Summary */}
      <Card className="bg-muted/30">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Total a pagar</span>
            <span className="text-xl font-bold">
              {formatCurrency(amount, currency)}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="outline" className="flex-1" onClick={onBack}>
          Volver
        </Button>
        <Button className="flex-1" onClick={handleContinue}>
          Continuar
        </Button>
      </div>
    </div>
  );
}
