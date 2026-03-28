"use client";

import { useState } from "react";
import {
  Users,
  Plus,
  Search,
  Star,
  MoreVertical,
  Edit2,
  Trash2,
  Send,
  Building2,
  Phone,
  Mail,
  Copy,
  Check,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useBeneficiaries,
  useDeleteBeneficiary,
  useToggleFavorite,
} from "@/features/beneficiaries/hooks/use-beneficiaries";
import { BeneficiaryFormModal } from "./_components/beneficiary-form-modal";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { Beneficiary } from "@/types";

export default function BeneficiariesPage() {
  const [search, setSearch] = useState("");
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBeneficiary, setEditingBeneficiary] = useState<Beneficiary | null>(null);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const { data: beneficiaries = [], isLoading } = useBeneficiaries({
    favorites_only: showFavoritesOnly,
  });
  const deleteMutation = useDeleteBeneficiary();
  const toggleFavoriteMutation = useToggleFavorite();

  // Filtrar por búsqueda
  const filteredBeneficiaries = beneficiaries.filter((b) => {
    const searchLower = search.toLowerCase();
    return (
      b.nickname.toLowerCase().includes(searchLower) ||
      b.recipient_info.name.toLowerCase().includes(searchLower) ||
      b.recipient_info.bank_name?.toLowerCase().includes(searchLower) ||
      b.recipient_info.clabe?.includes(search) ||
      b.recipient_info.account_number?.includes(search)
    );
  });

  const handleEdit = (beneficiary: Beneficiary) => {
    setEditingBeneficiary(beneficiary);
    setIsModalOpen(true);
    setMenuOpen(null);
  };

  const handleDelete = async (id: string) => {
    if (confirm("¿Estás seguro de eliminar este beneficiario?")) {
      try {
        await deleteMutation.mutateAsync(id);
        toast.success("Beneficiario eliminado");
      } catch {
        toast.error("Error al eliminar beneficiario");
      }
    }
    setMenuOpen(null);
  };

  const handleToggleFavorite = async (id: string) => {
    try {
      await toggleFavoriteMutation.mutateAsync(id);
    } catch {
      toast.error("Error al actualizar favorito");
    }
  };

  const handleCopy = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    toast.success("Copiado al portapapeles");
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingBeneficiary(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="h-6 w-6" />
            Beneficiarios
          </h1>
          <p className="text-muted-foreground">
            Gestiona tus beneficiarios frecuentes para envíos más rápidos
          </p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nuevo beneficiario
        </Button>
      </div>

      {/* Filtros y búsqueda */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por nombre, banco o cuenta..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <Button
          variant={showFavoritesOnly ? "default" : "outline"}
          onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
          className="shrink-0"
        >
          <Star className={cn("h-4 w-4 mr-2", showFavoritesOnly && "fill-current")} />
          Favoritos
        </Button>
      </div>

      {/* Lista de beneficiarios */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4">
                <div className="h-20 bg-muted rounded" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filteredBeneficiaries.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Users className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-1">
              {search ? "No se encontraron resultados" : "Sin beneficiarios"}
            </h3>
            <p className="text-muted-foreground mb-4">
              {search
                ? "Intenta con otros términos de búsqueda"
                : "Agrega beneficiarios para enviar dinero más rápido"}
            </p>
            {!search && (
              <Button onClick={() => setIsModalOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Agregar beneficiario
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredBeneficiaries.map((beneficiary) => (
            <BeneficiaryCard
              key={beneficiary.id}
              beneficiary={beneficiary}
              isMenuOpen={menuOpen === beneficiary.id}
              onMenuToggle={() =>
                setMenuOpen(menuOpen === beneficiary.id ? null : beneficiary.id)
              }
              onEdit={() => handleEdit(beneficiary)}
              onDelete={() => handleDelete(beneficiary.id)}
              onToggleFavorite={() => handleToggleFavorite(beneficiary.id)}
              onCopy={handleCopy}
              copiedId={copiedId}
            />
          ))}
        </div>
      )}

      {/* Modal de crear/editar */}
      <BeneficiaryFormModal
        open={isModalOpen}
        onClose={handleCloseModal}
        beneficiary={editingBeneficiary}
      />
    </div>
  );
}

interface BeneficiaryCardProps {
  beneficiary: Beneficiary;
  isMenuOpen: boolean;
  onMenuToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onToggleFavorite: () => void;
  onCopy: (text: string, id: string) => void;
  copiedId: string | null;
}

function BeneficiaryCard({
  beneficiary,
  isMenuOpen,
  onMenuToggle,
  onEdit,
  onDelete,
  onToggleFavorite,
  onCopy,
  copiedId,
}: BeneficiaryCardProps) {
  const { recipient_info } = beneficiary;
  const accountDisplay = recipient_info.clabe || recipient_info.account_number || recipient_info.iban;
  const accountId = `${beneficiary.id}-account`;

  return (
    <Card className="group relative overflow-hidden hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        {/* Header con nombre y favorito */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold truncate">{beneficiary.nickname}</h3>
              {beneficiary.is_favorite && (
                <Star className="h-4 w-4 text-yellow-500 fill-yellow-500 shrink-0" />
              )}
            </div>
            <p className="text-sm text-muted-foreground truncate">
              {recipient_info.name}
            </p>
          </div>

          {/* Menú de acciones */}
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onMenuToggle}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>

            {isMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={onMenuToggle}
                />
                <div className="absolute right-0 top-full mt-1 w-48 bg-popover border rounded-lg shadow-lg z-20 py-1">
                  <button
                    onClick={onToggleFavorite}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted"
                  >
                    <Star
                      className={cn(
                        "h-4 w-4",
                        beneficiary.is_favorite && "fill-yellow-500 text-yellow-500"
                      )}
                    />
                    {beneficiary.is_favorite ? "Quitar de favoritos" : "Agregar a favoritos"}
                  </button>
                  <button
                    onClick={onEdit}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted"
                  >
                    <Edit2 className="h-4 w-4" />
                    Editar
                  </button>
                  <button
                    onClick={onDelete}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="h-4 w-4" />
                    Eliminar
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Información bancaria */}
        <div className="space-y-2 text-sm">
          {recipient_info.bank_name && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Building2 className="h-4 w-4 shrink-0" />
              <span className="truncate">{recipient_info.bank_name}</span>
            </div>
          )}

          {accountDisplay && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="font-mono text-xs truncate flex-1">
                {recipient_info.clabe ? `CLABE: ${accountDisplay}` : accountDisplay}
              </span>
              <button
                onClick={() => onCopy(accountDisplay, accountId)}
                className="shrink-0 p-1 hover:bg-muted rounded"
              >
                {copiedId === accountId ? (
                  <Check className="h-3 w-3 text-green-500" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </button>
            </div>
          )}

          {recipient_info.phone && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Phone className="h-4 w-4 shrink-0" />
              <span>{recipient_info.phone}</span>
            </div>
          )}

          {recipient_info.email && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Mail className="h-4 w-4 shrink-0" />
              <span className="truncate">{recipient_info.email}</span>
            </div>
          )}
        </div>

        {/* Footer con país y última fecha */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t">
          <Badge variant="outline" className="text-xs">
            {getCountryFlag(recipient_info.country)} {recipient_info.country}
          </Badge>

          {beneficiary.last_used_at && (
            <span className="text-xs text-muted-foreground">
              Usado {formatRelativeTime(beneficiary.last_used_at)}
            </span>
          )}
        </div>

        {/* Botón de enviar */}
        <Link
          href={`/remittances/new?beneficiary=${beneficiary.id}`}
          className="mt-3 w-full"
        >
          <Button variant="outline" size="sm" className="w-full">
            <Send className="h-4 w-4 mr-2" />
            Enviar dinero
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

// Helper para obtener bandera de país
function getCountryFlag(countryCode: string): string {
  const flags: Record<string, string> = {
    MX: "🇲🇽",
    US: "🇺🇸",
    CO: "🇨🇴",
    PE: "🇵🇪",
    CL: "🇨🇱",
    AR: "🇦🇷",
    BR: "🇧🇷",
    ES: "🇪🇸",
    GT: "🇬🇹",
    HN: "🇭🇳",
    SV: "🇸🇻",
    EC: "🇪🇨",
  };
  return flags[countryCode] || "🌎";
}
