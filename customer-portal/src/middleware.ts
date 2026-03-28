import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Rutas públicas (no requieren autenticación)
const publicRoutes = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
];

// Rutas que requieren KYC completado (TODO: implementar verificación)
export const kycRequiredRoutes = [
  "/remittances/new",
  "/wallet/buy",
];

// Rutas de API que no necesitan middleware
const apiRoutes = ["/api/"];

/**
 * Middleware de seguridad para el Customer Portal
 *
 * Funciones:
 * 1. Protección de rutas autenticadas
 * 2. Content Security Policy (CSP)
 * 3. Headers de seguridad adicionales
 * 4. Verificación de KYC para operaciones sensibles
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Ignorar rutas de API y archivos estáticos
  if (
    apiRoutes.some((route) => pathname.startsWith(route)) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/static") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  // Obtener token de sesión de la cookie
  const sessionToken = request.cookies.get("next-auth.session-token")?.value ||
    request.cookies.get("__Secure-next-auth.session-token")?.value;

  const isAuthenticated = !!sessionToken;
  const isPublicRoute = publicRoutes.some((route) => pathname.startsWith(route));

  // Redirigir usuarios no autenticados a login (incluyendo la homepage)
  if (!isAuthenticated && !isPublicRoute) {
    const loginUrl = new URL("/login", request.url);
    // Solo agregar callbackUrl si no es la homepage (para evitar redirigir a / después de login)
    if (pathname !== "/") {
      loginUrl.searchParams.set("callbackUrl", pathname);
    }
    return NextResponse.redirect(loginUrl);
  }

  // Redirigir usuarios autenticados lejos de páginas de auth
  if (isAuthenticated && isPublicRoute) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // Crear respuesta con headers de seguridad
  const response = NextResponse.next();

  // Content Security Policy
  const cspDirectives = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://challenges.cloudflare.com",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    "connect-src 'self' https://api.fincore.com wss://api.fincore.com https://polygon-rpc.com https://rpc.ankr.com https://cloudflare-eth.com",
    "frame-src 'self' https://challenges.cloudflare.com https://verify.walletconnect.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
  ];

  // En desarrollo, permitir localhost
  if (process.env.NODE_ENV === "development") {
    cspDirectives[1] = "script-src 'self' 'unsafe-eval' 'unsafe-inline'";
    cspDirectives[4] = "connect-src 'self' http://localhost:* ws://localhost:* https: wss:";
  }

  response.headers.set("Content-Security-Policy", cspDirectives.join("; "));

  // Headers de seguridad adicionales
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-XSS-Protection", "1; mode=block");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set(
    "Permissions-Policy",
    "camera=(), microphone=(), geolocation=(self), payment=(self), usb=()"
  );

  // HSTS solo en producción
  if (process.env.NODE_ENV === "production") {
    response.headers.set(
      "Strict-Transport-Security",
      "max-age=31536000; includeSubDomains; preload"
    );
  }

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\..*|api/).*)",
  ],
};
