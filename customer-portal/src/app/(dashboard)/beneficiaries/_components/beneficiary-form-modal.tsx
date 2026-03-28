"use client";

import { useState, useEffect } from "react";
import { X, User, Building2, CreditCard, Phone, Mail, MapPin } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useCreateBeneficiary,
  useUpdateBeneficiary,
} from "@/features/beneficiaries/hooks/use-beneficiaries";
import type { Beneficiary, RecipientInfo } from "@/types";

interface BeneficiaryFormModalProps {
  open: boolean;
  onClose: () => void;
  beneficiary?: Beneficiary | null;
}

interface FormData {
  nickname: string;
  name: string;
  bank_name: string;
  clabe: string;
  account_number: string;
  phone: string;
  email: string;
  country: string;
}

const COUNTRIES = [
  { code: "MX", name: "México", flag: "🇲🇽" },
  { code: "US", name: "Estados Unidos", flag: "🇺🇸" },
  { code: "CO", name: "Colombia", flag: "🇨🇴" },
  { code: "PE", name: "Perú", flag: "🇵🇪" },
  { code: "CL", name: "Chile", flag: "🇨🇱" },
  { code: "AR", name: "Argentina", flag: "🇦🇷" },
  { code: "BR", name: "Brasil", flag: "🇧🇷" },
  { code: "GT", name: "Guatemala", flag: "🇬🇹" },
  { code: "HN", name: "Honduras", flag: "🇭🇳" },
  { code: "SV", name: "El Salvador", flag: "🇸🇻" },
  { code: "EC", name: "Ecuador", flag: "🇪🇨" },
];

const MEXICAN_BANKS = [
  "BBVA México",
  "Santander",
  "Banorte",
  "Citibanamex",
  "HSBC",
  "Scotiabank",
  "Banco Azteca",
  "Inbursa",
  "BanCoppel",
  "Banregio",
  "Afirme",
  "Compartamos Banco",
  "Otro",
];

export function BeneficiaryFormModal({
  open,
  onClose,
  beneficiary,
}: BeneficiaryFormModalProps) {
  const isEditing = !!beneficiary;
  const createMutation = useCreateBeneficiary();
  const updateMutation = useUpdateBeneficiary();

  const [formData, setFormData] = useState<FormData>({
    nickname: "",
    name: "",
    bank_name: "",
    clabe: "",
    account_number: "",
    phone: "",
    email: "",
    country: "MX",
  });

  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>({});

  // Cargar datos cuando se edita
  useEffect(() => {
    if (beneficiary) {
      setFormData({
        nickname: beneficiary.nickname,
        name: beneficiary.recipient_info.name,
        bank_name: beneficiary.recipient_info.bank_name || "",
        clabe: beneficiary.recipient_info.clabe || "",
        account_number: beneficiary.recipient_info.account_number || "",
        phone: beneficiary.recipient_info.phone || "",
        email: beneficiary.recipient_info.email || "",
        country: beneficiary.recipient_info.country,
      });
    } else {
      setFormData({
        nickname: "",
        name: "",
        bank_name: "",
        clabe: "",
        account_number: "",
        phone: "",
        email: "",
        country: "MX",
      });
    }
    setErrors({});
  }, [beneficiary, open]);

  const handleChange = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Limpiar error al cambiar
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Partial<Record<keyof FormData, string>> = {};

    if (!formData.nickname.trim()) {
      newErrors.nickname = "El alias es requerido";
    }

    if (!formData.name.trim()) {
      newErrors.name = "El nombre es requerido";
    }

    if (!formData.bank_name) {
      newErrors.bank_name = "El banco es requerido";
    }

    // Validar CLABE para México
    if (formData.country === "MX") {
      if (!formData.clabe) {
        newErrors.clabe = "La CLABE es requerida para México";
      } else if (formData.clabe.length !== 18) {
        newErrors.clabe = "La CLABE debe tener 18 dígitos";
      } else if (!/^\d+$/.test(formData.clabe)) {
        newErrors.clabe = "La CLABE solo debe contener números";
      }
    } else if (!formData.account_number) {
      newErrors.account_number = "El número de cuenta es requerido";
    }

    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Email inválido";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    const recipient_info: RecipientInfo = {
      name: formData.name.trim(),
      bank_name: formData.bank_name,
      country: formData.country,
      ...(formData.clabe && { clabe: formData.clabe }),
      ...(formData.account_number && { account_number: formData.account_number }),
      ...(formData.phone && { phone: formData.phone }),
      ...(formData.email && { email: formData.email }),
    };

    try {
      if (isEditing && beneficiary) {
        await updateMutation.mutateAsync({
          id: beneficiary.id,
          nickname: formData.nickname.trim(),
          recipient_info,
        });
        toast.success("Beneficiario actualizado");
      } else {
        await createMutation.mutateAsync({
          nickname: formData.nickname.trim(),
          recipient_info,
        });
        toast.success("Beneficiario creado");
      }
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Error al guardar beneficiario"
      );
    }
  };

  if (!open) return null;

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-background rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-hidden animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">
            {isEditing ? "Editar beneficiario" : "Nuevo beneficiario"}
          </h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4 overflow-y-auto max-h-[calc(90vh-140px)]">
          {/* Alias */}
          <div className="space-y-2">
            <Label htmlFor="nickname" className="flex items-center gap-2">
              <User className="h-4 w-4" />
              Alias / Apodo
            </Label>
            <Input
              id="nickname"
              placeholder="Ej: Mamá, Juan trabajo, etc."
              value={formData.nickname}
              onChange={(e) => handleChange("nickname", e.target.value)}
              className={errors.nickname ? "border-destructive" : ""}
            />
            {errors.nickname && (
              <p className="text-xs text-destructive">{errors.nickname}</p>
            )}
          </div>

          {/* Nombre completo */}
          <div className="space-y-2">
            <Label htmlFor="name">Nombre completo del beneficiario</Label>
            <Input
              id="name"
              placeholder="Nombre como aparece en el banco"
              value={formData.name}
              onChange={(e) => handleChange("name", e.target.value)}
              className={errors.name ? "border-destructive" : ""}
            />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name}</p>
            )}
          </div>

          {/* País */}
          <div className="space-y-2">
            <Label htmlFor="country" className="flex items-center gap-2">
              <MapPin className="h-4 w-4" />
              País de destino
            </Label>
            <select
              id="country"
              value={formData.country}
              onChange={(e) => handleChange("country", e.target.value)}
              className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
            >
              {COUNTRIES.map((country) => (
                <option key={country.code} value={country.code}>
                  {country.flag} {country.name}
                </option>
              ))}
            </select>
          </div>

          {/* Banco */}
          <div className="space-y-2">
            <Label htmlFor="bank_name" className="flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              Banco
            </Label>
            {formData.country === "MX" ? (
              <select
                id="bank_name"
                value={formData.bank_name}
                onChange={(e) => handleChange("bank_name", e.target.value)}
                className={`w-full h-10 px-3 rounded-md border bg-background text-sm ${
                  errors.bank_name ? "border-destructive" : "border-input"
                }`}
              >
                <option value="">Selecciona un banco</option>
                {MEXICAN_BANKS.map((bank) => (
                  <option key={bank} value={bank}>
                    {bank}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                id="bank_name"
                placeholder="Nombre del banco"
                value={formData.bank_name}
                onChange={(e) => handleChange("bank_name", e.target.value)}
                className={errors.bank_name ? "border-destructive" : ""}
              />
            )}
            {errors.bank_name && (
              <p className="text-xs text-destructive">{errors.bank_name}</p>
            )}
          </div>

          {/* CLABE o Cuenta */}
          {formData.country === "MX" ? (
            <div className="space-y-2">
              <Label htmlFor="clabe" className="flex items-center gap-2">
                <CreditCard className="h-4 w-4" />
                CLABE Interbancaria
              </Label>
              <Input
                id="clabe"
                placeholder="18 dígitos"
                value={formData.clabe}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, "").slice(0, 18);
                  handleChange("clabe", value);
                }}
                className={`font-mono ${errors.clabe ? "border-destructive" : ""}`}
                maxLength={18}
              />
              {errors.clabe && (
                <p className="text-xs text-destructive">{errors.clabe}</p>
              )}
              <p className="text-xs text-muted-foreground">
                {formData.clabe.length}/18 dígitos
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="account_number" className="flex items-center gap-2">
                <CreditCard className="h-4 w-4" />
                Número de cuenta
              </Label>
              <Input
                id="account_number"
                placeholder="Número de cuenta bancaria"
                value={formData.account_number}
                onChange={(e) => handleChange("account_number", e.target.value)}
                className={errors.account_number ? "border-destructive" : ""}
              />
              {errors.account_number && (
                <p className="text-xs text-destructive">{errors.account_number}</p>
              )}
            </div>
          )}

          {/* Teléfono (opcional) */}
          <div className="space-y-2">
            <Label htmlFor="phone" className="flex items-center gap-2">
              <Phone className="h-4 w-4" />
              Teléfono
              <span className="text-xs text-muted-foreground">(opcional)</span>
            </Label>
            <Input
              id="phone"
              type="tel"
              placeholder="+52 55 1234 5678"
              value={formData.phone}
              onChange={(e) => handleChange("phone", e.target.value)}
            />
          </div>

          {/* Email (opcional) */}
          <div className="space-y-2">
            <Label htmlFor="email" className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Email
              <span className="text-xs text-muted-foreground">(opcional)</span>
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="correo@ejemplo.com"
              value={formData.email}
              onChange={(e) => handleChange("email", e.target.value)}
              className={errors.email ? "border-destructive" : ""}
            />
            {errors.email && (
              <p className="text-xs text-destructive">{errors.email}</p>
            )}
          </div>
        </form>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t bg-muted/30">
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
            Cancelar
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting} isLoading={isSubmitting}>
            {isEditing ? "Guardar cambios" : "Crear beneficiario"}
          </Button>
        </div>
      </div>
    </div>
  );
}
