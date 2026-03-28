"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, Search, Star, User, Building2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { isValidCLABE, getBankFromCLABE } from "@/lib/utils";
import type { RecipientInfo, Beneficiary } from "@/types";

const beneficiarySchema = z.object({
  name: z
    .string()
    .min(2, "El nombre debe tener al menos 2 caracteres")
    .max(100, "El nombre es muy largo"),
  bank_name: z.string().optional(),
  clabe: z
    .string()
    .length(18, "El CLABE debe tener 18 dígitos")
    .refine(isValidCLABE, "CLABE inválido"),
  email: z.string().email("Email inválido").optional().or(z.literal("")),
  phone: z.string().optional(),
});

type BeneficiaryForm = z.infer<typeof beneficiarySchema>;

interface BeneficiaryStepProps {
  onSelect: (recipient: RecipientInfo, id?: string) => void;
  onBack: () => void;
}

// Mock data - en producción vendría del backend
const savedBeneficiaries: Beneficiary[] = [
  {
    id: "1",
    user_id: "user1",
    nickname: "María García",
    recipient_info: {
      name: "María García López",
      bank_name: "BBVA México",
      clabe: "012180015678912345",
      country: "MX",
    },
    is_favorite: true,
    created_at: "2024-01-15",
    last_used_at: "2024-03-20",
  },
  {
    id: "2",
    user_id: "user1",
    nickname: "Juan Pérez",
    recipient_info: {
      name: "Juan Pérez Hernández",
      bank_name: "Banorte",
      clabe: "072180015678912346",
      country: "MX",
    },
    is_favorite: false,
    created_at: "2024-02-10",
  },
];

export function BeneficiaryStep({ onSelect, onBack }: BeneficiaryStepProps) {
  const [mode, setMode] = useState<"select" | "new">("select");
  const [searchQuery, setSearchQuery] = useState("");
  const [detectedBank, setDetectedBank] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isValid },
  } = useForm<BeneficiaryForm>({
    resolver: zodResolver(beneficiarySchema),
    mode: "onChange",
    defaultValues: {
      name: "",
      clabe: "",
      email: "",
      phone: "",
    },
  });

  const clabe = watch("clabe");

  // Detectar banco cuando cambia CLABE
  const handleClabeChange = (value: string) => {
    const cleanValue = value.replace(/\D/g, "").slice(0, 18);
    setValue("clabe", cleanValue);

    if (cleanValue.length >= 3) {
      const bank = getBankFromCLABE(cleanValue);
      setDetectedBank(bank);
      if (bank) {
        setValue("bank_name", bank);
      }
    } else {
      setDetectedBank(null);
    }
  };

  const onSubmit = (data: BeneficiaryForm) => {
    const recipient: RecipientInfo = {
      name: data.name,
      bank_name: data.bank_name || detectedBank || undefined,
      clabe: data.clabe,
      email: data.email || undefined,
      phone: data.phone || undefined,
      country: "MX",
    };
    onSelect(recipient);
  };

  const handleSelectBeneficiary = (beneficiary: Beneficiary) => {
    onSelect(beneficiary.recipient_info, beneficiary.id);
  };

  const filteredBeneficiaries = savedBeneficiaries.filter(
    (b) =>
      b.nickname.toLowerCase().includes(searchQuery.toLowerCase()) ||
      b.recipient_info.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (mode === "new") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Nuevo beneficiario
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nombre completo</Label>
              <Input
                id="name"
                placeholder="María García López"
                {...register("name")}
                error={!!errors.name}
              />
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="clabe">CLABE interbancaria</Label>
              <Input
                id="clabe"
                placeholder="018 dígitos"
                value={clabe}
                onChange={(e) => handleClabeChange(e.target.value)}
                maxLength={18}
                error={!!errors.clabe}
                rightIcon={
                  detectedBank ? (
                    <div className="flex items-center gap-1 text-green-600">
                      <Building2 className="h-3 w-3" />
                      <span className="text-xs">{detectedBank}</span>
                    </div>
                  ) : undefined
                }
              />
              {errors.clabe && (
                <p className="text-sm text-destructive">{errors.clabe.message}</p>
              )}
              {clabe.length > 0 && clabe.length < 18 && (
                <p className="text-xs text-muted-foreground">
                  {18 - clabe.length} dígitos restantes
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email (opcional)</Label>
              <Input
                id="email"
                type="email"
                placeholder="beneficiario@email.com"
                {...register("email")}
                error={!!errors.email}
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email.message}</p>
              )}
              <p className="text-xs text-muted-foreground">
                Le notificaremos cuando reciba el dinero
              </p>
            </div>

            <Separator />

            <div className="flex gap-3">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                onClick={() => setMode("select")}
              >
                Cancelar
              </Button>
              <Button type="submit" className="flex-1" disabled={!isValid}>
                Continuar
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar beneficiario..."
          className="pl-10"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {/* Saved Beneficiaries */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Beneficiarios guardados</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {filteredBeneficiaries.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No se encontraron beneficiarios
            </p>
          ) : (
            filteredBeneficiaries.map((beneficiary) => (
              <button
                key={beneficiary.id}
                onClick={() => handleSelectBeneficiary(beneficiary)}
                className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors text-left"
              >
                <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <span className="text-primary font-semibold text-sm">
                    {beneficiary.recipient_info.name
                      .split(" ")
                      .map((n) => n[0])
                      .slice(0, 2)
                      .join("")}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium truncate">
                      {beneficiary.recipient_info.name}
                    </p>
                    {beneficiary.is_favorite && (
                      <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {beneficiary.recipient_info.bank_name} •{" "}
                    ****{beneficiary.recipient_info.clabe?.slice(-4)}
                  </p>
                </div>
              </button>
            ))
          )}
        </CardContent>
      </Card>

      {/* New Beneficiary Button */}
      <Button
        variant="outline"
        className="w-full h-12"
        onClick={() => setMode("new")}
      >
        <Plus className="h-4 w-4 mr-2" />
        Nuevo beneficiario
      </Button>

      <Button variant="ghost" className="w-full" onClick={onBack}>
        Volver
      </Button>
    </div>
  );
}
