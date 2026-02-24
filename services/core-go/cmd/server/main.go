/*
FinCore Core Financial Service - Go Implementation

Este servicio maneja las operaciones financieras críticas con:
- Alta concurrencia (goroutines)
- Seguridad de grado militar
- Latencia mínima
- Binarios estáticos seguros

Inspirado en arquitecturas de Nubank, Stripe, y Square.
*/
package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/fincore/core-go/internal/handlers"
	"github.com/fincore/core-go/internal/security"
	"github.com/gin-gonic/gin"
)

func main() {
	// Configurar modo producción
	if os.Getenv("GIN_MODE") == "" {
		gin.SetMode(gin.ReleaseMode)
	}

	// Inicializar seguridad
	securityManager := security.NewSecurityManager()

	// Crear router
	router := setupRouter(securityManager)

	// Configurar servidor con timeouts seguros
	srv := &http.Server{
		Addr:         getServerAddr(),
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Iniciar servidor en goroutine
	go func() {
		log.Printf("Starting FinCore Go Service on %s", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %s", err)
		}
	}()

	// Graceful shutdown
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	log.Println("Server exited cleanly")
}

func getServerAddr() string {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8002"
	}
	return ":" + port
}

func setupRouter(secMgr *security.SecurityManager) *gin.Engine {
	router := gin.New()

	// Middleware de seguridad
	router.Use(gin.Recovery())
	router.Use(securityMiddleware(secMgr))
	router.Use(corsMiddleware())

	// Health check
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":  "healthy",
			"service": "fincore-core-go",
			"version": "1.0.0",
		})
	})

	// API v1
	v1 := router.Group("/api/v1")
	{
		// Transacciones financieras (requiere mTLS)
		transactions := v1.Group("/transactions")
		transactions.Use(mTLSMiddleware())
		{
			transactions.POST("/process", handlers.ProcessTransaction)
			transactions.GET("/verify/:id", handlers.VerifyTransaction)
			transactions.POST("/batch", handlers.BatchProcess)
		}

		// Ledger inmutable
		ledger := v1.Group("/ledger")
		{
			ledger.POST("/entry", handlers.CreateLedgerEntry)
			ledger.GET("/verify", handlers.VerifyLedgerIntegrity)
			ledger.GET("/entry/:sequence", handlers.GetLedgerEntry)
		}

		// Servicios internos (Zero Trust)
		internal := v1.Group("/internal")
		internal.Use(zeroTrustMiddleware(secMgr))
		{
			internal.POST("/calculate", handlers.CalculateMetrics)
			internal.POST("/validate-transfer", handlers.ValidateTransfer)
		}
	}

	return router
}

// Middleware de seguridad general
func securityMiddleware(secMgr *security.SecurityManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Agregar headers de seguridad
		c.Header("X-Content-Type-Options", "nosniff")
		c.Header("X-Frame-Options", "DENY")
		c.Header("X-XSS-Protection", "1; mode=block")
		c.Header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		c.Header("Content-Security-Policy", "default-src 'self'")

		// Generar request ID
		requestID := secMgr.GenerateRequestID()
		c.Set("request_id", requestID)
		c.Header("X-Request-ID", requestID)

		c.Next()
	}
}

// CORS Middleware
func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		allowedOrigins := []string{
			"http://localhost:3000",
			"https://fincore.app",
		}

		for _, allowed := range allowedOrigins {
			if origin == allowed {
				c.Header("Access-Control-Allow-Origin", origin)
				break
			}
		}

		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Service-Token")
		c.Header("Access-Control-Max-Age", "86400")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(http.StatusNoContent)
			return
		}

		c.Next()
	}
}

// mTLS Middleware para endpoints críticos
func mTLSMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// En producción, verificar certificado del cliente
		if os.Getenv("ENABLE_MTLS") == "true" {
			if c.Request.TLS == nil || len(c.Request.TLS.PeerCertificates) == 0 {
				c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
					"error": "mTLS certificate required",
				})
				return
			}
		}
		c.Next()
	}
}

// Zero Trust Middleware para comunicación entre servicios
func zeroTrustMiddleware(secMgr *security.SecurityManager) gin.HandlerFunc {
	return func(c *gin.Context) {
		serviceToken := c.GetHeader("X-Service-Token")
		if serviceToken == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "Service token required",
			})
			return
		}

		// Verificar token temporal
		claims, err := secMgr.VerifyServiceToken(serviceToken)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": "Invalid service token",
			})
			return
		}

		c.Set("service_claims", claims)
		c.Next()
	}
}
