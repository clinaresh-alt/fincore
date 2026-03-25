"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { companiesAPI } from "@/lib/api-client";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/page-header";
import {
  Building2,
  FileText,
  MapPin,
  User,
  Briefcase,
  ArrowLeft,
  ArrowRight,
  Check,
  AlertTriangle,
  Loader2,
} from "lucide-react";

// Tipos de empresa disponibles
const tiposEmpresa = [
  "S.A. de C.V.",
  "S. de R.L. de C.V.",
  "S.A.P.I. de C.V.",
  "S.A.S.",
  "Persona Fisica con Actividad Empresarial",
  "S.C.",
  "A.C.",
  "Otro",
];

const tamanosEmpresa = ["Micro", "Pequena", "Mediana", "Grande"];

const sectores = [
  "Tecnologia",
  "Inmobiliario",
  "Comercio",
  "Servicios",
  "Manufactura",
  "Agricultura",
  "Energia",
  "Construccion",
  "Transporte",
  "Salud",
  "Educacion",
  "Finanzas",
  "Otro",
];

const estadosMexico = [
  "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Chiapas",
  "Chihuahua", "Ciudad de Mexico", "Coahuila", "Colima", "Durango", "Estado de Mexico",
  "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacan", "Morelos", "Nayarit",
  "Nuevo Leon", "Oaxaca", "Puebla", "Queretaro", "Quintana Roo", "San Luis Potosi",
  "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatan", "Zacatecas"
];

interface CompanyFormData {
  // Datos basicos
  razon_social: string;
  nombre_comercial: string;
  tipo_empresa: string;
  rfc: string;
  // Datos fiscales
  regimen_fiscal: string;
  actividad_economica: string;
  // Direccion
  calle: string;
  numero_exterior: string;
  numero_interior: string;
  colonia: string;
  codigo_postal: string;
  municipio: string;
  estado: string;
  // Contacto
  telefono_principal: string;
  email_corporativo: string;
  sitio_web: string;
  // Representante legal
  representante_nombre: string;
  representante_cargo: string;
  representante_email: string;
  representante_telefono: string;
  // Informacion financiera
  tamano_empresa: string;
  numero_empleados: string;
  ingresos_anuales: string;
  sector: string;
  industria: string;
}

const steps = [
  { id: 1, title: "Datos Basicos", icon: Building2 },
  { id: 2, title: "Direccion", icon: MapPin },
  { id: 3, title: "Representante", icon: User },
  { id: 4, title: "Info Financiera", icon: Briefcase },
];

export default function NewCompanyPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<CompanyFormData>({
    razon_social: "",
    nombre_comercial: "",
    tipo_empresa: "S.A. de C.V.",
    rfc: "",
    regimen_fiscal: "",
    actividad_economica: "",
    calle: "",
    numero_exterior: "",
    numero_interior: "",
    colonia: "",
    codigo_postal: "",
    municipio: "",
    estado: "",
    telefono_principal: "",
    email_corporativo: "",
    sitio_web: "",
    representante_nombre: "",
    representante_cargo: "",
    representante_email: "",
    representante_telefono: "",
    tamano_empresa: "",
    numero_empleados: "",
    ingresos_anuales: "",
    sector: "",
    industria: "",
  });

  const updateField = (field: keyof CompanyFormData, value: string) => {
    setFormData({ ...formData, [field]: value });
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return formData.razon_social.length >= 3 && formData.rfc.length >= 12;
      case 2:
        return true; // Direccion es opcional
      case 3:
        return true; // Representante es opcional
      case 4:
        return true; // Financiera es opcional
      default:
        return true;
    }
  };

  const handleNext = () => {
    setCurrentStep(Math.min(currentStep + 1, 4));
  };

  const handleBack = () => {
    setCurrentStep(Math.max(currentStep - 1, 1));
  };

  const handleSubmit = async () => {
    setSaving(true);
    setError(null);

    try {
      // Preparar datos para enviar
      const dataToSend: Record<string, any> = {
        razon_social: formData.razon_social,
        rfc: formData.rfc.toUpperCase(),
        tipo_empresa: formData.tipo_empresa,
      };

      // Agregar campos opcionales si tienen valor
      if (formData.nombre_comercial) dataToSend.nombre_comercial = formData.nombre_comercial;
      if (formData.regimen_fiscal) dataToSend.regimen_fiscal = formData.regimen_fiscal;
      if (formData.actividad_economica) dataToSend.actividad_economica = formData.actividad_economica;
      if (formData.calle) dataToSend.calle = formData.calle;
      if (formData.numero_exterior) dataToSend.numero_exterior = formData.numero_exterior;
      if (formData.numero_interior) dataToSend.numero_interior = formData.numero_interior;
      if (formData.colonia) dataToSend.colonia = formData.colonia;
      if (formData.codigo_postal) dataToSend.codigo_postal = formData.codigo_postal;
      if (formData.municipio) dataToSend.municipio = formData.municipio;
      if (formData.estado) dataToSend.estado = formData.estado;
      if (formData.telefono_principal) dataToSend.telefono_principal = formData.telefono_principal;
      if (formData.email_corporativo) dataToSend.email_corporativo = formData.email_corporativo;
      if (formData.sitio_web) dataToSend.sitio_web = formData.sitio_web;
      if (formData.representante_nombre) dataToSend.representante_nombre = formData.representante_nombre;
      if (formData.representante_cargo) dataToSend.representante_cargo = formData.representante_cargo;
      if (formData.representante_email) dataToSend.representante_email = formData.representante_email;
      if (formData.representante_telefono) dataToSend.representante_telefono = formData.representante_telefono;
      if (formData.tamano_empresa) dataToSend.tamano_empresa = formData.tamano_empresa;
      if (formData.numero_empleados) dataToSend.numero_empleados = parseInt(formData.numero_empleados);
      if (formData.ingresos_anuales) dataToSend.ingresos_anuales = parseFloat(formData.ingresos_anuales);
      if (formData.sector) dataToSend.sector = formData.sector;
      if (formData.industria) dataToSend.industria = formData.industria;

      await companiesAPI.create(dataToSend);
      router.push("/companies");
    } catch (err: any) {
      console.error("Error creating company:", err);
      setError(err.response?.data?.detail || "Error al crear la empresa");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <PageHeader
        title="Nueva Empresa"
        description="Registra una empresa solicitante de proyectos"
        backHref="/companies"
      />

      {/* Progress Steps */}
      <div className="flex items-center justify-between">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center">
            <div
              className={`flex items-center justify-center h-10 w-10 rounded-full border-2 transition-colors ${
                currentStep >= step.id
                  ? "bg-primary border-primary text-white"
                  : "border-slate-300 text-slate-400"
              }`}
            >
              {currentStep > step.id ? (
                <Check className="h-5 w-5" />
              ) : (
                <step.icon className="h-5 w-5" />
              )}
            </div>
            <div className="ml-2 hidden sm:block">
              <p
                className={`text-sm font-medium ${
                  currentStep >= step.id ? "text-primary" : "text-slate-400"
                }`}
              >
                {step.title}
              </p>
            </div>
            {index < steps.length - 1 && (
              <div
                className={`h-0.5 w-12 mx-4 ${
                  currentStep > step.id ? "bg-primary" : "bg-slate-200"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Form Content */}
      <Card>
        <CardContent className="p-6">
          {/* Step 1: Datos Basicos */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div>
                <CardTitle className="text-lg mb-1">Datos Basicos de la Empresa</CardTitle>
                <CardDescription>
                  Informacion legal y fiscal requerida
                </CardDescription>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Razon Social *</label>
                  <Input
                    value={formData.razon_social}
                    onChange={(e) => updateField("razon_social", e.target.value)}
                    placeholder="Ej: Tecnologias Innovadoras S.A. de C.V."
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Nombre Comercial</label>
                  <Input
                    value={formData.nombre_comercial}
                    onChange={(e) => updateField("nombre_comercial", e.target.value)}
                    placeholder="Nombre de marca"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Tipo de Empresa</label>
                  <select
                    value={formData.tipo_empresa}
                    onChange={(e) => updateField("tipo_empresa", e.target.value)}
                    className="mt-1 w-full px-3 py-2 border rounded-md text-sm"
                  >
                    {tiposEmpresa.map((tipo) => (
                      <option key={tipo} value={tipo}>{tipo}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-sm font-medium">RFC *</label>
                  <Input
                    value={formData.rfc}
                    onChange={(e) => updateField("rfc", e.target.value.toUpperCase())}
                    placeholder="ABC123456XYZ"
                    maxLength={13}
                    className="mt-1 uppercase"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    12-13 caracteres alfanumericos
                  </p>
                </div>

                <div>
                  <label className="text-sm font-medium">Regimen Fiscal</label>
                  <Input
                    value={formData.regimen_fiscal}
                    onChange={(e) => updateField("regimen_fiscal", e.target.value)}
                    placeholder="General de Ley Personas Morales"
                    className="mt-1"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Actividad Economica</label>
                  <Input
                    value={formData.actividad_economica}
                    onChange={(e) => updateField("actividad_economica", e.target.value)}
                    placeholder="Desarrollo de software, comercio, etc."
                    className="mt-1"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Direccion */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <CardTitle className="text-lg mb-1">Direccion Fiscal</CardTitle>
                <CardDescription>
                  Domicilio registrado de la empresa
                </CardDescription>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Calle</label>
                  <Input
                    value={formData.calle}
                    onChange={(e) => updateField("calle", e.target.value)}
                    placeholder="Av. Reforma"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Numero Exterior</label>
                  <Input
                    value={formData.numero_exterior}
                    onChange={(e) => updateField("numero_exterior", e.target.value)}
                    placeholder="123"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Numero Interior</label>
                  <Input
                    value={formData.numero_interior}
                    onChange={(e) => updateField("numero_interior", e.target.value)}
                    placeholder="A (opcional)"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Colonia</label>
                  <Input
                    value={formData.colonia}
                    onChange={(e) => updateField("colonia", e.target.value)}
                    placeholder="Centro"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Codigo Postal</label>
                  <Input
                    value={formData.codigo_postal}
                    onChange={(e) => updateField("codigo_postal", e.target.value.replace(/\D/g, "").slice(0, 5))}
                    placeholder="06600"
                    maxLength={5}
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Municipio/Delegacion</label>
                  <Input
                    value={formData.municipio}
                    onChange={(e) => updateField("municipio", e.target.value)}
                    placeholder="Cuauhtemoc"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Estado</label>
                  <select
                    value={formData.estado}
                    onChange={(e) => updateField("estado", e.target.value)}
                    className="mt-1 w-full px-3 py-2 border rounded-md text-sm"
                  >
                    <option value="">Seleccionar...</option>
                    {estadosMexico.map((estado) => (
                      <option key={estado} value={estado}>{estado}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-sm font-medium">Telefono Principal</label>
                  <Input
                    value={formData.telefono_principal}
                    onChange={(e) => updateField("telefono_principal", e.target.value)}
                    placeholder="5555551234"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Email Corporativo</label>
                  <Input
                    type="email"
                    value={formData.email_corporativo}
                    onChange={(e) => updateField("email_corporativo", e.target.value)}
                    placeholder="contacto@empresa.com"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Sitio Web</label>
                  <Input
                    value={formData.sitio_web}
                    onChange={(e) => updateField("sitio_web", e.target.value)}
                    placeholder="https://www.empresa.com"
                    className="mt-1"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Representante Legal */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div>
                <CardTitle className="text-lg mb-1">Representante Legal</CardTitle>
                <CardDescription>
                  Datos de contacto del representante legal
                </CardDescription>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Nombre Completo</label>
                  <Input
                    value={formData.representante_nombre}
                    onChange={(e) => updateField("representante_nombre", e.target.value)}
                    placeholder="Juan Perez Garcia"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Cargo</label>
                  <Input
                    value={formData.representante_cargo}
                    onChange={(e) => updateField("representante_cargo", e.target.value)}
                    placeholder="Director General"
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Telefono</label>
                  <Input
                    value={formData.representante_telefono}
                    onChange={(e) => updateField("representante_telefono", e.target.value)}
                    placeholder="5555554321"
                    className="mt-1"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Email</label>
                  <Input
                    type="email"
                    value={formData.representante_email}
                    onChange={(e) => updateField("representante_email", e.target.value)}
                    placeholder="representante@empresa.com"
                    className="mt-1"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Informacion Financiera */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div>
                <CardTitle className="text-lg mb-1">Informacion Financiera</CardTitle>
                <CardDescription>
                  Datos sobre tamano y sector de la empresa
                </CardDescription>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">Tamano de Empresa</label>
                  <select
                    value={formData.tamano_empresa}
                    onChange={(e) => updateField("tamano_empresa", e.target.value)}
                    className="mt-1 w-full px-3 py-2 border rounded-md text-sm"
                  >
                    <option value="">Seleccionar...</option>
                    {tamanosEmpresa.map((tamano) => (
                      <option key={tamano} value={tamano}>{tamano}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-sm font-medium">Numero de Empleados</label>
                  <Input
                    type="number"
                    value={formData.numero_empleados}
                    onChange={(e) => updateField("numero_empleados", e.target.value)}
                    placeholder="25"
                    min={0}
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Ingresos Anuales (MXN)</label>
                  <Input
                    type="number"
                    value={formData.ingresos_anuales}
                    onChange={(e) => updateField("ingresos_anuales", e.target.value)}
                    placeholder="5000000"
                    min={0}
                    className="mt-1"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Sector</label>
                  <select
                    value={formData.sector}
                    onChange={(e) => updateField("sector", e.target.value)}
                    className="mt-1 w-full px-3 py-2 border rounded-md text-sm"
                  >
                    <option value="">Seleccionar...</option>
                    {sectores.map((sector) => (
                      <option key={sector} value={sector}>{sector}</option>
                    ))}
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Industria/Giro</label>
                  <Input
                    value={formData.industria}
                    onChange={(e) => updateField("industria", e.target.value)}
                    placeholder="Software, Inmobiliario, etc."
                    className="mt-1"
                  />
                </div>
              </div>

              {/* Summary */}
              <div className="mt-6 p-4 rounded-lg bg-slate-50 border">
                <h4 className="font-medium mb-3">Resumen de Registro</h4>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="text-muted-foreground">Razon Social:</div>
                  <div className="font-medium">{formData.razon_social || "-"}</div>
                  <div className="text-muted-foreground">RFC:</div>
                  <div className="font-medium">{formData.rfc || "-"}</div>
                  <div className="text-muted-foreground">Tipo:</div>
                  <div className="font-medium">{formData.tipo_empresa}</div>
                  {formData.sector && (
                    <>
                      <div className="text-muted-foreground">Sector:</div>
                      <div className="font-medium">{formData.sector}</div>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error message */}
      {error && (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-600" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between">
        <Button variant="outline" onClick={handleBack} disabled={currentStep === 1 || saving}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Anterior
        </Button>
        <div className="flex gap-2">
          {currentStep < 4 ? (
            <Button onClick={handleNext} disabled={!canProceed()}>
              Siguiente
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button onClick={handleSubmit} disabled={saving || !canProceed()}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Guardando...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4 mr-2" />
                  Registrar Empresa
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
