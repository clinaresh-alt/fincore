"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// ==================== TYPES ====================

export type TicketCategory =
  | "general"
  | "account"
  | "trading"
  | "wallet"
  | "remittance"
  | "kyc"
  | "technical"
  | "billing"
  | "security"
  | "compliance";

export type TicketPriority = "low" | "medium" | "high" | "urgent";

export type TicketStatus =
  | "open"
  | "in_progress"
  | "waiting_user"
  | "waiting_third_party"
  | "resolved"
  | "closed";

export interface Ticket {
  id: string;
  ticket_number: string;
  user_id?: string;
  subject: string;
  description: string;
  category: TicketCategory;
  priority: TicketPriority;
  status: TicketStatus;
  assigned_to?: string;
  user_email?: string;
  user_name?: string;
  tags: string[];
  attachments: { filename: string; url: string; size: number; type: string }[];
  related_entity_type?: string;
  related_entity_id?: string;
  satisfaction_rating?: number;
  created_at: string;
  updated_at: string;
  first_response_at?: string;
  resolved_at?: string;
  closed_at?: string;
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  user_id?: string;
  message: string;
  is_internal: boolean;
  is_from_user: boolean;
  attachments: { filename: string; url: string; size: number; type: string }[];
  created_at: string;
  read_at?: string;
}

export interface TicketDetail {
  ticket: Ticket;
  messages: TicketMessage[];
}

export interface TicketListResponse {
  tickets: Ticket[];
  total: number;
  page: number;
  page_size: number;
}

export interface TicketCreateInput {
  subject: string;
  description: string;
  category?: TicketCategory;
  priority?: TicketPriority;
  related_entity_type?: string;
  related_entity_id?: string;
  attachments?: { filename: string; url: string; size: number; type: string }[];
}

export interface TicketMessageInput {
  message: string;
  attachments?: { filename: string; url: string; size: number; type: string }[];
}

// Status Page Types
export type SystemStatus =
  | "operational"
  | "degraded"
  | "partial_outage"
  | "major_outage"
  | "maintenance";

export interface StatusComponent {
  id: string;
  name: string;
  description?: string;
  group?: string;
  status: SystemStatus;
  display_order: number;
  last_incident_at?: string;
}

export interface StatusUpdate {
  id: string;
  message: string;
  status: SystemStatus;
  created_at: string;
}

export interface StatusIncident {
  id: string;
  component_id?: string;
  component_name?: string;
  title: string;
  description?: string;
  status: SystemStatus;
  is_scheduled: boolean;
  scheduled_for?: string;
  scheduled_until?: string;
  is_resolved: boolean;
  created_at: string;
  resolved_at?: string;
  updates: StatusUpdate[];
}

export interface StatusPage {
  overall_status: SystemStatus;
  components: StatusComponent[];
  active_incidents: StatusIncident[];
  scheduled_maintenances: StatusIncident[];
  recent_incidents: StatusIncident[];
  last_updated: string;
}

// Tax Center Types
export interface TaxYearSummary {
  year: number;
  total_investments: number;
  total_returns: number;
  total_dividends: number;
  total_trades: number;
  realized_gains: number;
  realized_losses: number;
  net_realized_pnl: number;
  total_fees_paid: number;
  total_remittances_sent: number;
  total_remittances_received: number;
}

export interface TaxTransaction {
  date: string;
  type: "investment" | "dividend" | "trade" | "remittance";
  description: string;
  amount: number;
  currency: string;
  cost_basis?: number;
  gain_loss?: number;
  reference_id: string;
}

export interface TaxReport {
  user_id: string;
  user_name: string;
  user_rfc?: string;
  year: number;
  generated_at: string;
  summary: TaxYearSummary;
  transactions: TaxTransaction[];
  download_url?: string;
}

// SAT 69-B Types
export interface SAT69BCheckResult {
  rfc: string;
  is_listed: boolean;
  status: "clean" | "listed_definitive" | "listed_presumed" | "listed_favorable";
  list_type?: "69-B" | "69-B Bis";
  publication_date?: string;
  reason?: string;
  checked_at: string;
  source: string;
}

// Chat Config
export interface ChatConfig {
  provider: "crisp" | "intercom" | "none";
  website_id?: string;
  app_id?: string;
  user_data?: {
    email: string;
    name?: string;
    nickname?: string;
    user_id: string;
    created_at?: number;
  };
  settings?: Record<string, unknown>;
  message?: string;
}

// ==================== QUERY KEYS ====================

export const supportKeys = {
  all: ["support"] as const,
  tickets: () => [...supportKeys.all, "tickets"] as const,
  ticketList: (filters: { status?: string; category?: string; page?: number }) =>
    [...supportKeys.tickets(), filters] as const,
  ticketDetail: (id: string) => [...supportKeys.tickets(), "detail", id] as const,
  status: () => [...supportKeys.all, "status"] as const,
  taxReport: (year: number) => [...supportKeys.all, "tax", year] as const,
  sat69b: (rfc: string) => [...supportKeys.all, "sat69b", rfc] as const,
  chat: () => [...supportKeys.all, "chat"] as const,
};

// ==================== TICKET HOOKS ====================

export function useTickets(
  filters: { status?: TicketStatus; category?: TicketCategory; page?: number } = {}
) {
  const { status, category, page = 1 } = filters;

  return useQuery({
    queryKey: supportKeys.ticketList({ status, category, page }),
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.append("status", status);
      if (category) params.append("category", category);
      params.append("page", String(page));
      params.append("page_size", "20");

      return apiClient.get<TicketListResponse>(
        `/support/tickets?${params.toString()}`
      );
    },
  });
}

export function useTicket(id: string) {
  return useQuery({
    queryKey: supportKeys.ticketDetail(id),
    queryFn: () => apiClient.get<TicketDetail>(`/support/tickets/${id}`),
    enabled: !!id,
    refetchInterval: 30 * 1000, // Actualizar cada 30 segundos para nuevos mensajes
  });
}

export function useCreateTicket() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TicketCreateInput) =>
      apiClient.post<Ticket>("/support/tickets", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supportKeys.tickets() });
    },
  });
}

export function useAddTicketMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      ticketId,
      data,
    }: {
      ticketId: string;
      data: TicketMessageInput;
    }) =>
      apiClient.post<TicketMessage>(
        `/support/tickets/${ticketId}/messages`,
        data
      ),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: supportKeys.ticketDetail(variables.ticketId),
      });
    },
  });
}

export function useRateTicket() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      ticketId,
      rating,
      feedback,
    }: {
      ticketId: string;
      rating: number;
      feedback?: string;
    }) =>
      apiClient.post<{ message: string; rating: number }>(
        `/support/tickets/${ticketId}/rate`,
        { rating, feedback }
      ),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: supportKeys.ticketDetail(variables.ticketId),
      });
    },
  });
}

export function useCloseTicket() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ticketId: string) =>
      apiClient.post<{ message: string; ticket_number: string }>(
        `/support/tickets/${ticketId}/close`
      ),
    onSuccess: (_, ticketId) => {
      queryClient.invalidateQueries({ queryKey: supportKeys.tickets() });
      queryClient.invalidateQueries({
        queryKey: supportKeys.ticketDetail(ticketId),
      });
    },
  });
}

// ==================== STATUS PAGE HOOKS ====================

export function useStatusPage() {
  return useQuery({
    queryKey: supportKeys.status(),
    queryFn: () => apiClient.get<StatusPage>("/support/status"),
    refetchInterval: 60 * 1000, // Actualizar cada minuto
    staleTime: 30 * 1000,
  });
}

// ==================== TAX CENTER HOOKS ====================

export function useTaxReport(year: number) {
  return useQuery({
    queryKey: supportKeys.taxReport(year),
    queryFn: () => apiClient.get<TaxReport>(`/support/tax-center/${year}`),
    enabled: year >= 2020 && year <= new Date().getFullYear(),
  });
}

export function useDownloadTaxReport() {
  return useMutation({
    mutationFn: (year: number) =>
      apiClient.get<{ message: string; year: number; format: string }>(
        `/support/tax-center/${year}/download`
      ),
  });
}

// ==================== SAT 69-B HOOKS ====================

export function useCheckSAT69B() {
  return useMutation({
    mutationFn: (rfc: string) =>
      apiClient.post<SAT69BCheckResult>("/support/sat-69b/check", { rfc }),
  });
}

// ==================== CHAT HOOKS ====================

export function useChatConfig() {
  return useQuery({
    queryKey: supportKeys.chat(),
    queryFn: () => apiClient.get<ChatConfig>("/support/chat/config"),
    staleTime: 1000 * 60 * 60, // 1 hora
  });
}

// ==================== HELPERS ====================

export const ticketStatusLabels: Record<TicketStatus, string> = {
  open: "Abierto",
  in_progress: "En Progreso",
  waiting_user: "Esperando Respuesta",
  waiting_third_party: "Esperando Tercero",
  resolved: "Resuelto",
  closed: "Cerrado",
};

export const ticketStatusColors: Record<TicketStatus, string> = {
  open: "bg-blue-100 text-blue-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  waiting_user: "bg-orange-100 text-orange-800",
  waiting_third_party: "bg-purple-100 text-purple-800",
  resolved: "bg-green-100 text-green-800",
  closed: "bg-gray-100 text-gray-800",
};

export const ticketCategoryLabels: Record<TicketCategory, string> = {
  general: "General",
  account: "Cuenta",
  trading: "Trading",
  wallet: "Wallet",
  remittance: "Remesas",
  kyc: "KYC/Verificación",
  technical: "Técnico",
  billing: "Facturación",
  security: "Seguridad",
  compliance: "Compliance",
};

export const ticketPriorityLabels: Record<TicketPriority, string> = {
  low: "Baja",
  medium: "Media",
  high: "Alta",
  urgent: "Urgente",
};

export const ticketPriorityColors: Record<TicketPriority, string> = {
  low: "bg-gray-100 text-gray-800",
  medium: "bg-blue-100 text-blue-800",
  high: "bg-orange-100 text-orange-800",
  urgent: "bg-red-100 text-red-800",
};

export const systemStatusLabels: Record<SystemStatus, string> = {
  operational: "Operativo",
  degraded: "Degradado",
  partial_outage: "Interrupción Parcial",
  major_outage: "Interrupción Mayor",
  maintenance: "Mantenimiento",
};

export const systemStatusColors: Record<SystemStatus, string> = {
  operational: "bg-green-500",
  degraded: "bg-yellow-500",
  partial_outage: "bg-orange-500",
  major_outage: "bg-red-500",
  maintenance: "bg-blue-500",
};
