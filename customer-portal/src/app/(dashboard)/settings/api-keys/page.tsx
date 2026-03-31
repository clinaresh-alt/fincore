"use client";

import { useState } from "react";
import {
  KeyRound,
  Plus,
  Copy,
  Trash2,
  Eye,
  EyeOff,
  AlertTriangle,
  Check,
  BarChart3,
  Clock,
  Globe,
  Shield,
} from "lucide-react";
import {
  useAPIKeys,
  useCreateAPIKey,
  useRevokeAPIKey,
  useAvailablePermissions,
  APIKey,
  APIKeyCreated,
  APIKeyCreateInput,
} from "@/features/api-keys/hooks/use-api-keys";
import { formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";

export default function APIKeysPage() {
  const { data: apiKeys, isLoading } = useAPIKeys();
  const { data: permissionsData } = useAvailablePermissions();
  const createMutation = useCreateAPIKey();
  const revokeMutation = useRevokeAPIKey();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showNewKey, setShowNewKey] = useState<APIKeyCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokeConfirm, setRevokeConfirm] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<APIKeyCreateInput>({
    name: "",
    description: "",
    permissions: ["read:portfolio", "read:balances"],
    allowed_ips: [],
    rate_limit_per_minute: 60,
    rate_limit_per_day: 10000,
  });
  const [ipInput, setIpInput] = useState("");

  const handleCreate = async () => {
    try {
      const result = await createMutation.mutateAsync(formData);
      setShowNewKey(result);
      setShowCreateModal(false);
      setFormData({
        name: "",
        description: "",
        permissions: ["read:portfolio", "read:balances"],
        allowed_ips: [],
        rate_limit_per_minute: 60,
        rate_limit_per_day: 10000,
      });
    } catch (error) {
      console.error("Error creating API key:", error);
    }
  };

  const handleRevoke = async (id: string) => {
    try {
      await revokeMutation.mutateAsync(id);
      setRevokeConfirm(null);
    } catch (error) {
      console.error("Error revoking API key:", error);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const togglePermission = (code: string) => {
    setFormData((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(code)
        ? prev.permissions.filter((p) => p !== code)
        : [...prev.permissions, code],
    }));
  };

  const addIP = () => {
    if (ipInput && !formData.allowed_ips?.includes(ipInput)) {
      setFormData((prev) => ({
        ...prev,
        allowed_ips: [...(prev.allowed_ips || []), ipInput],
      }));
      setIpInput("");
    }
  };

  const removeIP = (ip: string) => {
    setFormData((prev) => ({
      ...prev,
      allowed_ips: prev.allowed_ips?.filter((i) => i !== ip),
    }));
  };

  const permissionsByCategory =
    permissionsData?.permissions.reduce(
      (acc, perm) => {
        if (!acc[perm.category]) acc[perm.category] = [];
        acc[perm.category].push(perm);
        return acc;
      },
      {} as Record<string, typeof permissionsData.permissions>
    ) || {};

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
          <p className="text-gray-600 mt-1">
            Gestiona el acceso programático a tu cuenta
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Nueva API Key
        </button>
      </div>

      {/* Warning */}
      <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-amber-800">
            Mantén tus API Keys seguras
          </p>
          <p className="text-sm text-amber-700 mt-1">
            No compartas tus API Keys. Usa IPs permitidas para mayor seguridad.
            Las keys con permiso de retiro pueden mover fondos.
          </p>
        </div>
      </div>

      {/* API Keys List */}
      <div className="space-y-4">
        {apiKeys?.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
            <KeyRound className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">
              No tienes API Keys
            </h3>
            <p className="text-gray-500 mt-2">
              Crea una para acceder a la API de forma programática
            </p>
          </div>
        ) : (
          apiKeys?.map((key: APIKey) => (
            <div
              key={key.id}
              className="bg-white rounded-lg border border-gray-200 p-6"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-gray-900">{key.name}</h3>
                    <span
                      className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                        key.status === "active"
                          ? "bg-green-100 text-green-800"
                          : key.status === "revoked"
                            ? "bg-red-100 text-red-800"
                            : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {key.status === "active"
                        ? "Activa"
                        : key.status === "revoked"
                          ? "Revocada"
                          : "Expirada"}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">
                    {key.description || "Sin descripción"}
                  </p>
                  <div className="flex items-center gap-4 mt-3 text-sm text-gray-600">
                    <span className="font-mono bg-gray-100 px-2 py-1 rounded">
                      {key.key_prefix}...
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-4 h-4" />
                      {key.last_used_at
                        ? `Usado ${formatDistanceToNow(new Date(key.last_used_at), { addSuffix: true, locale: es })}`
                        : "Nunca usado"}
                    </span>
                    <span className="flex items-center gap-1">
                      <BarChart3 className="w-4 h-4" />
                      {key.total_requests.toLocaleString()} requests
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-3">
                    {key.permissions.map((perm) => (
                      <span
                        key={perm}
                        className="px-2 py-0.5 text-xs bg-purple-100 text-purple-700 rounded"
                      >
                        {perm}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={`/settings/api-keys/${key.id}`}
                    className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                    title="Ver estadísticas"
                  >
                    <BarChart3 className="w-5 h-5" />
                  </a>
                  {key.status === "active" && (
                    <button
                      onClick={() => setRevokeConfirm(key.id)}
                      className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                      title="Revocar"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">
                Crear Nueva API Key
              </h2>
            </div>
            <div className="p-6 space-y-6">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Nombre *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  placeholder="Mi API Key de Trading"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Descripción
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  rows={2}
                  placeholder="Descripción opcional..."
                />
              </div>

              {/* Permissions */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Permisos
                </label>
                <div className="space-y-4">
                  {Object.entries(permissionsByCategory).map(
                    ([category, perms]) => (
                      <div key={category}>
                        <h4 className="text-sm font-medium text-gray-600 mb-2">
                          {category}
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {perms.map((perm) => (
                            <button
                              key={perm.code}
                              onClick={() => togglePermission(perm.code)}
                              className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                                formData.permissions.includes(perm.code)
                                  ? "bg-purple-100 border-purple-300 text-purple-800"
                                  : "bg-white border-gray-300 text-gray-600 hover:bg-gray-50"
                              }`}
                            >
                              {perm.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )
                  )}
                </div>
              </div>

              {/* Allowed IPs */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4" />
                    IPs Permitidas (opcional)
                  </div>
                </label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={ipInput}
                    onChange={(e) => setIpInput(e.target.value)}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    placeholder="192.168.1.1"
                  />
                  <button
                    onClick={addIP}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                  >
                    Agregar
                  </button>
                </div>
                {formData.allowed_ips && formData.allowed_ips.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {formData.allowed_ips.map((ip) => (
                      <span
                        key={ip}
                        className="flex items-center gap-1 px-2 py-1 bg-gray-100 rounded text-sm"
                      >
                        {ip}
                        <button
                          onClick={() => removeIP(ip)}
                          className="text-gray-400 hover:text-red-600"
                        >
                          &times;
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                <p className="text-xs text-gray-500 mt-1">
                  Dejar vacío para permitir cualquier IP
                </p>
              </div>

              {/* Rate Limits */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Límite por minuto
                  </label>
                  <input
                    type="number"
                    value={formData.rate_limit_per_minute}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        rate_limit_per_minute: parseInt(e.target.value) || 60,
                      })
                    }
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    min={1}
                    max={1000}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Límite por día
                  </label>
                  <input
                    type="number"
                    value={formData.rate_limit_per_day}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        rate_limit_per_day: parseInt(e.target.value) || 10000,
                      })
                    }
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    min={100}
                    max={100000}
                  />
                </div>
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
                disabled={!formData.name || createMutation.isPending}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? "Creando..." : "Crear API Key"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Show New Key Modal */}
      {showNewKey && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-lg w-full">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-full">
                  <Check className="w-6 h-6 text-green-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    API Key Creada
                  </h2>
                  <p className="text-sm text-gray-500">{showNewKey.name}</p>
                </div>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-amber-800">
                  Esta es la <strong>única vez</strong> que verás la API Key
                  completa. Guárdala en un lugar seguro.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Tu API Key
                </label>
                <div className="flex items-center gap-2 p-3 bg-gray-100 rounded-lg font-mono text-sm">
                  <span className="flex-1 break-all">{showNewKey.key}</span>
                  <button
                    onClick={() => copyToClipboard(showNewKey.key)}
                    className="p-2 text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    {copied ? (
                      <Check className="w-5 h-5 text-green-600" />
                    ) : (
                      <Copy className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>
            </div>
            <div className="p-6 border-t border-gray-200">
              <button
                onClick={() => setShowNewKey(null)}
                className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
              >
                Entendido, la guardé
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Revoke Confirmation Modal */}
      {revokeConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 rounded-full">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <h2 className="text-xl font-bold text-gray-900">
                Revocar API Key
              </h2>
            </div>
            <p className="text-gray-600 mb-6">
              Esta acción es irreversible. Las aplicaciones que usen esta API
              Key dejarán de funcionar inmediatamente.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setRevokeConfirm(null)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleRevoke(revokeConfirm)}
                disabled={revokeMutation.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {revokeMutation.isPending ? "Revocando..." : "Revocar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
