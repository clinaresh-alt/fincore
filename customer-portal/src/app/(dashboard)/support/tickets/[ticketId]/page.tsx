"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Send,
  Clock,
  User,
  Headphones,
  Star,
  X,
  CheckCircle,
} from "lucide-react";
import {
  useTicket,
  useAddTicketMessage,
  useRateTicket,
  useCloseTicket,
  ticketStatusLabels,
  ticketStatusColors,
  ticketCategoryLabels,
  ticketPriorityLabels,
  ticketPriorityColors,
} from "@/features/support/hooks/use-support";
import { format, formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";

export default function TicketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const ticketId = params.ticketId as string;

  const { data, isLoading } = useTicket(ticketId);
  const addMessageMutation = useAddTicketMessage();
  const rateMutation = useRateTicket();
  const closeMutation = useCloseTicket();

  const [message, setMessage] = useState("");
  const [showRateModal, setShowRateModal] = useState(false);
  const [rating, setRating] = useState(5);
  const [feedback, setFeedback] = useState("");

  const handleSendMessage = async () => {
    if (!message.trim()) return;

    try {
      await addMessageMutation.mutateAsync({
        ticketId,
        data: { message: message.trim() },
      });
      setMessage("");
    } catch (error) {
      console.error("Error sending message:", error);
    }
  };

  const handleRate = async () => {
    try {
      await rateMutation.mutateAsync({
        ticketId,
        rating,
        feedback: feedback || undefined,
      });
      setShowRateModal(false);
    } catch (error) {
      console.error("Error rating ticket:", error);
    }
  };

  const handleClose = async () => {
    try {
      await closeMutation.mutateAsync(ticketId);
      router.push("/support");
    } catch (error) {
      console.error("Error closing ticket:", error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">
          Ticket no encontrado
        </h2>
        <Link href="/support" className="text-purple-600 hover:underline mt-2">
          Volver a soporte
        </Link>
      </div>
    );
  }

  const { ticket, messages } = data;
  const canReply = !["closed", "resolved"].includes(ticket.status);
  const canRate =
    ["closed", "resolved"].includes(ticket.status) && !ticket.satisfaction_rating;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/support"
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Volver a tickets
          </Link>
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
          <h1 className="text-2xl font-bold text-gray-900">{ticket.subject}</h1>
          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              Creado{" "}
              {formatDistanceToNow(new Date(ticket.created_at), {
                addSuffix: true,
                locale: es,
              })}
            </span>
            <span className="px-2 py-0.5 bg-gray-100 rounded">
              {ticketCategoryLabels[ticket.category]}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canRate && (
            <button
              onClick={() => setShowRateModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Star className="w-4 h-4" />
              Calificar
            </button>
          )}
          {canReply && (
            <button
              onClick={handleClose}
              disabled={closeMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <X className="w-4 h-4" />
              Cerrar Ticket
            </button>
          )}
        </div>
      </div>

      {/* Ticket Content */}
      <div className="bg-white rounded-lg border border-gray-200">
        {/* Original Description */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5 text-purple-600" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="font-medium text-gray-900">Tú</span>
                <span className="text-xs text-gray-500">
                  {format(new Date(ticket.created_at), "PPp", { locale: es })}
                </span>
              </div>
              <p className="text-gray-700 whitespace-pre-wrap">
                {ticket.description}
              </p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="divide-y divide-gray-100">
          {messages.map((msg) => (
            <div key={msg.id} className="p-6">
              <div className="flex items-start gap-4">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                    msg.is_from_user
                      ? "bg-purple-100"
                      : "bg-blue-100"
                  }`}
                >
                  {msg.is_from_user ? (
                    <User className="w-5 h-5 text-purple-600" />
                  ) : (
                    <Headphones className="w-5 h-5 text-blue-600" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-medium text-gray-900">
                      {msg.is_from_user ? "Tú" : "Soporte"}
                    </span>
                    <span className="text-xs text-gray-500">
                      {format(new Date(msg.created_at), "PPp", { locale: es })}
                    </span>
                    {msg.read_at && !msg.is_from_user && (
                      <span className="text-xs text-green-600 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" />
                        Leído
                      </span>
                    )}
                  </div>
                  <p className="text-gray-700 whitespace-pre-wrap">
                    {msg.message}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Reply Box */}
        {canReply ? (
          <div className="p-6 border-t border-gray-200 bg-gray-50">
            <div className="flex gap-4">
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Escribe tu respuesta..."
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                rows={3}
              />
              <button
                onClick={handleSendMessage}
                disabled={!message.trim() || addMessageMutation.isPending}
                className="self-end px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                <Send className="w-4 h-4" />
                Enviar
              </button>
            </div>
          </div>
        ) : (
          <div className="p-6 border-t border-gray-200 bg-gray-50 text-center text-gray-500">
            Este ticket está cerrado. No puedes agregar más mensajes.
          </div>
        )}
      </div>

      {/* Rating already submitted */}
      {ticket.satisfaction_rating && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <div className="flex">
              {[1, 2, 3, 4, 5].map((star) => (
                <Star
                  key={star}
                  className={`w-5 h-5 ${
                    star <= ticket.satisfaction_rating!
                      ? "text-yellow-400 fill-yellow-400"
                      : "text-gray-300"
                  }`}
                />
              ))}
            </div>
            <span className="text-green-800">
              Gracias por tu calificación
            </span>
          </div>
        </div>
      )}

      {/* Rate Modal */}
      {showRateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              Califica tu experiencia
            </h2>
            <p className="text-gray-600 mb-6">
              ¿Cómo calificarías la resolución de tu ticket?
            </p>

            <div className="flex justify-center gap-2 mb-6">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setRating(star)}
                  className="p-1"
                >
                  <Star
                    className={`w-8 h-8 transition-colors ${
                      star <= rating
                        ? "text-yellow-400 fill-yellow-400"
                        : "text-gray-300 hover:text-yellow-200"
                    }`}
                  />
                </button>
              ))}
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Comentario (opcional)
              </label>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                rows={3}
                placeholder="¿Algún comentario adicional?"
              />
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowRateModal(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleRate}
                disabled={rateMutation.isPending}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
              >
                {rateMutation.isPending ? "Enviando..." : "Enviar Calificación"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
