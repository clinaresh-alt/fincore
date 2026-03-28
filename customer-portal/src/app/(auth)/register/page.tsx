"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Mail, Lock, Check } from "lucide-react";
import { toast } from "sonner";
import { signIn } from "next-auth/react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const registerSchema = z
  .object({
    email: z
      .string()
      .min(1, "El email es requerido")
      .email("Ingresa un email válido"),
    password: z
      .string()
      .min(8, "La contraseña debe tener al menos 8 caracteres")
      .regex(/[A-Z]/, "Debe contener al menos una mayúscula")
      .regex(/[a-z]/, "Debe contener al menos una minúscula")
      .regex(/[0-9]/, "Debe contener al menos un número"),
    confirm_password: z.string().min(1, "Confirma tu contraseña"),
    accept_terms: z.boolean().refine((val) => val === true, {
      message: "Debes aceptar los términos y condiciones",
    }),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Las contraseñas no coinciden",
    path: ["confirm_password"],
  });

type RegisterForm = z.infer<typeof registerSchema>;

const passwordRequirements = [
  { regex: /.{8,}/, label: "Al menos 8 caracteres" },
  { regex: /[A-Z]/, label: "Una letra mayúscula" },
  { regex: /[a-z]/, label: "Una letra minúscula" },
  { regex: /[0-9]/, label: "Un número" },
];

export default function RegisterPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: "",
      password: "",
      confirm_password: "",
      accept_terms: false,
    },
  });

  const password = watch("password");

  const onSubmit = async (data: RegisterForm) => {
    setIsLoading(true);
    try {
      // Registrar usuario en el backend
      const response = await fetch(`${API_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: data.email,
          password: data.password,
          rol: "Cliente",
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || "Error al crear la cuenta");
      }

      toast.success("Cuenta creada exitosamente");

      // Auto-login después del registro
      const signInResult = await signIn("credentials", {
        email: data.email,
        password: data.password,
        redirect: false,
      });

      if (signInResult?.ok) {
        router.push("/");
        router.refresh();
      } else {
        // Si falla el auto-login, redirigir a login
        router.push("/login?registered=true");
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Error al crear la cuenta";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="border-0 shadow-lg">
      <CardHeader className="space-y-1 text-center">
        <CardTitle className="text-2xl font-bold">Crear cuenta</CardTitle>
        <CardDescription>
          Regístrate para enviar remesas de forma segura
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Registration Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="tu@email.com"
              autoComplete="email"
              leftIcon={<Mail className="h-4 w-4" />}
              error={!!errors.email}
              {...register("email")}
            />
            {errors.email && (
              <p className="text-sm text-destructive">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Contraseña</Label>
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              autoComplete="new-password"
              leftIcon={<Lock className="h-4 w-4" />}
              rightIcon={
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="hover:text-foreground"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              }
              error={!!errors.password}
              {...register("password")}
            />
            {/* Password requirements */}
            <div className="grid grid-cols-2 gap-1 mt-2">
              {passwordRequirements.map((req) => (
                <div
                  key={req.label}
                  className={`flex items-center gap-1.5 text-xs ${
                    req.regex.test(password || "")
                      ? "text-green-600"
                      : "text-muted-foreground"
                  }`}
                >
                  <Check
                    className={`h-3 w-3 ${
                      req.regex.test(password || "") ? "opacity-100" : "opacity-30"
                    }`}
                  />
                  {req.label}
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm_password">Confirmar contraseña</Label>
            <Input
              id="confirm_password"
              type="password"
              placeholder="••••••••"
              autoComplete="new-password"
              leftIcon={<Lock className="h-4 w-4" />}
              error={!!errors.confirm_password}
              {...register("confirm_password")}
            />
            {errors.confirm_password && (
              <p className="text-sm text-destructive">
                {errors.confirm_password.message}
              </p>
            )}
          </div>

          <div className="flex items-start gap-2">
            <input
              type="checkbox"
              id="accept_terms"
              className="mt-1 h-4 w-4 rounded border-input"
              {...register("accept_terms")}
            />
            <Label htmlFor="accept_terms" className="text-sm font-normal">
              Acepto los{" "}
              <Link href="/terms" className="text-primary hover:underline">
                Términos de Servicio
              </Link>{" "}
              y la{" "}
              <Link href="/privacy" className="text-primary hover:underline">
                Política de Privacidad
              </Link>
            </Label>
          </div>
          {errors.accept_terms && (
            <p className="text-sm text-destructive">
              {errors.accept_terms.message}
            </p>
          )}

          <Button type="submit" className="w-full h-11" isLoading={isLoading}>
            Crear cuenta
          </Button>
        </form>
      </CardContent>

      <CardFooter className="flex flex-col space-y-4">
        <p className="text-sm text-center text-muted-foreground">
          ¿Ya tienes una cuenta?{" "}
          <Link href="/login" className="text-primary font-medium hover:underline">
            Inicia sesión
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
