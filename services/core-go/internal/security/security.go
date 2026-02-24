/*
Módulo de Seguridad de Grado Militar para Go

Implementa:
- Cifrado con libsodium (NaCl)
- Verificación de tokens Zero Trust
- Device Fingerprinting
- Integridad de datos con HMAC
*/
package security

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"time"

	"github.com/google/uuid"
	"golang.org/x/crypto/nacl/secretbox"
)

// SecurityManager maneja todas las operaciones de seguridad
type SecurityManager struct {
	secretKey    []byte
	encryptKey   [32]byte
	vaultEnabled bool
}

// ServiceTokenClaims contiene los claims de un token de servicio
type ServiceTokenClaims struct {
	Source      string   `json:"source"`
	Target      string   `json:"target"`
	Permissions []string `json:"permissions"`
	IssuedAt    string   `json:"iat"`
	ExpiresAt   string   `json:"exp"`
	TokenID     string   `json:"token_id"`
}

// NewSecurityManager crea una nueva instancia del manager de seguridad
func NewSecurityManager() *SecurityManager {
	secretKey := os.Getenv("SECRET_KEY")
	if secretKey == "" {
		secretKey = "fincore-default-key-change-in-production"
	}

	encryptKey := os.Getenv("ENCRYPTION_KEY")
	if encryptKey == "" {
		encryptKey = "fincore-encrypt-key-32-bytes-ok!"
	}

	// Derivar clave de 32 bytes
	var key [32]byte
	h := sha256.Sum256([]byte(encryptKey))
	copy(key[:], h[:])

	return &SecurityManager{
		secretKey:    []byte(secretKey),
		encryptKey:   key,
		vaultEnabled: os.Getenv("VAULT_ADDR") != "",
	}
}

// GenerateRequestID genera un ID único para cada request
func (sm *SecurityManager) GenerateRequestID() string {
	return uuid.New().String()
}

// Encrypt cifra datos usando NaCl secretbox (XSalsa20-Poly1305)
func (sm *SecurityManager) Encrypt(plaintext []byte) (string, error) {
	// Generar nonce aleatorio de 24 bytes
	var nonce [24]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return "", fmt.Errorf("failed to generate nonce: %w", err)
	}

	// Cifrar
	encrypted := secretbox.Seal(nonce[:], plaintext, &nonce, &sm.encryptKey)

	// Retornar como base64
	return base64.StdEncoding.EncodeToString(encrypted), nil
}

// Decrypt descifra datos
func (sm *SecurityManager) Decrypt(ciphertext string) ([]byte, error) {
	// Decodificar base64
	encrypted, err := base64.StdEncoding.DecodeString(ciphertext)
	if err != nil {
		return nil, fmt.Errorf("failed to decode ciphertext: %w", err)
	}

	// Extraer nonce (primeros 24 bytes)
	if len(encrypted) < 24 {
		return nil, errors.New("ciphertext too short")
	}

	var nonce [24]byte
	copy(nonce[:], encrypted[:24])

	// Descifrar
	decrypted, ok := secretbox.Open(nil, encrypted[24:], &nonce, &sm.encryptKey)
	if !ok {
		return nil, errors.New("decryption failed")
	}

	return decrypted, nil
}

// GenerateServiceToken genera un token temporal para comunicación entre servicios
func (sm *SecurityManager) GenerateServiceToken(source, target string, permissions []string, ttlSeconds int) (string, error) {
	now := time.Now()
	expiresAt := now.Add(time.Duration(ttlSeconds) * time.Second)

	claims := ServiceTokenClaims{
		Source:      source,
		Target:      target,
		Permissions: permissions,
		IssuedAt:    now.Format(time.RFC3339),
		ExpiresAt:   expiresAt.Format(time.RFC3339),
		TokenID:     uuid.New().String(),
	}

	// Serializar claims
	claimsJSON, err := json.Marshal(claims)
	if err != nil {
		return "", fmt.Errorf("failed to marshal claims: %w", err)
	}

	// Calcular HMAC
	mac := hmac.New(sha256.New, sm.secretKey)
	mac.Write(claimsJSON)
	signature := hex.EncodeToString(mac.Sum(nil))

	// Combinar claims y signature
	tokenData := map[string]string{
		"claims":    base64.StdEncoding.EncodeToString(claimsJSON),
		"signature": signature,
	}

	tokenJSON, err := json.Marshal(tokenData)
	if err != nil {
		return "", fmt.Errorf("failed to marshal token: %w", err)
	}

	return base64.StdEncoding.EncodeToString(tokenJSON), nil
}

// VerifyServiceToken verifica un token de servicio
func (sm *SecurityManager) VerifyServiceToken(token string) (*ServiceTokenClaims, error) {
	// Decodificar token
	tokenJSON, err := base64.StdEncoding.DecodeString(token)
	if err != nil {
		return nil, fmt.Errorf("invalid token encoding: %w", err)
	}

	var tokenData map[string]string
	if err := json.Unmarshal(tokenJSON, &tokenData); err != nil {
		return nil, fmt.Errorf("invalid token format: %w", err)
	}

	// Obtener claims y signature
	claimsB64, ok := tokenData["claims"]
	if !ok {
		return nil, errors.New("missing claims in token")
	}
	signature, ok := tokenData["signature"]
	if !ok {
		return nil, errors.New("missing signature in token")
	}

	// Decodificar claims
	claimsJSON, err := base64.StdEncoding.DecodeString(claimsB64)
	if err != nil {
		return nil, fmt.Errorf("invalid claims encoding: %w", err)
	}

	// Verificar HMAC
	mac := hmac.New(sha256.New, sm.secretKey)
	mac.Write(claimsJSON)
	expectedSignature := hex.EncodeToString(mac.Sum(nil))

	if !hmac.Equal([]byte(signature), []byte(expectedSignature)) {
		return nil, errors.New("invalid signature")
	}

	// Parsear claims
	var claims ServiceTokenClaims
	if err := json.Unmarshal(claimsJSON, &claims); err != nil {
		return nil, fmt.Errorf("invalid claims format: %w", err)
	}

	// Verificar expiración
	expiresAt, err := time.Parse(time.RFC3339, claims.ExpiresAt)
	if err != nil {
		return nil, fmt.Errorf("invalid expiration time: %w", err)
	}

	if time.Now().After(expiresAt) {
		return nil, errors.New("token expired")
	}

	return &claims, nil
}

// CalculateIntegrityHash calcula hash de integridad para un registro
func (sm *SecurityManager) CalculateIntegrityHash(data map[string]interface{}) string {
	// Serializar de forma determinística
	jsonData, _ := json.Marshal(data)

	// Calcular SHA-256
	hash := sha256.Sum256(jsonData)
	return hex.EncodeToString(hash[:])
}

// VerifyIntegrityHash verifica el hash de integridad
func (sm *SecurityManager) VerifyIntegrityHash(data map[string]interface{}, expectedHash string) bool {
	calculatedHash := sm.CalculateIntegrityHash(data)
	return hmac.Equal([]byte(calculatedHash), []byte(expectedHash))
}

// GenerateDeviceFingerprint genera fingerprint del dispositivo
func (sm *SecurityManager) GenerateDeviceFingerprint(userAgent, acceptLanguage, acceptEncoding string) string {
	components := userAgent + "|" + acceptLanguage + "|" + acceptEncoding
	hash := sha256.Sum256([]byte(components))
	return hex.EncodeToString(hash[:16]) // Primeros 16 bytes (32 caracteres hex)
}

// SecureCompare compara dos strings de forma segura (timing-safe)
func SecureCompare(a, b string) bool {
	return hmac.Equal([]byte(a), []byte(b))
}
