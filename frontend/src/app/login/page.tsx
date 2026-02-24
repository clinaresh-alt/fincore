"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, Lock, Mail } from "lucide-react";

const loginSchema = z.object({
  email: z.string().email("Email invalido"),
  password: z.string().min(8, "Minimo 8 caracteres"),
});

const mfaSchema = z.object({
  code: z.string().length(6, "El codigo debe tener 6 digitos"),
});

type LoginForm = z.infer<typeof loginSchema>;
type MFAForm = z.infer<typeof mfaSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { login, verifyMFA, mfaPending, isLoading } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

  const loginForm = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const mfaForm = useForm<MFAForm>({
    resolver: zodResolver(mfaSchema),
    defaultValues: { code: "" },
  });

  const onLogin = async (data: LoginForm) => {
    setError(null);
    try {
      const success = await login(data.email, data.password);
      if (success) {
        router.push("/dashboard");
      }
      // Si no es success, significa que se requiere MFA
    } catch (err: any) {
      setError(err.response?.data?.detail || "Error al iniciar sesion");
    }
  };

  const onVerifyMFA = async (data: MFAForm) => {
    setError(null);
    try {
      const success = await verifyMFA(data.code);
      if (success) {
        router.push("/dashboard");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Codigo MFA incorrecto");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex h-16 w-16 rounded-2xl bg-primary items-center justify-center mb-4">
            <span className="text-3xl font-bold text-white">F</span>
          </div>
          <h1 className="text-3xl font-bold text-white">FinCore</h1>
          <p className="text-slate-400 mt-2">Sistema Financiero de Alto Nivel</p>
        </div>

        <Card className="border-slate-700 bg-slate-800/50 backdrop-blur">
          <CardHeader className="text-center">
            <CardTitle className="text-white">
              {mfaPending ? "Verificacion MFA" : "Iniciar Sesion"}
            </CardTitle>
            <CardDescription className="text-slate-400">
              {mfaPending
                ? "Ingresa el codigo de tu app de autenticacion"
                : "Ingresa tus credenciales para continuar"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            {!mfaPending ? (
              // Login Form
              <form onSubmit={loginForm.handleSubmit(onLogin)} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-200">
                    Email
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      {...loginForm.register("email")}
                      type="email"
                      placeholder="tu@email.com"
                      className="pl-10 bg-slate-900/50 border-slate-600 text-white placeholder:text-slate-500"
                      error={loginForm.formState.errors.email?.message}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-200">
                    Contrasena
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      {...loginForm.register("password")}
                      type="password"
                      placeholder="********"
                      className="pl-10 bg-slate-900/50 border-slate-600 text-white placeholder:text-slate-500"
                      error={loginForm.formState.errors.password?.message}
                    />
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  loading={isLoading}
                >
                  Iniciar Sesion
                </Button>
              </form>
            ) : (
              // MFA Form
              <form onSubmit={mfaForm.handleSubmit(onVerifyMFA)} className="space-y-4">
                <div className="flex justify-center mb-4">
                  <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
                    <Shield className="h-8 w-8 text-primary" />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-200 text-center block">
                    Codigo de 6 digitos
                  </label>
                  <Input
                    {...mfaForm.register("code")}
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    placeholder="000000"
                    className="text-center text-2xl tracking-widest bg-slate-900/50 border-slate-600 text-white"
                    error={mfaForm.formState.errors.code?.message}
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  loading={isLoading}
                >
                  Verificar
                </Button>

                <Button
                  type="button"
                  variant="ghost"
                  className="w-full text-slate-400"
                  onClick={() => window.location.reload()}
                >
                  Cancelar
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        <p className="text-center text-slate-500 text-sm mt-6">
          No tienes cuenta?{" "}
          <a href="/register" className="text-primary hover:underline">
            Registrate
          </a>
        </p>
      </div>
    </div>
  );
}
