// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title FinCoreRemittance
 * @dev Contrato de escrow para remesas transfronterizas.
 *
 * Flujo:
 * 1. Usuario deposita stablecoins (USDC/USDT) -> lockFunds()
 * 2. Operador confirma entrega fiat al beneficiario -> releaseFunds()
 * 3. Si no se libera en 48h, sender puede reclamar reembolso -> refund()
 *
 * Seguridad:
 * - AccessControl con roles OPERATOR_ROLE y ADMIN_ROLE
 * - ReentrancyGuard para prevenir ataques de reentrada
 * - Pausable para emergencias
 * - Time-lock de 48 horas para reembolsos automaticos
 */
contract FinCoreRemittance is AccessControl, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    // ============ Roles ============
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");

    // ============ Constantes ============
    uint256 public constant TIMELOCK_DURATION = 48 hours;
    uint256 public constant MIN_AMOUNT = 1e6; // 1 USDC (6 decimals)
    uint256 public constant MAX_AMOUNT = 100_000e6; // 100,000 USDC

    // ============ Estructuras ============
    struct Remittance {
        bytes32 referenceId;      // ID externo de referencia
        address sender;           // Quien deposita los fondos
        address token;            // USDC/USDT address
        uint256 amount;           // Monto bloqueado
        uint256 platformFee;      // Comision de plataforma
        uint256 createdAt;        // Timestamp de creacion
        uint256 expiresAt;        // Timestamp de expiracion (createdAt + 48h)
        RemittanceState state;    // Estado actual
    }

    enum RemittanceState {
        Locked,     // Fondos bloqueados en escrow
        Released,   // Fondos liberados al pool de liquidez
        Refunded,   // Fondos devueltos al sender
        Cancelled   // Cancelado antes de lock
    }

    // ============ Storage ============
    // Mapping de ID de remesa -> datos
    mapping(uint256 => Remittance) public remittances;
    uint256 public nextRemittanceId;

    // Mapping de referenceId externo -> remittanceId interno
    mapping(bytes32 => uint256) public referenceToId;

    // Tokens soportados (USDC, USDT, etc.)
    mapping(address => bool) public supportedTokens;

    // Pool de liquidez donde se liberan los fondos
    address public liquidityPool;

    // Fee de plataforma en basis points (100 = 1%)
    uint256 public platformFeeBps;

    // Totales para conciliacion
    uint256 public totalLocked;
    uint256 public totalReleased;
    uint256 public totalRefunded;
    uint256 public totalFeesCollected;

    // ============ Eventos ============
    event RemittanceCreated(
        uint256 indexed remittanceId,
        bytes32 indexed referenceId,
        address indexed sender,
        address token,
        uint256 amount,
        uint256 fee,
        uint256 expiresAt
    );

    event RemittanceReleased(
        uint256 indexed remittanceId,
        bytes32 indexed referenceId,
        address indexed operator,
        uint256 amount
    );

    event RemittanceRefunded(
        uint256 indexed remittanceId,
        bytes32 indexed referenceId,
        address indexed sender,
        uint256 amount
    );

    event TokenAdded(address indexed token);
    event TokenRemoved(address indexed token);
    event LiquidityPoolUpdated(address indexed oldPool, address indexed newPool);
    event PlatformFeeUpdated(uint256 oldFee, uint256 newFee);

    // ============ Errores ============
    error InvalidAmount();
    error TokenNotSupported();
    error RemittanceNotFound();
    error InvalidState();
    error NotExpired();
    error AlreadyExpired();
    error NotSender();
    error ReferenceAlreadyUsed();
    error InvalidAddress();

    // ============ Constructor ============
    constructor(
        address _liquidityPool,
        uint256 _platformFeeBps
    ) {
        if (_liquidityPool == address(0)) revert InvalidAddress();

        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
        _grantRole(OPERATOR_ROLE, msg.sender);

        liquidityPool = _liquidityPool;
        platformFeeBps = _platformFeeBps;
    }

    // ============ Funciones Principales ============

    /**
     * @dev Bloquea fondos en escrow para una remesa.
     * @param referenceId ID externo de referencia (del backend)
     * @param token Direccion del stablecoin (USDC/USDT)
     * @param amount Monto a bloquear
     * @return remittanceId ID interno de la remesa
     */
    function lockFunds(
        bytes32 referenceId,
        address token,
        uint256 amount
    ) external nonReentrant whenNotPaused returns (uint256 remittanceId) {
        // Validaciones
        if (amount < MIN_AMOUNT || amount > MAX_AMOUNT) revert InvalidAmount();
        if (!supportedTokens[token]) revert TokenNotSupported();
        if (referenceToId[referenceId] != 0) revert ReferenceAlreadyUsed();

        // Calcular fee
        uint256 fee = (amount * platformFeeBps) / 10000;
        uint256 netAmount = amount - fee;

        // Crear remesa
        remittanceId = ++nextRemittanceId;
        uint256 expiresAt = block.timestamp + TIMELOCK_DURATION;

        remittances[remittanceId] = Remittance({
            referenceId: referenceId,
            sender: msg.sender,
            token: token,
            amount: netAmount,
            platformFee: fee,
            createdAt: block.timestamp,
            expiresAt: expiresAt,
            state: RemittanceState.Locked
        });

        referenceToId[referenceId] = remittanceId;
        totalLocked += netAmount;

        // Transferir fondos al contrato
        IERC20(token).safeTransferFrom(msg.sender, address(this), amount);

        // Transferir fee al pool de liquidez
        if (fee > 0) {
            IERC20(token).safeTransfer(liquidityPool, fee);
            totalFeesCollected += fee;
        }

        emit RemittanceCreated(
            remittanceId,
            referenceId,
            msg.sender,
            token,
            netAmount,
            fee,
            expiresAt
        );

        return remittanceId;
    }

    /**
     * @dev Libera fondos del escrow al pool de liquidez.
     * Solo puede ser llamado por OPERATOR_ROLE despues de confirmar
     * la entrega fiat al beneficiario.
     * @param remittanceId ID de la remesa
     */
    function releaseFunds(uint256 remittanceId)
        external
        nonReentrant
        whenNotPaused
        onlyRole(OPERATOR_ROLE)
    {
        Remittance storage remittance = remittances[remittanceId];

        if (remittance.sender == address(0)) revert RemittanceNotFound();
        if (remittance.state != RemittanceState.Locked) revert InvalidState();

        // Actualizar estado
        remittance.state = RemittanceState.Released;
        totalLocked -= remittance.amount;
        totalReleased += remittance.amount;

        // Transferir fondos al pool de liquidez
        IERC20(remittance.token).safeTransfer(liquidityPool, remittance.amount);

        emit RemittanceReleased(
            remittanceId,
            remittance.referenceId,
            msg.sender,
            remittance.amount
        );
    }

    /**
     * @dev Reembolsa fondos al sender si el time-lock ha expirado.
     * Puede ser llamado por cualquiera despues de 48h.
     * @param remittanceId ID de la remesa
     */
    function refund(uint256 remittanceId) external nonReentrant whenNotPaused {
        Remittance storage remittance = remittances[remittanceId];

        if (remittance.sender == address(0)) revert RemittanceNotFound();
        if (remittance.state != RemittanceState.Locked) revert InvalidState();
        if (block.timestamp < remittance.expiresAt) revert NotExpired();

        // Actualizar estado
        remittance.state = RemittanceState.Refunded;
        totalLocked -= remittance.amount;
        totalRefunded += remittance.amount;

        // Devolver fondos al sender
        IERC20(remittance.token).safeTransfer(remittance.sender, remittance.amount);

        emit RemittanceRefunded(
            remittanceId,
            remittance.referenceId,
            remittance.sender,
            remittance.amount
        );
    }

    /**
     * @dev Permite al sender cancelar antes de que el operador procese.
     * Solo si aun esta en estado Locked y no ha expirado.
     * @param remittanceId ID de la remesa
     */
    function cancelBySender(uint256 remittanceId) external nonReentrant whenNotPaused {
        Remittance storage remittance = remittances[remittanceId];

        if (remittance.sender == address(0)) revert RemittanceNotFound();
        if (remittance.state != RemittanceState.Locked) revert InvalidState();
        if (msg.sender != remittance.sender) revert NotSender();

        // Actualizar estado
        remittance.state = RemittanceState.Cancelled;
        totalLocked -= remittance.amount;
        totalRefunded += remittance.amount;

        // Devolver fondos al sender
        IERC20(remittance.token).safeTransfer(remittance.sender, remittance.amount);

        emit RemittanceRefunded(
            remittanceId,
            remittance.referenceId,
            remittance.sender,
            remittance.amount
        );
    }

    // ============ Funciones de Vista ============

    /**
     * @dev Obtiene datos de una remesa por su ID.
     */
    function getRemittance(uint256 remittanceId)
        external
        view
        returns (
            bytes32 referenceId,
            address sender,
            address token,
            uint256 amount,
            uint256 platformFee,
            uint256 createdAt,
            uint256 expiresAt,
            RemittanceState state
        )
    {
        Remittance storage r = remittances[remittanceId];
        return (
            r.referenceId,
            r.sender,
            r.token,
            r.amount,
            r.platformFee,
            r.createdAt,
            r.expiresAt,
            r.state
        );
    }

    /**
     * @dev Obtiene el ID de remesa por referencia externa.
     */
    function getRemittanceByReference(bytes32 referenceId)
        external
        view
        returns (uint256)
    {
        return referenceToId[referenceId];
    }

    /**
     * @dev Verifica si una remesa puede ser reembolsada (expirada).
     */
    function canRefund(uint256 remittanceId) external view returns (bool) {
        Remittance storage r = remittances[remittanceId];
        return r.state == RemittanceState.Locked && block.timestamp >= r.expiresAt;
    }

    /**
     * @dev Obtiene totales para conciliacion.
     */
    function getTotals()
        external
        view
        returns (
            uint256 locked,
            uint256 released,
            uint256 refunded,
            uint256 fees
        )
    {
        return (totalLocked, totalReleased, totalRefunded, totalFeesCollected);
    }

    // ============ Funciones Admin ============

    /**
     * @dev Agrega un token soportado.
     */
    function addSupportedToken(address token) external onlyRole(ADMIN_ROLE) {
        if (token == address(0)) revert InvalidAddress();
        supportedTokens[token] = true;
        emit TokenAdded(token);
    }

    /**
     * @dev Remueve un token soportado.
     */
    function removeSupportedToken(address token) external onlyRole(ADMIN_ROLE) {
        supportedTokens[token] = false;
        emit TokenRemoved(token);
    }

    /**
     * @dev Actualiza el pool de liquidez.
     */
    function setLiquidityPool(address newPool) external onlyRole(ADMIN_ROLE) {
        if (newPool == address(0)) revert InvalidAddress();
        address oldPool = liquidityPool;
        liquidityPool = newPool;
        emit LiquidityPoolUpdated(oldPool, newPool);
    }

    /**
     * @dev Actualiza el fee de plataforma (max 5%).
     */
    function setPlatformFee(uint256 newFeeBps) external onlyRole(ADMIN_ROLE) {
        require(newFeeBps <= 500, "Fee too high"); // Max 5%
        uint256 oldFee = platformFeeBps;
        platformFeeBps = newFeeBps;
        emit PlatformFeeUpdated(oldFee, newFeeBps);
    }

    /**
     * @dev Pausa el contrato en caso de emergencia.
     */
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
    }

    /**
     * @dev Despausa el contrato.
     */
    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }

    /**
     * @dev Recupera tokens enviados por error (no afecta remesas activas).
     */
    function rescueTokens(
        address token,
        address to,
        uint256 amount
    ) external onlyRole(ADMIN_ROLE) {
        if (to == address(0)) revert InvalidAddress();

        // Verificar que no estamos retirando fondos de remesas activas
        uint256 contractBalance = IERC20(token).balanceOf(address(this));
        require(amount <= contractBalance - totalLocked, "Cannot withdraw locked funds");

        IERC20(token).safeTransfer(to, amount);
    }
}
