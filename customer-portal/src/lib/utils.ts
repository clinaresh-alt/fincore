import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Combina clases de Tailwind de forma segura
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Formatea un número como moneda
 */
export function formatCurrency(
  amount: number,
  currency: string = "USD",
  locale: string = "es-MX"
): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Formatea un número con separadores de miles
 */
export function formatNumber(
  value: number,
  decimals: number = 2,
  locale: string = "es-MX"
): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Formatea una fecha relativa (hace 2 horas, ayer, etc.)
 */
export function formatRelativeTime(date: Date | string, locale: string = "es-MX"): string {
  const now = new Date();
  const target = typeof date === "string" ? new Date(date) : date;
  const diffInSeconds = Math.floor((now.getTime() - target.getTime()) / 1000);

  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  if (diffInSeconds < 60) {
    return rtf.format(-diffInSeconds, "second");
  } else if (diffInSeconds < 3600) {
    return rtf.format(-Math.floor(diffInSeconds / 60), "minute");
  } else if (diffInSeconds < 86400) {
    return rtf.format(-Math.floor(diffInSeconds / 3600), "hour");
  } else if (diffInSeconds < 604800) {
    return rtf.format(-Math.floor(diffInSeconds / 86400), "day");
  } else {
    return target.toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }
}

/**
 * Formatea una fecha completa
 */
export function formatDate(
  date: Date | string,
  options: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  },
  locale: string = "es-MX"
): string {
  const target = typeof date === "string" ? new Date(date) : date;
  return target.toLocaleDateString(locale, options);
}

/**
 * Trunca un hash de transacción blockchain
 */
export function truncateHash(hash: string, startChars: number = 6, endChars: number = 4): string {
  if (hash.length <= startChars + endChars) {
    return hash;
  }
  return `${hash.slice(0, startChars)}...${hash.slice(-endChars)}`;
}

/**
 * Trunca una dirección de wallet
 */
export function truncateAddress(address: string): string {
  return truncateHash(address, 6, 4);
}

/**
 * Valida un CLABE mexicano (18 dígitos)
 */
export function isValidCLABE(clabe: string): boolean {
  if (!/^\d{18}$/.test(clabe)) {
    return false;
  }

  // Algoritmo de validación del dígito verificador
  const weights = [3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7, 1, 3, 7];
  let sum = 0;

  for (let i = 0; i < 17; i++) {
    const digit = parseInt(clabe[i]!, 10);
    const product = digit * weights[i]!;
    sum += product % 10;
  }

  const checkDigit = (10 - (sum % 10)) % 10;
  return checkDigit === parseInt(clabe[17]!, 10);
}

/**
 * Obtiene el nombre del banco desde un CLABE
 */
export function getBankFromCLABE(clabe: string): string | null {
  const bankCodes: Record<string, string> = {
    "002": "Banamex",
    "012": "BBVA México",
    "014": "Santander",
    "021": "HSBC",
    "030": "Bajío",
    "036": "Inbursa",
    "042": "Mifel",
    "044": "Scotiabank",
    "058": "Banregio",
    "059": "Invex",
    "062": "Afirme",
    "072": "Banorte",
    "106": "Bank of America",
    "108": "Mufg",
    "112": "Bmonex",
    "113": "Ve por Más",
    "127": "Azteca",
    "128": "Autofin",
    "129": "Barclays",
    "130": "Compartamos",
    "131": "Banco Famsa",
    "132": "Multiva",
    "133": "Actinver",
    "134": "Intercam",
    "135": "Nafin",
    "136": "Monex",
    "137": "Bancoppel",
    "138": "ABC Capital",
    "140": "Consubanco",
    "141": "Volkswagen",
    "143": "Cibanco",
    "145": "Bbase",
    "147": "Bankaool",
    "148": "Pagatodo",
    "150": "INMOBILIARIO",
    "156": "Sabadell",
    "166": "Bansefi",
    "168": "Hipotecaria",
    "600": "Monexcb",
    "601": "GBM",
    "602": "Masari",
    "605": "Value",
    "606": "Estructuradores",
    "607": "Tiber",
    "608": "Vector",
    "610": "B&B",
    "614": "Accival",
    "615": "Merrill Lynch",
    "616": "Finamex",
    "617": "Valmex",
    "618": "Unica",
    "619": "Mapfre",
    "620": "Profuturo",
    "621": "CB Actinver",
    "622": "Oactin",
    "623": "Skandia",
    "626": "Cbdeutsche",
    "627": "Zurich",
    "628": "Zurichvi",
    "629": "Su Casita",
    "630": "CB Intercam",
    "631": "CI Bolsa",
    "632": "Bulltick CB",
    "633": "Sterling",
    "634": "Fincomun",
    "636": "HDI Seguros",
    "637": "Order",
    "638": "Akala",
    "640": "CB JP Morgan",
    "642": "Reforma",
    "646": "STP",
    "647": "Telecomm",
    "648": "Evercore",
    "649": "Skandia",
    "651": "Segmty",
    "652": "Asea",
    "653": "Kuspit",
    "655": "UNAGRA",
    "656": "SOFIEXPRESS",
    "659": "ASP Integra",
    "670": "Libertad",
    "677": "CAJA POP MEXICA",
    "679": "FND",
    "680": "Cristóbal Colón",
    "683": "Caja Telefonist",
    "684": "Transfer",
    "685": "Fondo (FIRA)",
    "686": "INVERCAP",
    "689": "FOMPED",
    "722": "Mercado Pago",
    "901": "CLS",
    "902": "INDEVAL",
    "999": "N/A",
  };

  const code = clabe.slice(0, 3);
  return bankCodes[code] ?? null;
}

/**
 * Genera un ID único
 */
export function generateId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 11)}`;
}

/**
 * Debounce para funciones
 */
export function debounce<T extends (...args: Parameters<T>) => ReturnType<T>>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

/**
 * Espera un tiempo determinado
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Copia texto al portapapeles
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback para navegadores antiguos
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand("copy");
      return true;
    } catch {
      return false;
    } finally {
      document.body.removeChild(textArea);
    }
  }
}

/**
 * Sanitiza HTML para prevenir XSS
 */
export function sanitizeHtml(html: string): string {
  // Importar DOMPurify dinámicamente en el cliente
  if (typeof window !== "undefined") {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const DOMPurify = require("dompurify");
    return DOMPurify.sanitize(html, {
      ALLOWED_TAGS: ["b", "i", "em", "strong", "a", "br"],
      ALLOWED_ATTR: ["href", "target", "rel"],
    });
  }
  // En servidor, escapar caracteres peligrosos
  return html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
