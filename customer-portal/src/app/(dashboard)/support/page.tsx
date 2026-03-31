"use client";

import { useState } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Plus,
  Search,
  Clock,
  CheckCircle,
  AlertCircle,
  ChevronRight,
  HelpCircle,
  FileText,
  Activity,
} from "lucide-react";
import {
  useTickets,
  useCreateTicket,
  TicketStatus,
  TicketCategory,
  ticketStatusLabels,
  ticketStatusColors,
  ticketCategoryLabels,
  ticketPriorityLabels,
  ticketPriorityColors,
} from "@/features/support/hooks/use-support";
import { formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";

const quickLinks = [
  {
    title: "Centro de Ayuda",
    description: "Guías y tutoriales",
    href: "/support/help",
    icon: HelpCircle,
  },
  {
    title: "Estado del Sistema",
    description: "Ver status de servicios",
    href: "/support/status",
    icon: Activity,
  },
  {
    title: "Centro de Impuestos",
    description: "Reportes fiscales SAT",
    href: "/settings/tax-center",
    icon: FileText,
  },
];

export default function SupportPage() {
  const [statusFilter, setStatusFilter] = useState<TicketStatus | undefined>();
  const [categoryFilter, setCategoryFilter] = useState<
    TicketCategory | undefined
  >();
  const [page, setPage] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { data: ticketsData, isLoading } = useTickets({
    status: statusFilter,
    category: categoryFilter,
    page,
  });
  const createMutation = useCreateTicket();

  // Form state
  const [formData, setFormData] = useState({
    subject: "",
    description: "",
    category: "general" as TicketCategory,
    priority: "medium" as "low" | "medium" | "high" | "urgent",
  });

  const handleCreate = async () => {
    try {
      await createMutation.mutateAsync(formData);
      setShowCreateModal(false);
      setFormData({
        subject: "",
        description: "",
        category: "general",
        priority: "medium",
      });
    } catch (error) {
      console.error("Error creating ticket:", error);
    }
  };

  const statusOptions: { value: TicketStatus | ""; label: string }[] = [
    { value: "", label: "Todos los estados" },
    { value: "open", label: "Abiertos" },
    { value: "in_progress", label: "En Progreso" },
    { value: "waiting_user", label: "Esperando Respuesta" },
    { value: "resolved", label: "Resueltos" },
    { value: "closed", label: "Cerrados" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Soporte</h1>
          <p className="text-gray-600 mt-1">
            Gestiona tus tickets y obtén ayuda
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Nuevo Ticket
        </button>
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {quickLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="flex items-center gap-4 p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all group"
          >
            <div className="p-3 bg-purple-100 rounded-lg">
              <link.icon className="w-5 h-5 text-purple-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-medium text-gray-900">{link.title}</h3>
              <p className="text-sm text-gray-500">{link.description}</p>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-gray-600" />
          </Link>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <select
          value={statusFilter || ""}
          onChange={(e) =>
            setStatusFilter((e.target.value as TicketStatus) || undefined)
          }
          className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        >
          {statusOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <select
          value={categoryFilter || ""}
          onChange={(e) =>
            setCategoryFilter((e.target.value as TicketCategory) || undefined)
          }
          className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        >
          <option value="">Todas las categorías</option>
          {Object.entries(ticketCategoryLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {/* Tickets List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600" />
          </div>
        ) : ticketsData?.tickets.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
            <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">
              No tienes tickets
            </h3>
            <p className="text-gray-500 mt-2 mb-4">
              Crea un ticket si necesitas ayuda
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Crear Ticket
            </button>
          </div>
        ) : (
          <>
            {ticketsData?.tickets.map((ticket) => (
              <Link
                key={ticket.id}
                href={`/support/tickets/${ticket.id}`}
                className="block bg-white rounded-lg border border-gray-200 p-6 hover:border-gray-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-sm font-mono text-gray-500">
                        {ticket.ticket_number}
                      </span>
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded-full ${ticketStatusColors[ticket.status]}`}
                      >
                        {ticketStatusLabels[ticket.status]}
                      </span>
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded-full ${ticketPriorityColors[ticket.priority]}`}
                      >
                        {ticketPriorityLabels[ticket.priority]}
                      </span>
                    </div>
                    <h3 className="font-semibold text-gray-900">
                      {ticket.subject}
                    </h3>
                    <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                      {ticket.description}
                    </p>
                    <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <Clock className="w-4 h-4" />
                        {formatDistanceToNow(new Date(ticket.created_at), {
                          addSuffix: true,
                          locale: es,
                        })}
                      </span>
                      <span className="px-2 py-0.5 bg-gray-100 rounded text-xs">
                        {ticketCategoryLabels[ticket.category]}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0" />
                </div>
              </Link>
            ))}

            {/* Pagination */}
            {ticketsData && ticketsData.total > ticketsData.page_size && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50"
                >
                  Anterior
                </button>
                <span className="px-4 py-2 text-gray-600">
                  Página {page} de{" "}
                  {Math.ceil(ticketsData.total / ticketsData.page_size)}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={
                    page >=
                    Math.ceil(ticketsData.total / ticketsData.page_size)
                  }
                  className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50"
                >
                  Siguiente
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Create Ticket Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-lg w-full">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">
                Crear Nuevo Ticket
              </h2>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Asunto *
                </label>
                <input
                  type="text"
                  value={formData.subject}
                  onChange={(e) =>
                    setFormData({ ...formData, subject: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  placeholder="Describe brevemente tu problema..."
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Categoría
                  </label>
                  <select
                    value={formData.category}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        category: e.target.value as TicketCategory,
                      })
                    }
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  >
                    {Object.entries(ticketCategoryLabels).map(
                      ([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      )
                    )}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Prioridad
                  </label>
                  <select
                    value={formData.priority}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        priority: e.target.value as
                          | "low"
                          | "medium"
                          | "high"
                          | "urgent",
                      })
                    }
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  >
                    {Object.entries(ticketPriorityLabels).map(
                      ([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      )
                    )}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Descripción *
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  rows={5}
                  placeholder="Describe tu problema en detalle. Incluye cualquier información relevante como fechas, montos, IDs de transacción, etc."
                />
                <p className="text-xs text-gray-500 mt-1">
                  Mínimo 20 caracteres
                </p>
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreate}
                disabled={
                  !formData.subject ||
                  formData.description.length < 20 ||
                  createMutation.isPending
                }
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? "Creando..." : "Crear Ticket"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
