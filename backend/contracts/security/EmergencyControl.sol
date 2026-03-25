// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title EmergencyControl
 * @author FinCore Security Team
 * @notice Contrato base con controles de emergencia para Fintech
 * @dev Implementa Circuit Breaker, Multi-sig virtual y monitoreo
 *
 * FUNCIONALIDADES DE SEGURIDAD:
 * 1. Circuit Breaker (Pausable) - Detiene todas las operaciones
 * 2. Role-Based Access Control - Solo autorizados pueden pausar
 * 3. Reentrancy Guard - Previene ataques de reentrada
 * 4. Rate Limiting - Limita operaciones por tiempo
 * 5. Emergency Withdrawal - Retiro de emergencia con timelock
 */
contract EmergencyControl is AccessControl, Pausable, ReentrancyGuard {

    // ============ ROLES ============
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant EMERGENCY_ROLE = keccak256("EMERGENCY_ROLE");
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    // ============ ESTADO ============

    // Circuit Breaker state
    bool public circuitBreakerTripped;
    uint256 public lastPauseTime;
    uint256 public pauseCount;

    // Rate limiting
    mapping(address => uint256) public lastOperationTime;
    mapping(address => uint256) public operationCount;
    uint256 public rateLimitWindow = 1 hours;
    uint256 public maxOperationsPerWindow = 100;

    // Emergency withdrawal timelock
    uint256 public emergencyTimelockDuration = 24 hours;
    mapping(bytes32 => EmergencyAction) public emergencyActions;

    struct EmergencyAction {
        address initiator;
        bytes32 actionType;
        bytes data;
        uint256 scheduledTime;
        bool executed;
        uint256 approvalCount;
        mapping(address => bool) approvals;
    }

    // Monitoring thresholds
    uint256 public largeTransactionThreshold;
    uint256 public maxDailyWithdrawal;
    uint256 public dailyWithdrawalAmount;
    uint256 public lastWithdrawalReset;

    // ============ EVENTOS ============

    event CircuitBreakerTripped(address indexed triggeredBy, string reason);
    event CircuitBreakerReset(address indexed resetBy);
    event EmergencyPause(address indexed pausedBy, string reason);
    event EmergencyUnpause(address indexed unpausedBy);
    event LargeTransactionDetected(
        address indexed from,
        address indexed to,
        uint256 amount,
        string transactionType
    );
    event SuspiciousActivity(
        address indexed actor,
        string activityType,
        bytes data
    );
    event EmergencyActionScheduled(
        bytes32 indexed actionId,
        address indexed initiator,
        bytes32 actionType,
        uint256 scheduledTime
    );
    event EmergencyActionExecuted(bytes32 indexed actionId);
    event EmergencyActionCancelled(bytes32 indexed actionId);
    event RateLimitExceeded(address indexed user, uint256 operationCount);
    event ThresholdBreached(string thresholdType, uint256 value, uint256 threshold);

    // ============ MODIFICADORES ============

    /**
     * @dev Verifica que el circuit breaker no esté activado
     */
    modifier circuitBreakerOff() {
        require(!circuitBreakerTripped, "Circuit breaker is tripped");
        _;
    }

    /**
     * @dev Rate limiting por usuario
     */
    modifier rateLimited() {
        _checkRateLimit(msg.sender);
        _;
    }

    /**
     * @dev Verifica límite de retiro diario
     */
    modifier withinDailyLimit(uint256 amount) {
        _resetDailyLimitIfNeeded();
        require(
            dailyWithdrawalAmount + amount <= maxDailyWithdrawal,
            "Daily withdrawal limit exceeded"
        );
        _;
        dailyWithdrawalAmount += amount;
    }

    // ============ CONSTRUCTOR ============

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(PAUSER_ROLE, msg.sender);
        _grantRole(EMERGENCY_ROLE, msg.sender);
        _grantRole(OPERATOR_ROLE, msg.sender);

        // Set default thresholds
        largeTransactionThreshold = 10000 ether; // 10,000 tokens
        maxDailyWithdrawal = 100000 ether; // 100,000 tokens
        lastWithdrawalReset = block.timestamp;
    }

    // ============ FUNCIONES DE EMERGENCIA ============

    /**
     * @notice Activa el Circuit Breaker - DETIENE TODO
     * @param reason Motivo de la activación
     */
    function tripCircuitBreaker(string calldata reason)
        external
        onlyRole(EMERGENCY_ROLE)
    {
        circuitBreakerTripped = true;
        _pause();
        lastPauseTime = block.timestamp;
        pauseCount++;

        emit CircuitBreakerTripped(msg.sender, reason);
    }

    /**
     * @notice Resetea el Circuit Breaker
     * @dev Requiere rol de admin y verificación adicional
     */
    function resetCircuitBreaker()
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(circuitBreakerTripped, "Circuit breaker not tripped");
        require(
            block.timestamp >= lastPauseTime + 1 hours,
            "Must wait 1 hour before reset"
        );

        circuitBreakerTripped = false;
        _unpause();

        emit CircuitBreakerReset(msg.sender);
    }

    /**
     * @notice Pausa de emergencia rápida
     * @param reason Motivo de la pausa
     */
    function emergencyPause(string calldata reason)
        external
        onlyRole(PAUSER_ROLE)
    {
        _pause();
        lastPauseTime = block.timestamp;
        pauseCount++;

        emit EmergencyPause(msg.sender, reason);
    }

    /**
     * @notice Despausa el contrato
     */
    function emergencyUnpause()
        external
        onlyRole(PAUSER_ROLE)
    {
        require(!circuitBreakerTripped, "Circuit breaker must be reset first");
        _unpause();

        emit EmergencyUnpause(msg.sender);
    }

    // ============ ACCIONES PROGRAMADAS ============

    /**
     * @notice Programa una acción de emergencia con timelock
     * @param actionType Tipo de acción
     * @param data Datos de la acción
     */
    function scheduleEmergencyAction(
        bytes32 actionType,
        bytes calldata data
    )
        external
        onlyRole(EMERGENCY_ROLE)
        returns (bytes32 actionId)
    {
        actionId = keccak256(abi.encodePacked(
            actionType,
            data,
            block.timestamp,
            msg.sender
        ));

        EmergencyAction storage action = emergencyActions[actionId];
        action.initiator = msg.sender;
        action.actionType = actionType;
        action.data = data;
        action.scheduledTime = block.timestamp + emergencyTimelockDuration;
        action.executed = false;
        action.approvalCount = 1;
        action.approvals[msg.sender] = true;

        emit EmergencyActionScheduled(
            actionId,
            msg.sender,
            actionType,
            action.scheduledTime
        );
    }

    /**
     * @notice Aprueba una acción de emergencia (multi-sig)
     * @param actionId ID de la acción
     */
    function approveEmergencyAction(bytes32 actionId)
        external
        onlyRole(EMERGENCY_ROLE)
    {
        EmergencyAction storage action = emergencyActions[actionId];
        require(action.initiator != address(0), "Action does not exist");
        require(!action.executed, "Action already executed");
        require(!action.approvals[msg.sender], "Already approved");

        action.approvals[msg.sender] = true;
        action.approvalCount++;
    }

    /**
     * @notice Cancela una acción de emergencia
     * @param actionId ID de la acción
     */
    function cancelEmergencyAction(bytes32 actionId)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        EmergencyAction storage action = emergencyActions[actionId];
        require(action.initiator != address(0), "Action does not exist");
        require(!action.executed, "Action already executed");

        delete emergencyActions[actionId];

        emit EmergencyActionCancelled(actionId);
    }

    // ============ MONITOREO ============

    /**
     * @notice Registra una transacción grande para monitoreo
     * @param from Dirección origen
     * @param to Dirección destino
     * @param amount Monto
     * @param txType Tipo de transacción
     */
    function _monitorTransaction(
        address from,
        address to,
        uint256 amount,
        string memory txType
    ) internal {
        if (amount >= largeTransactionThreshold) {
            emit LargeTransactionDetected(from, to, amount, txType);
            emit ThresholdBreached("LARGE_TRANSACTION", amount, largeTransactionThreshold);
        }
    }

    /**
     * @notice Reporta actividad sospechosa
     * @param actor Dirección del actor
     * @param activityType Tipo de actividad
     * @param data Datos adicionales
     */
    function _reportSuspiciousActivity(
        address actor,
        string memory activityType,
        bytes memory data
    ) internal {
        emit SuspiciousActivity(actor, activityType, data);
    }

    // ============ RATE LIMITING ============

    /**
     * @dev Verifica y actualiza el rate limit
     */
    function _checkRateLimit(address user) internal {
        // Reset counter if window has passed
        if (block.timestamp >= lastOperationTime[user] + rateLimitWindow) {
            operationCount[user] = 0;
            lastOperationTime[user] = block.timestamp;
        }

        operationCount[user]++;

        if (operationCount[user] > maxOperationsPerWindow) {
            emit RateLimitExceeded(user, operationCount[user]);
            revert("Rate limit exceeded");
        }
    }

    /**
     * @dev Resetea el límite diario si es necesario
     */
    function _resetDailyLimitIfNeeded() internal {
        if (block.timestamp >= lastWithdrawalReset + 1 days) {
            dailyWithdrawalAmount = 0;
            lastWithdrawalReset = block.timestamp;
        }
    }

    // ============ CONFIGURACIÓN ============

    /**
     * @notice Actualiza umbral de transacción grande
     */
    function setLargeTransactionThreshold(uint256 threshold)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        largeTransactionThreshold = threshold;
    }

    /**
     * @notice Actualiza límite de retiro diario
     */
    function setMaxDailyWithdrawal(uint256 limit)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        maxDailyWithdrawal = limit;
    }

    /**
     * @notice Actualiza parámetros de rate limiting
     */
    function setRateLimitParams(
        uint256 window,
        uint256 maxOps
    )
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        rateLimitWindow = window;
        maxOperationsPerWindow = maxOps;
    }

    /**
     * @notice Actualiza duración del timelock
     */
    function setEmergencyTimelockDuration(uint256 duration)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(duration >= 1 hours, "Minimum 1 hour");
        require(duration <= 7 days, "Maximum 7 days");
        emergencyTimelockDuration = duration;
    }

    // ============ VISTAS ============

    /**
     * @notice Estado actual del sistema de seguridad
     */
    function getSecurityStatus()
        external
        view
        returns (
            bool isPaused,
            bool isCircuitBreakerTripped,
            uint256 totalPauseCount,
            uint256 lastPause,
            uint256 currentDailyWithdrawal,
            uint256 dailyLimit
        )
    {
        return (
            paused(),
            circuitBreakerTripped,
            pauseCount,
            lastPauseTime,
            dailyWithdrawalAmount,
            maxDailyWithdrawal
        );
    }

    /**
     * @notice Verifica el rate limit de un usuario
     */
    function getUserRateLimitStatus(address user)
        external
        view
        returns (
            uint256 operations,
            uint256 maxOps,
            uint256 windowRemaining
        )
    {
        uint256 windowEnd = lastOperationTime[user] + rateLimitWindow;
        uint256 remaining = windowEnd > block.timestamp ? windowEnd - block.timestamp : 0;

        return (
            operationCount[user],
            maxOperationsPerWindow,
            remaining
        );
    }
}
