# Build stage
FROM golang:1.22-alpine AS builder

# Instalar certificados y git
RUN apk add --no-cache ca-certificates git

WORKDIR /app

# Copiar go.mod y go.sum primero para cache de dependencias
COPY go.mod go.sum* ./
RUN go mod download

# Copiar código fuente
COPY . .

# Compilar binario estático
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s -X main.Version=1.0.0" \
    -o /app/fincore-core \
    ./cmd/server

# Runtime stage - imagen mínima
FROM scratch

# Copiar certificados CA
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Copiar binario
COPY --from=builder /app/fincore-core /fincore-core

# Puerto
EXPOSE 8002

# Ejecutar
ENTRYPOINT ["/fincore-core"]
