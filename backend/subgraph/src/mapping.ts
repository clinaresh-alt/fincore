/**
 * FinCore Remittance Subgraph Mappings
 *
 * Handlers para eventos del contrato FinCoreRemittance.
 * Compila a WebAssembly para ejecución en The Graph nodes.
 */
import {
  BigInt,
  Bytes,
  Address,
  log,
} from "@graphprotocol/graph-ts"

import {
  RemittanceCreated,
  RemittanceReleased,
  RemittanceRefunded,
  TokenAdded,
  TokenRemoved,
  LiquidityPoolUpdated,
  PlatformFeeUpdated,
} from "../generated/FinCoreRemittance/FinCoreRemittance"

import { ERC20 } from "../generated/FinCoreRemittance/ERC20"

import {
  Remittance,
  RemittanceEvent,
  Token,
  Account,
  DailyStats,
  ProtocolStats,
} from "../generated/schema"

// Constantes
const ZERO = BigInt.fromI32(0)
const ONE = BigInt.fromI32(1)
const SECONDS_PER_DAY = BigInt.fromI32(86400)

// ==================== Helpers ====================

/**
 * Obtiene o crea las estadísticas globales del protocolo.
 */
function getOrCreateProtocolStats(): ProtocolStats {
  let stats = ProtocolStats.load("global")

  if (stats == null) {
    stats = new ProtocolStats("global")
    stats.totalRemittances = ZERO
    stats.activeRemittances = ZERO
    stats.completedRemittances = ZERO
    stats.refundedRemittances = ZERO
    stats.totalVolume = ZERO
    stats.totalFees = ZERO
    stats.supportedTokensCount = ZERO
    stats.uniqueUsers = ZERO
    stats.currentFeeBps = ZERO
    stats.liquidityPool = Bytes.empty()
    stats.lastUpdatedAt = ZERO
    stats.lastBlockNumber = ZERO
    stats.save()
  }

  return stats
}

/**
 * Obtiene o crea una cuenta de usuario.
 */
function getOrCreateAccount(address: Address, timestamp: BigInt): Account {
  let id = address.toHexString()
  let account = Account.load(id)

  if (account == null) {
    account = new Account(id)
    account.remittancesSentCount = ZERO
    account.totalVolumeSent = ZERO
    account.remittancesReleasedCount = ZERO
    account.firstActivityAt = timestamp
    account.lastActivityAt = timestamp

    // Incrementar usuarios únicos
    let stats = getOrCreateProtocolStats()
    stats.uniqueUsers = stats.uniqueUsers.plus(ONE)
    stats.save()
  }

  account.lastActivityAt = timestamp
  account.save()

  return account
}

/**
 * Obtiene o crea un token.
 */
function getOrCreateToken(address: Address): Token {
  let id = address.toHexString()
  let token = Token.load(id)

  if (token == null) {
    token = new Token(id)

    // Intentar leer metadata del token ERC20
    let contract = ERC20.bind(address)

    let symbolResult = contract.try_symbol()
    token.symbol = symbolResult.reverted ? "UNKNOWN" : symbolResult.value

    let nameResult = contract.try_name()
    token.name = nameResult.reverted ? "Unknown Token" : nameResult.value

    let decimalsResult = contract.try_decimals()
    token.decimals = decimalsResult.reverted ? 18 : decimalsResult.value

    token.isSupported = true
    token.totalLocked = ZERO
    token.totalReleased = ZERO
    token.totalRefunded = ZERO
    token.totalFees = ZERO
    token.remittanceCount = ZERO
    token.save()

    // Incrementar contador de tokens
    let stats = getOrCreateProtocolStats()
    stats.supportedTokensCount = stats.supportedTokensCount.plus(ONE)
    stats.save()
  }

  return token
}

/**
 * Obtiene o crea estadísticas diarias.
 */
function getOrCreateDailyStats(timestamp: BigInt): DailyStats {
  let dayTimestamp = timestamp.div(SECONDS_PER_DAY).times(SECONDS_PER_DAY)
  let id = dayTimestamp.toString()

  let stats = DailyStats.load(id)

  if (stats == null) {
    stats = new DailyStats(id)
    stats.date = dayTimestamp
    stats.remittancesCreated = ZERO
    stats.remittancesCompleted = ZERO
    stats.remittancesRefunded = ZERO
    stats.volumeLocked = ZERO
    stats.volumeReleased = ZERO
    stats.volumeRefunded = ZERO
    stats.feesCollected = ZERO
    stats.uniqueUsers = ZERO
    stats.totalGasUsed = ZERO
    stats.save()
  }

  return stats
}

/**
 * Crea un evento de remesa.
 */
function createRemittanceEvent(
  remittance: Remittance,
  eventType: string,
  event: ethereum.Event,
  data: string | null = null
): void {
  let id = event.transaction.hash.toHexString() + "-" + event.logIndex.toString()
  let remittanceEvent = new RemittanceEvent(id)

  remittanceEvent.eventType = eventType
  remittanceEvent.remittance = remittance.id
  remittanceEvent.timestamp = event.block.timestamp
  remittanceEvent.blockNumber = event.block.number
  remittanceEvent.txHash = event.transaction.hash
  remittanceEvent.logIndex = event.logIndex

  if (data != null) {
    remittanceEvent.data = data
  }

  remittanceEvent.save()
}

// ==================== Event Handlers ====================

/**
 * Handler para RemittanceCreated.
 *
 * Se dispara cuando un usuario bloquea fondos en escrow.
 */
export function handleRemittanceCreated(event: RemittanceCreated): void {
  let id = event.params.remittanceId.toString()
  let timestamp = event.block.timestamp

  // Crear o actualizar cuenta del sender
  let sender = getOrCreateAccount(event.params.sender, timestamp)
  sender.remittancesSentCount = sender.remittancesSentCount.plus(ONE)
  sender.totalVolumeSent = sender.totalVolumeSent.plus(event.params.amount)
  sender.save()

  // Obtener o crear token
  let token = getOrCreateToken(event.params.token)
  token.totalLocked = token.totalLocked.plus(event.params.amount)
  token.totalFees = token.totalFees.plus(event.params.fee)
  token.remittanceCount = token.remittanceCount.plus(ONE)
  token.save()

  // Crear remesa
  let remittance = new Remittance(id)
  remittance.referenceId = event.params.referenceId
  remittance.sender = sender.id
  remittance.token = token.id
  remittance.amount = event.params.amount
  remittance.platformFee = event.params.fee
  remittance.createdAt = timestamp
  remittance.expiresAt = event.params.expiresAt
  remittance.state = "Locked"
  remittance.createdTxHash = event.transaction.hash
  remittance.createdBlockNumber = event.block.number
  remittance.save()

  // Crear evento
  createRemittanceEvent(remittance, "Created", event)

  // Actualizar estadísticas diarias
  let dailyStats = getOrCreateDailyStats(timestamp)
  dailyStats.remittancesCreated = dailyStats.remittancesCreated.plus(ONE)
  dailyStats.volumeLocked = dailyStats.volumeLocked.plus(event.params.amount)
  dailyStats.feesCollected = dailyStats.feesCollected.plus(event.params.fee)
  dailyStats.save()

  // Actualizar estadísticas globales
  let stats = getOrCreateProtocolStats()
  stats.totalRemittances = stats.totalRemittances.plus(ONE)
  stats.activeRemittances = stats.activeRemittances.plus(ONE)
  stats.totalVolume = stats.totalVolume.plus(event.params.amount)
  stats.totalFees = stats.totalFees.plus(event.params.fee)
  stats.lastUpdatedAt = timestamp
  stats.lastBlockNumber = event.block.number
  stats.save()

  log.info("RemittanceCreated: {} - {} tokens", [
    id,
    event.params.amount.toString()
  ])
}

/**
 * Handler para RemittanceReleased.
 *
 * Se dispara cuando un operador libera los fondos al pool de liquidez.
 */
export function handleRemittanceReleased(event: RemittanceReleased): void {
  let id = event.params.remittanceId.toString()
  let timestamp = event.block.timestamp

  let remittance = Remittance.load(id)
  if (remittance == null) {
    log.warning("RemittanceReleased: Remesa no encontrada: {}", [id])
    return
  }

  // Actualizar remesa
  remittance.state = "Released"
  remittance.finalTxHash = event.transaction.hash
  remittance.finalizedAt = timestamp

  // Registrar operador
  let operator = getOrCreateAccount(event.params.operator, timestamp)
  operator.remittancesReleasedCount = operator.remittancesReleasedCount.plus(ONE)
  operator.save()
  remittance.releasedBy = operator.id

  remittance.save()

  // Actualizar token
  let token = Token.load(remittance.token)
  if (token != null) {
    token.totalLocked = token.totalLocked.minus(event.params.amount)
    token.totalReleased = token.totalReleased.plus(event.params.amount)
    token.save()
  }

  // Crear evento
  createRemittanceEvent(remittance, "Released", event)

  // Actualizar estadísticas diarias
  let dailyStats = getOrCreateDailyStats(timestamp)
  dailyStats.remittancesCompleted = dailyStats.remittancesCompleted.plus(ONE)
  dailyStats.volumeReleased = dailyStats.volumeReleased.plus(event.params.amount)
  dailyStats.save()

  // Actualizar estadísticas globales
  let stats = getOrCreateProtocolStats()
  stats.activeRemittances = stats.activeRemittances.minus(ONE)
  stats.completedRemittances = stats.completedRemittances.plus(ONE)
  stats.lastUpdatedAt = timestamp
  stats.lastBlockNumber = event.block.number
  stats.save()

  log.info("RemittanceReleased: {} - {} tokens by {}", [
    id,
    event.params.amount.toString(),
    event.params.operator.toHexString()
  ])
}

/**
 * Handler para RemittanceRefunded.
 *
 * Se dispara cuando una remesa es reembolsada (expirada o cancelada).
 */
export function handleRemittanceRefunded(event: RemittanceRefunded): void {
  let id = event.params.remittanceId.toString()
  let timestamp = event.block.timestamp

  let remittance = Remittance.load(id)
  if (remittance == null) {
    log.warning("RemittanceRefunded: Remesa no encontrada: {}", [id])
    return
  }

  // Actualizar remesa
  remittance.state = "Refunded"
  remittance.finalTxHash = event.transaction.hash
  remittance.finalizedAt = timestamp
  remittance.save()

  // Actualizar token
  let token = Token.load(remittance.token)
  if (token != null) {
    token.totalLocked = token.totalLocked.minus(event.params.amount)
    token.totalRefunded = token.totalRefunded.plus(event.params.amount)
    token.save()
  }

  // Crear evento
  createRemittanceEvent(remittance, "Refunded", event)

  // Actualizar estadísticas diarias
  let dailyStats = getOrCreateDailyStats(timestamp)
  dailyStats.remittancesRefunded = dailyStats.remittancesRefunded.plus(ONE)
  dailyStats.volumeRefunded = dailyStats.volumeRefunded.plus(event.params.amount)
  dailyStats.save()

  // Actualizar estadísticas globales
  let stats = getOrCreateProtocolStats()
  stats.activeRemittances = stats.activeRemittances.minus(ONE)
  stats.refundedRemittances = stats.refundedRemittances.plus(ONE)
  stats.lastUpdatedAt = timestamp
  stats.lastBlockNumber = event.block.number
  stats.save()

  log.info("RemittanceRefunded: {} - {} tokens to {}", [
    id,
    event.params.amount.toString(),
    event.params.sender.toHexString()
  ])
}

/**
 * Handler para TokenAdded.
 */
export function handleTokenAdded(event: TokenAdded): void {
  let token = getOrCreateToken(event.params.token)
  token.isSupported = true
  token.save()

  log.info("TokenAdded: {}", [event.params.token.toHexString()])
}

/**
 * Handler para TokenRemoved.
 */
export function handleTokenRemoved(event: TokenRemoved): void {
  let id = event.params.token.toHexString()
  let token = Token.load(id)

  if (token != null) {
    token.isSupported = false
    token.save()

    // Decrementar contador
    let stats = getOrCreateProtocolStats()
    stats.supportedTokensCount = stats.supportedTokensCount.minus(ONE)
    stats.save()
  }

  log.info("TokenRemoved: {}", [id])
}

/**
 * Handler para LiquidityPoolUpdated.
 */
export function handleLiquidityPoolUpdated(event: LiquidityPoolUpdated): void {
  let stats = getOrCreateProtocolStats()
  stats.liquidityPool = event.params.newPool
  stats.lastUpdatedAt = event.block.timestamp
  stats.save()

  log.info("LiquidityPoolUpdated: {} -> {}", [
    event.params.oldPool.toHexString(),
    event.params.newPool.toHexString()
  ])
}

/**
 * Handler para PlatformFeeUpdated.
 */
export function handlePlatformFeeUpdated(event: PlatformFeeUpdated): void {
  let stats = getOrCreateProtocolStats()
  stats.currentFeeBps = event.params.newFee
  stats.lastUpdatedAt = event.block.timestamp
  stats.save()

  log.info("PlatformFeeUpdated: {} -> {} bps", [
    event.params.oldFee.toString(),
    event.params.newFee.toString()
  ])
}
