/*
Handlers para el servicio Go de FinCore

Maneja:
- Procesamiento de transacciones de alta velocidad
- Ledger inmutable
- Métricas financieras
*/
package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/shopspring/decimal"
)

// Transaction representa una transacción financiera
type Transaction struct {
	ID              string          `json:"id"`
	Type            string          `json:"type"`
	UserID          string          `json:"user_id"`
	ProjectID       string          `json:"project_id,omitempty"`
	InvestmentID    string          `json:"investment_id,omitempty"`
	Amount          decimal.Decimal `json:"amount"`
	Currency        string          `json:"currency"`
	Status          string          `json:"status"`
	IntegrityHash   string          `json:"integrity_hash"`
	ProcessedAt     time.Time       `json:"processed_at"`
	ProcessingTime  int64           `json:"processing_time_ms"`
}

// LedgerEntry representa una entrada en el ledger inmutable
type LedgerEntry struct {
	SequenceNumber int64           `json:"sequence_number"`
	PreviousHash   string          `json:"previous_hash"`
	EntryHash      string          `json:"entry_hash"`
	EntryType      string          `json:"entry_type"`
	Amount         decimal.Decimal `json:"amount"`
	Currency       string          `json:"currency"`
	Description    string          `json:"description"`
	CreatedAt      time.Time       `json:"created_at"`
	IsVerified     bool            `json:"is_verified"`
}

// ProcessTransaction procesa una transacción de forma concurrente
func ProcessTransaction(c *gin.Context) {
	startTime := time.Now()

	var req struct {
		Type         string          `json:"type" binding:"required"`
		UserID       string          `json:"user_id" binding:"required"`
		ProjectID    string          `json:"project_id"`
		InvestmentID string          `json:"investment_id"`
		Amount       decimal.Decimal `json:"amount" binding:"required"`
		Currency     string          `json:"currency"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request",
			"details": err.Error(),
		})
		return
	}

	// Validar monto positivo
	if req.Amount.LessThanOrEqual(decimal.Zero) {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Amount must be positive",
		})
		return
	}

	// Establecer currency por defecto
	if req.Currency == "" {
		req.Currency = "MXN"
	}

	// Procesar transacción (simulado - en producción conectaría a BD)
	transaction := Transaction{
		ID:           uuid.New().String(),
		Type:         req.Type,
		UserID:       req.UserID,
		ProjectID:    req.ProjectID,
		InvestmentID: req.InvestmentID,
		Amount:       req.Amount,
		Currency:     req.Currency,
		Status:       "completed",
		ProcessedAt:  time.Now(),
	}

	// Calcular tiempo de procesamiento
	processingTime := time.Since(startTime).Milliseconds()
	transaction.ProcessingTime = processingTime

	c.JSON(http.StatusOK, gin.H{
		"success":     true,
		"transaction": transaction,
		"message":     "Transaction processed successfully",
	})
}

// VerifyTransaction verifica el estado de una transacción
func VerifyTransaction(c *gin.Context) {
	transactionID := c.Param("id")

	// Validar UUID
	if _, err := uuid.Parse(transactionID); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid transaction ID",
		})
		return
	}

	// En producción, buscaría en la BD
	c.JSON(http.StatusOK, gin.H{
		"transaction_id": transactionID,
		"status":        "verified",
		"verified_at":   time.Now(),
	})
}

// BatchProcess procesa múltiples transacciones concurrentemente
func BatchProcess(c *gin.Context) {
	startTime := time.Now()

	var req struct {
		Transactions []struct {
			Type         string          `json:"type"`
			UserID       string          `json:"user_id"`
			ProjectID    string          `json:"project_id"`
			InvestmentID string          `json:"investment_id"`
			Amount       decimal.Decimal `json:"amount"`
			Currency     string          `json:"currency"`
		} `json:"transactions" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request",
		})
		return
	}

	// Procesar en paralelo usando goroutines
	results := make([]Transaction, len(req.Transactions))
	done := make(chan int, len(req.Transactions))

	for i, tx := range req.Transactions {
		go func(index int, txData struct {
			Type         string
			UserID       string
			ProjectID    string
			InvestmentID string
			Amount       decimal.Decimal
			Currency     string
		}) {
			currency := txData.Currency
			if currency == "" {
				currency = "MXN"
			}

			results[index] = Transaction{
				ID:           uuid.New().String(),
				Type:         txData.Type,
				UserID:       txData.UserID,
				ProjectID:    txData.ProjectID,
				InvestmentID: txData.InvestmentID,
				Amount:       txData.Amount,
				Currency:     currency,
				Status:       "completed",
				ProcessedAt:  time.Now(),
			}
			done <- index
		}(i, struct {
			Type         string
			UserID       string
			ProjectID    string
			InvestmentID string
			Amount       decimal.Decimal
			Currency     string
		}{
			Type:         tx.Type,
			UserID:       tx.UserID,
			ProjectID:    tx.ProjectID,
			InvestmentID: tx.InvestmentID,
			Amount:       tx.Amount,
			Currency:     tx.Currency,
		})
	}

	// Esperar a que terminen todas
	for i := 0; i < len(req.Transactions); i++ {
		<-done
	}

	processingTime := time.Since(startTime).Milliseconds()

	c.JSON(http.StatusOK, gin.H{
		"success":            true,
		"transactions":       results,
		"total_processed":    len(results),
		"processing_time_ms": processingTime,
	})
}

// CreateLedgerEntry crea una entrada en el ledger inmutable
func CreateLedgerEntry(c *gin.Context) {
	var req struct {
		EntryType   string          `json:"entry_type" binding:"required"`
		Amount      decimal.Decimal `json:"amount" binding:"required"`
		Currency    string          `json:"currency"`
		Description string          `json:"description"`
		UserID      string          `json:"user_id"`
		ProjectID   string          `json:"project_id"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request",
		})
		return
	}

	// En producción, esto iría a PostgreSQL con triggers de inmutabilidad
	entry := LedgerEntry{
		SequenceNumber: time.Now().UnixNano(),
		EntryType:      req.EntryType,
		Amount:         req.Amount,
		Currency:       req.Currency,
		Description:    req.Description,
		CreatedAt:      time.Now(),
		IsVerified:     true,
	}

	c.JSON(http.StatusCreated, gin.H{
		"success": true,
		"entry":   entry,
	})
}

// VerifyLedgerIntegrity verifica la integridad de la cadena del ledger
func VerifyLedgerIntegrity(c *gin.Context) {
	// En producción, verificaría toda la cadena de hashes
	c.JSON(http.StatusOK, gin.H{
		"is_valid":         true,
		"entries_verified": 0,
		"verified_at":      time.Now(),
		"message":          "Ledger integrity verified",
	})
}

// GetLedgerEntry obtiene una entrada específica del ledger
func GetLedgerEntry(c *gin.Context) {
	sequence := c.Param("sequence")

	c.JSON(http.StatusOK, gin.H{
		"sequence_number": sequence,
		"status":         "found",
	})
}

// CalculateMetrics calcula métricas financieras
func CalculateMetrics(c *gin.Context) {
	startTime := time.Now()

	var req struct {
		InversionInicial float64   `json:"inversion_inicial" binding:"required"`
		FlujosIngresos   []float64 `json:"flujos_ingresos" binding:"required"`
		FlujosCostos     []float64 `json:"flujos_costos"`
		TasaDescuento    float64   `json:"tasa_descuento" binding:"required"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request",
		})
		return
	}

	// Calcular flujos netos
	flujosNetos := make([]float64, len(req.FlujosIngresos))
	for i := range req.FlujosIngresos {
		costo := 0.0
		if i < len(req.FlujosCostos) {
			costo = req.FlujosCostos[i]
		}
		flujosNetos[i] = req.FlujosIngresos[i] - costo
	}

	// Calcular VAN
	van := -req.InversionInicial
	for i, flujo := range flujosNetos {
		van += flujo / pow(1+req.TasaDescuento, float64(i+1))
	}

	// Calcular Payback
	acumulado := -req.InversionInicial
	payback := -1.0
	for i, flujo := range flujosNetos {
		acumulado += flujo
		if acumulado >= 0 && payback < 0 {
			// Interpolación
			flujoAnterior := acumulado - flujo
			payback = float64(i) + (-flujoAnterior / flujo)
			break
		}
	}

	// Calcular ROI
	totalFlujos := 0.0
	for _, f := range flujosNetos {
		totalFlujos += f
	}
	roi := (totalFlujos - req.InversionInicial) / req.InversionInicial

	processingTime := time.Since(startTime).Microseconds()

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"metrics": gin.H{
			"van":              van,
			"roi":              roi,
			"payback_meses":    payback,
			"es_viable":        van > 0,
			"flujos_netos":     flujosNetos,
		},
		"processing_time_us": processingTime,
	})
}

// ValidateTransfer valida una transferencia antes de ejecutarla
func ValidateTransfer(c *gin.Context) {
	var req struct {
		FromAccount string          `json:"from_account" binding:"required"`
		ToAccount   string          `json:"to_account" binding:"required"`
		Amount      decimal.Decimal `json:"amount" binding:"required"`
		Currency    string          `json:"currency"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid request",
		})
		return
	}

	// Validaciones
	validations := []string{}
	isValid := true

	if req.Amount.LessThanOrEqual(decimal.Zero) {
		validations = append(validations, "Amount must be positive")
		isValid = false
	}

	if req.FromAccount == req.ToAccount {
		validations = append(validations, "Source and destination accounts must be different")
		isValid = false
	}

	c.JSON(http.StatusOK, gin.H{
		"is_valid":    isValid,
		"validations": validations,
		"validated_at": time.Now(),
	})
}

// Función auxiliar para potencia
func pow(base, exp float64) float64 {
	result := 1.0
	for i := 0; i < int(exp); i++ {
		result *= base
	}
	return result
}
