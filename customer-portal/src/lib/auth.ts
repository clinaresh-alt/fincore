import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";
import type { Provider } from "next-auth/providers";
import type { User } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Verificar si Google OAuth está configurado
const GOOGLE_CONFIGURED = !!(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);

/**
 * Configuración de NextAuth.js v5 (Auth.js)
 *
 * Integración con el backend de FinCore:
 * - Credenciales (email/password) → POST /api/v1/auth/login
 * - OAuth (Google/Apple) → Registro automático si no existe
 * - JWT almacenado en cookies HttpOnly
 */
export const { handlers, signIn, signOut, auth } = NextAuth({
  pages: {
    signIn: "/login",
    signOut: "/login",
    error: "/login",
    newUser: "/setup-2fa",
  },

  providers: [
    // Autenticación con credenciales (email/password)
    Credentials({
      id: "credentials",
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Email y contraseña son requeridos");
        }

        try {
          // El backend usa OAuth2PasswordRequestForm que espera form-data
          const formData = new URLSearchParams();
          formData.append("username", credentials.email as string);
          formData.append("password", credentials.password as string);

          const response = await fetch(`${API_URL}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: formData.toString(),
          });

          const data = await response.json();

          if (!response.ok) {
            throw new Error(data.detail || "Credenciales inválidas");
          }

          // Si requiere MFA, devolver token temporal
          if (data.mfa_required) {
            return {
              id: "mfa_pending",
              email: credentials.email as string,
              mfaPendingToken: data.mfa_token,
              requiresMfa: true,
            };
          }

          // Login exitoso - obtener info del usuario
          const userResponse = await fetch(`${API_URL}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${data.access_token}` },
          });

          let user = null;
          if (userResponse.ok) {
            user = await userResponse.json();
          }

          return {
            id: user?.id || "unknown",
            email: user?.email || credentials.email as string,
            name: user ? `${user.nombre || ""} ${user.apellido || ""}`.trim() : null,
            image: user?.avatar_url,
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            user,
          };
        } catch (error) {
          console.error("Auth error:", error);
          throw error;
        }
      },
    }),

    // OAuth con Google (solo si está configurado)
    ...(GOOGLE_CONFIGURED
      ? [
          Google({
            clientId: process.env.GOOGLE_CLIENT_ID!,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
            authorization: {
              params: {
                prompt: "consent",
                access_type: "offline",
                response_type: "code",
              },
            },
          }),
        ]
      : []),
  ] as Provider[],

  callbacks: {
    // Callback cuando se crea el JWT
    async jwt({ token, user, account }) {
      // Primera vez que inicia sesión
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.name = user.name;
        token.accessToken = (user as { accessToken?: string }).accessToken;
        token.refreshToken = (user as { refreshToken?: string }).refreshToken;
        token.user = (user as { user?: User }).user;
        token.requiresMfa = (user as { requiresMfa?: boolean }).requiresMfa;
        token.mfaPendingToken = (user as { mfaPendingToken?: string }).mfaPendingToken;
        // Guardar tiempo de expiración (15 minutos desde ahora)
        token.accessTokenExpires = Date.now() + 15 * 60 * 1000;
      }

      // Si es login OAuth, registrar/vincular con backend
      if (account?.provider === "google" && account.access_token) {
        try {
          const response = await fetch(`${API_URL}/api/v1/auth/oauth/google`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              access_token: account.access_token,
              id_token: account.id_token,
            }),
          });

          if (response.ok) {
            const data = await response.json();
            token.accessToken = data.access_token;
            token.refreshToken = data.refresh_token;
            token.user = data.user;
            token.accessTokenExpires = Date.now() + 15 * 60 * 1000;
          }
        } catch (error) {
          console.error("OAuth backend sync error:", error);
        }
      }

      // Verificar si el token está por expirar (menos de 2 minutos)
      const tokenExpires = token.accessTokenExpires as number;
      if (tokenExpires && Date.now() > tokenExpires - 2 * 60 * 1000) {
        // Intentar refrescar el token
        if (token.refreshToken) {
          try {
            const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ refresh_token: token.refreshToken }),
            });

            if (response.ok) {
              const data = await response.json();
              token.accessToken = data.access_token;
              token.refreshToken = data.refresh_token || token.refreshToken;
              token.accessTokenExpires = Date.now() + 15 * 60 * 1000;
              console.log("[Auth] Token refreshed successfully");
            } else {
              // Refresh falló - forzar re-login
              console.warn("[Auth] Token refresh failed, session expired");
              token.error = "RefreshAccessTokenError";
            }
          } catch (error) {
            console.error("[Auth] Token refresh error:", error);
            token.error = "RefreshAccessTokenError";
          }
        }
      }

      return token;
    },

    // Callback cuando se crea la sesión
    async session({ session, token }) {
      if (token) {
        session.user.id = token.id as string;
        session.accessToken = token.accessToken as string;
        session.user.role = (token.user as User)?.role;
        session.user.kycStatus = (token.user as User)?.kyc_status;
        session.user.kycLevel = (token.user as User)?.kyc_level;
        session.user.mfaEnabled = (token.user as User)?.mfa_enabled;

        // Info de MFA pendiente
        if (token.requiresMfa) {
          session.requiresMfa = true;
          session.mfaPendingToken = token.mfaPendingToken as string;
        }
      }
      return session;
    },

    // Callback para permitir sign-in
    async signIn({ user, account }) {
      // Si requiere MFA, permitir pero marcar como pendiente
      if ((user as { requiresMfa?: boolean }).requiresMfa) {
        return true;
      }

      // OAuth siempre permitido
      if (account?.provider !== "credentials") {
        return true;
      }

      // Credenciales válidas
      return !!user;
    },

    // Redirect después de login
    async redirect({ url, baseUrl }) {
      // Si tiene MFA pendiente, redirigir a verificación
      if (url.includes("mfa_pending")) {
        return `${baseUrl}/setup-2fa/verify`;
      }

      // Redirigir a la URL solicitada o al dashboard
      if (url.startsWith("/")) {
        return `${baseUrl}${url}`;
      }
      if (url.startsWith(baseUrl)) {
        return url;
      }
      return baseUrl;
    },
  },

  session: {
    strategy: "jwt",
    maxAge: 30 * 60, // 30 minutos (igual que el backend)
  },

  cookies: {
    sessionToken: {
      name: `next-auth.session-token`,
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
      },
    },
  },

  debug: process.env.NODE_ENV === "development",
});

// Tipos extendidos para la sesión
declare module "next-auth" {
  interface Session {
    accessToken?: string;
    requiresMfa?: boolean;
    mfaPendingToken?: string;
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role?: string;
      kycStatus?: string;
      kycLevel?: number;
      mfaEnabled?: boolean;
    };
  }
}
