"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, Shield, User, CreditCard, ChevronRight } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { RemittanceCalculator } from "@/components/forms/remittance-calculator";
import { BeneficiaryStep } from "./_components/beneficiary-step";
import { PaymentStep } from "./_components/payment-step";
import { ConfirmationStep } from "./_components/confirmation-step";
import { useCreateRemittance } from "@/features/remittances/hooks/use-remittances";
import type { RemittanceQuote, RecipientInfo, PaymentMethod, DisbursementMethod, CreateRemittanceRequest } from "@/types";

type Step = "calculator" | "beneficiary" | "payment" | "confirmation";

const steps: { id: Step; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "calculator", label: "Monto", icon: CreditCard },
  { id: "beneficiary", label: "Beneficiario", icon: User },
  { id: "payment", label: "Pago", icon: CreditCard },
  { id: "confirmation", label: "Confirmar", icon: Shield },
];

export default function NewRemittancePage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<Step>("calculator");
  const [quote, setQuote] = useState<RemittanceQuote | null>(null);
  const [beneficiary, setBeneficiary] = useState<RecipientInfo | null>(null);
  const [beneficiaryId, setBeneficiaryId] = useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("spei");
  const [disbursementMethod, setDisbursementMethod] = useState<DisbursementMethod>("bank_transfer");

  // Hook para crear remesa
  const createRemittance = useCreateRemittance();

  const currentStepIndex = steps.findIndex((s) => s.id === currentStep);
  const progress = ((currentStepIndex + 1) / steps.length) * 100;

  const goBack = () => {
    const prevIndex = currentStepIndex - 1;
    if (prevIndex >= 0) {
      setCurrentStep(steps[prevIndex]!.id);
    } else {
      router.back();
    }
  };

  const goNext = () => {
    const nextIndex = currentStepIndex + 1;
    if (nextIndex < steps.length) {
      setCurrentStep(steps[nextIndex]!.id);
    }
  };

  const handleQuoteChange = (newQuote: RemittanceQuote | null) => {
    setQuote(newQuote);
  };

  const handleBeneficiarySelect = (info: RecipientInfo, id?: string) => {
    setBeneficiary(info);
    setBeneficiaryId(id ?? null);
    goNext();
  };

  const handlePaymentSelect = (payment: PaymentMethod, disbursement: DisbursementMethod) => {
    setPaymentMethod(payment);
    setDisbursementMethod(disbursement);
    goNext();
  };

  const handleConfirm = async (_signature: string) => {
    if (!quote || !beneficiary) {
      toast.error("Datos incompletos");
      return;
    }

    // Construir request para el backend
    const request: CreateRemittanceRequest = {
      amount_source: Number(quote.amount_source),
      currency_source: quote.currency_source,
      currency_destination: quote.currency_destination,
      payment_method: paymentMethod,
      disbursement_method: disbursementMethod,
      quote_id: quote.quote_id,
      recipient_info: beneficiary,
      ...(beneficiaryId && { recipient_id: beneficiaryId }),
    };

    try {
      const remittance = await createRemittance.mutateAsync(request);
      toast.success(`Remesa creada: ${remittance.reference_code}`);
      router.push(`/remittances/${remittance.id}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Error al crear la remesa";
      toast.error(message);
      throw error; // Re-throw para que el componente de confirmación maneje el estado
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={goBack}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-xl font-bold">Nueva remesa</h1>
          <p className="text-sm text-muted-foreground">
            Paso {currentStepIndex + 1} de {steps.length}
          </p>
        </div>
      </div>

      {/* Progress */}
      <div className="space-y-3">
        <Progress value={progress} className="h-2" />
        <div className="flex justify-between">
          {steps.map((step, index) => {
            const isCompleted = index < currentStepIndex;
            const isCurrent = step.id === currentStep;
            const StepIcon = step.icon;

            return (
              <div
                key={step.id}
                className={`flex items-center gap-2 ${
                  isCurrent
                    ? "text-primary"
                    : isCompleted
                    ? "text-green-600"
                    : "text-muted-foreground"
                }`}
              >
                <div
                  className={`h-8 w-8 rounded-full flex items-center justify-center ${
                    isCurrent
                      ? "bg-primary/10 text-primary"
                      : isCompleted
                      ? "bg-green-100 text-green-600 dark:bg-green-900/30"
                      : "bg-muted"
                  }`}
                >
                  {isCompleted ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <StepIcon className="h-4 w-4" />
                  )}
                </div>
                <span className="text-xs font-medium hidden md:inline">
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Step Content */}
      <div className="min-h-[400px]">
        {currentStep === "calculator" && (
          <div className="space-y-4">
            <RemittanceCalculator onQuoteChange={handleQuoteChange} />

            <Button
              className="w-full h-12"
              size="lg"
              disabled={!quote}
              onClick={goNext}
            >
              Continuar
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>

            {quote && (
              <p className="text-xs text-center text-muted-foreground">
                Esta cotización es válida por 15 minutos
              </p>
            )}
          </div>
        )}

        {currentStep === "beneficiary" && (
          <BeneficiaryStep
            onSelect={handleBeneficiarySelect}
            onBack={goBack}
          />
        )}

        {currentStep === "payment" && (
          <PaymentStep
            onSelect={handlePaymentSelect}
            onBack={goBack}
            amount={quote?.total_to_pay ?? 0}
            currency={quote?.currency_source ?? "USD"}
          />
        )}

        {currentStep === "confirmation" && quote && beneficiary && (
          <ConfirmationStep
            quote={quote}
            beneficiary={beneficiary}
            paymentMethod={paymentMethod}
            disbursementMethod={disbursementMethod}
            onConfirm={handleConfirm}
            onBack={goBack}
          />
        )}
      </div>
    </div>
  );
}
