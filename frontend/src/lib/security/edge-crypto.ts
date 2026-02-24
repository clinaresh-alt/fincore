/**
 * Módulo de Cifrado en el Edge (Frontend)
 *
 * Implementa cifrado de datos sensibles antes de enviarlos al servidor.
 * Usa Web Crypto API (estándar del navegador) con AES-GCM.
 *
 * Campos que se cifran:
 * - RFC/Tax ID
 * - Números de cuenta bancaria
 * - CLABE
 * - Información personal identificable (PII)
 */

// Tipos para los datos cifrados
export interface EncryptedField {
  ciphertext: string;
  iv: string;
  tag: string;
  version: string;
  encryptedAt: string;
}

export interface DeviceFingerprint {
  fingerprint: string;
  components: {
    userAgent: string;
    language: string;
    screenResolution: string;
    timezone: string;
    platform: string;
  };
  generatedAt: string;
}

/**
 * Clase para cifrado de datos sensibles en el cliente
 */
export class EdgeCrypto {
  private publicKey: CryptoKey | null = null;
  private symmetricKey: CryptoKey | null = null;

  /**
   * Inicializa el módulo de cifrado con la clave pública del servidor
   */
  async initialize(publicKeyPem: string): Promise<void> {
    try {
      // Importar clave pública RSA-OAEP del servidor
      const keyData = this.pemToArrayBuffer(publicKeyPem);
      this.publicKey = await crypto.subtle.importKey(
        "spki",
        keyData,
        {
          name: "RSA-OAEP",
          hash: "SHA-256",
        },
        false,
        ["encrypt"]
      );
    } catch (error) {
      console.error("Failed to initialize EdgeCrypto:", error);
      throw error;
    }
  }

  /**
   * Genera una clave simétrica temporal para la sesión
   */
  async generateSessionKey(): Promise<CryptoKey> {
    this.symmetricKey = await crypto.subtle.generateKey(
      {
        name: "AES-GCM",
        length: 256,
      },
      true,
      ["encrypt", "decrypt"]
    );
    return this.symmetricKey;
  }

  /**
   * Cifra un campo sensible usando AES-GCM
   */
  async encryptField(value: string): Promise<EncryptedField> {
    if (!this.symmetricKey) {
      await this.generateSessionKey();
    }

    // Generar IV aleatorio (12 bytes para AES-GCM)
    const iv = crypto.getRandomValues(new Uint8Array(12));

    // Cifrar
    const encoder = new TextEncoder();
    const data = encoder.encode(value);

    const ciphertext = await crypto.subtle.encrypt(
      {
        name: "AES-GCM",
        iv: iv,
        tagLength: 128,
      },
      this.symmetricKey!,
      data
    );

    return {
      ciphertext: this.arrayBufferToBase64(ciphertext),
      iv: this.arrayBufferToBase64(iv),
      tag: "", // El tag está incluido en el ciphertext en Web Crypto API
      version: "aes-gcm-256-v1",
      encryptedAt: new Date().toISOString(),
    };
  }

  /**
   * Cifra múltiples campos PII en un objeto
   */
  async encryptPII(
    data: Record<string, unknown>,
    piiFields: string[]
  ): Promise<Record<string, unknown>> {
    const result = { ...data };

    for (const field of piiFields) {
      if (result[field] && typeof result[field] === "string") {
        const encrypted = await this.encryptField(result[field] as string);
        result[`${field}_encrypted`] = encrypted;
        // Mantener solo últimos 4 caracteres para referencia
        const original = result[field] as string;
        result[`${field}_masked`] = `****${original.slice(-4)}`;
        delete result[field];
      }
    }

    return result;
  }

  /**
   * Exporta la clave de sesión cifrada con la clave pública del servidor
   */
  async exportEncryptedSessionKey(): Promise<string> {
    if (!this.publicKey || !this.symmetricKey) {
      throw new Error("Keys not initialized");
    }

    // Exportar clave simétrica
    const rawKey = await crypto.subtle.exportKey("raw", this.symmetricKey);

    // Cifrar con clave pública del servidor
    const encryptedKey = await crypto.subtle.encrypt(
      {
        name: "RSA-OAEP",
      },
      this.publicKey,
      rawKey
    );

    return this.arrayBufferToBase64(encryptedKey);
  }

  // Utilidades
  private pemToArrayBuffer(pem: string): ArrayBuffer {
    const b64 = pem
      .replace(/-----BEGIN PUBLIC KEY-----/, "")
      .replace(/-----END PUBLIC KEY-----/, "")
      .replace(/\s/g, "");
    return this.base64ToArrayBuffer(b64);
  }

  private base64ToArrayBuffer(base64: string): ArrayBuffer {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  }

  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }
}

/**
 * Genera Device Fingerprint para verificación de dispositivos
 */
export async function generateDeviceFingerprint(): Promise<DeviceFingerprint> {
  const components = {
    userAgent: navigator.userAgent,
    language: navigator.language,
    screenResolution: `${screen.width}x${screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    platform: navigator.platform,
  };

  // Generar hash de los componentes
  const encoder = new TextEncoder();
  const data = encoder.encode(Object.values(components).join("|"));
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const fingerprint = hashArray
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  return {
    fingerprint: fingerprint.substring(0, 32),
    components,
    generatedAt: new Date().toISOString(),
  };
}

/**
 * Genera Canvas Fingerprint para identificación más precisa
 */
export async function generateCanvasFingerprint(): Promise<string> {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  if (!ctx) {
    return "";
  }

  // Dibujar texto con diferentes fuentes y estilos
  ctx.textBaseline = "top";
  ctx.font = "14px Arial";
  ctx.fillText("FinCore Security", 2, 2);
  ctx.font = "18px Times New Roman";
  ctx.fillText("Device Check", 4, 18);

  // Generar hash del canvas
  const dataUrl = canvas.toDataURL();
  const encoder = new TextEncoder();
  const data = encoder.encode(dataUrl);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));

  return hashArray
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .substring(0, 32);
}

/**
 * Verifica si el dispositivo es conocido comparando fingerprints
 */
export function isKnownDevice(
  currentFingerprint: string,
  storedFingerprints: string[]
): boolean {
  return storedFingerprints.some((stored) => {
    // Permitir cierta variación (80% de similitud)
    const similarity = calculateSimilarity(currentFingerprint, stored);
    return similarity >= 0.8;
  });
}

/**
 * Calcula la similitud entre dos fingerprints
 */
function calculateSimilarity(fp1: string, fp2: string): number {
  if (fp1 === fp2) return 1;
  if (fp1.length !== fp2.length) return 0;

  let matches = 0;
  for (let i = 0; i < fp1.length; i++) {
    if (fp1[i] === fp2[i]) matches++;
  }

  return matches / fp1.length;
}

/**
 * Genera un token de seguridad para requests
 */
export async function generateSecurityToken(): Promise<string> {
  const timestamp = Date.now().toString();
  const random = crypto.getRandomValues(new Uint8Array(16));
  const randomStr = Array.from(random)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  const data = `${timestamp}|${randomStr}`;
  const encoder = new TextEncoder();
  const hashBuffer = await crypto.subtle.digest(
    "SHA-256",
    encoder.encode(data)
  );
  const hashArray = Array.from(new Uint8Array(hashBuffer));

  return btoa(
    JSON.stringify({
      t: timestamp,
      r: randomStr,
      h: hashArray
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("")
        .substring(0, 16),
    })
  );
}

// Exportar instancia singleton
export const edgeCrypto = new EdgeCrypto();
