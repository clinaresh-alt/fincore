"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Upload,
  Download,
  Eye,
  Trash2,
  CheckCircle2,
  Clock,
  AlertCircle,
} from "lucide-react";
import { formatDate } from "@/lib/utils";

interface Document {
  id: string;
  nombre: string;
  tipo: string;
  tamano: string;
  fecha_subida: string;
  estado: "verificado" | "pendiente" | "rechazado";
}

const mockDocuments: Document[] = [
  {
    id: "1",
    nombre: "Constancia_Situacion_Fiscal.pdf",
    tipo: "Fiscal",
    tamano: "245 KB",
    fecha_subida: "2024-02-10",
    estado: "verificado",
  },
  {
    id: "2",
    nombre: "Identificacion_Oficial.pdf",
    tipo: "Identidad",
    tamano: "1.2 MB",
    fecha_subida: "2024-02-08",
    estado: "verificado",
  },
  {
    id: "3",
    nombre: "Comprobante_Domicilio.pdf",
    tipo: "Domicilio",
    tamano: "890 KB",
    fecha_subida: "2024-02-15",
    estado: "pendiente",
  },
  {
    id: "4",
    nombre: "Estado_Cuenta_Bancario.pdf",
    tipo: "Financiero",
    tamano: "456 KB",
    fecha_subida: "2024-02-01",
    estado: "rechazado",
  },
];

const statusConfig = {
  verificado: { color: "text-green-600 bg-green-100", icon: CheckCircle2, label: "Verificado" },
  pendiente: { color: "text-yellow-600 bg-yellow-100", icon: Clock, label: "Pendiente" },
  rechazado: { color: "text-red-600 bg-red-100", icon: AlertCircle, label: "Rechazado" },
};

export default function DocumentsPage() {
  const [documents] = useState<Document[]>(mockDocuments);

  const verificados = documents.filter((d) => d.estado === "verificado").length;
  const pendientes = documents.filter((d) => d.estado === "pendiente").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Documentos</h1>
          <p className="text-muted-foreground mt-1">
            Gestion de documentos KYC y fiscales
          </p>
        </div>
        <Button>
          <Upload className="mr-2 h-4 w-4" />
          Subir Documento
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle2 className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{verificados}</p>
                <p className="text-sm text-muted-foreground">Verificados</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-yellow-100 flex items-center justify-center">
                <Clock className="h-6 w-6 text-yellow-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{pendientes}</p>
                <p className="text-sm text-muted-foreground">Pendientes</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                <FileText className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{documents.length}</p>
                <p className="text-sm text-muted-foreground">Total</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Documents List */}
      <Card>
        <CardHeader>
          <CardTitle>Mis Documentos</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {documents.map((doc) => {
              const StatusIcon = statusConfig[doc.estado].icon;
              return (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-4 rounded-lg border hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 rounded-lg bg-slate-100 flex items-center justify-center">
                      <FileText className="h-5 w-5 text-slate-600" />
                    </div>
                    <div>
                      <p className="font-medium">{doc.nombre}</p>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>{doc.tipo}</span>
                        <span>-</span>
                        <span>{doc.tamano}</span>
                        <span>-</span>
                        <span>{formatDate(doc.fecha_subida)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <span
                      className={`px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1 ${
                        statusConfig[doc.estado].color
                      }`}
                    >
                      <StatusIcon className="h-3 w-3" />
                      {statusConfig[doc.estado].label}
                    </span>

                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm">
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Upload Area */}
      <Card className="border-dashed">
        <CardContent className="p-8">
          <div className="text-center">
            <Upload className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="font-semibold mb-2">Arrastra archivos aqui</h3>
            <p className="text-sm text-muted-foreground mb-4">
              O haz click para seleccionar archivos
            </p>
            <Button variant="outline">Seleccionar Archivos</Button>
            <p className="text-xs text-muted-foreground mt-2">
              PDF, JPG, PNG hasta 10MB
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
