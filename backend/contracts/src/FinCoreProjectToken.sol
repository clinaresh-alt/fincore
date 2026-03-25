// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title FinCoreProjectToken
 * @dev Token ERC-20 que representa fracciones de un proyecto de inversion.
 * Implementa controles de acceso, pausabilidad y capacidad de quemar tokens.
 */
contract FinCoreProjectToken is ERC20, ERC20Burnable, ERC20Pausable, AccessControl, ReentrancyGuard {
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant TRANSFER_AGENT_ROLE = keccak256("TRANSFER_AGENT_ROLE");

    // Informacion del proyecto
    bytes32 public projectId;
    uint256 public projectValuation;
    uint256 public totalTokensForSale;
    uint256 public tokensSold;
    uint256 public pricePerToken;  // En USDC (6 decimales)

    // Configuracion de transferencias
    bool public transfersEnabled;
    bool public kycRequired;
    mapping(address => bool) public kycApproved;

    // Limites de inversion
    uint256 public minInvestmentTokens;
    uint256 public maxInvestmentPerWallet;
    mapping(address => uint256) public walletInvestments;

    // Vesting
    mapping(address => uint256) public lockedUntil;

    // Eventos
    event TokensPurchased(address indexed buyer, uint256 amount, uint256 totalPaid);
    event KYCStatusUpdated(address indexed account, bool approved);
    event TransfersToggled(bool enabled);
    event ProjectValuationUpdated(uint256 newValuation);
    event TokensLocked(address indexed account, uint256 until);
    event TokensUnlocked(address indexed account);

    /**
     * @dev Constructor del token del proyecto
     * @param name_ Nombre del token (ej: "FinCore Project 001")
     * @param symbol_ Simbolo del token (ej: "FCP001")
     * @param projectId_ ID interno del proyecto (hash)
     * @param totalSupply_ Total de tokens a crear
     * @param pricePerToken_ Precio por token en USDC (6 decimales)
     * @param admin Direccion del administrador
     */
    constructor(
        string memory name_,
        string memory symbol_,
        bytes32 projectId_,
        uint256 totalSupply_,
        uint256 pricePerToken_,
        address admin
    ) ERC20(name_, symbol_) {
        require(admin != address(0), "Invalid admin address");
        require(totalSupply_ > 0, "Total supply must be positive");
        require(pricePerToken_ > 0, "Price must be positive");

        projectId = projectId_;
        totalTokensForSale = totalSupply_;
        pricePerToken = pricePerToken_;
        projectValuation = totalSupply_ * pricePerToken_;

        // Configuracion por defecto
        transfersEnabled = false;  // Deshabilitadas hasta que termine la venta
        kycRequired = true;
        minInvestmentTokens = 1 * 10**decimals();  // Minimo 1 token
        maxInvestmentPerWallet = totalSupply_ / 10;  // Maximo 10% por wallet

        // Roles
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(MINTER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(TRANSFER_AGENT_ROLE, admin);
    }

    /**
     * @dev Compra tokens del proyecto
     * @param amount Cantidad de tokens a comprar
     */
    function purchaseTokens(uint256 amount) external nonReentrant whenNotPaused {
        require(amount >= minInvestmentTokens, "Below minimum investment");
        require(tokensSold + amount <= totalTokensForSale, "Not enough tokens available");
        require(
            walletInvestments[msg.sender] + amount <= maxInvestmentPerWallet,
            "Exceeds max investment per wallet"
        );

        if (kycRequired) {
            require(kycApproved[msg.sender], "KYC not approved");
        }

        uint256 totalCost = (amount * pricePerToken) / 10**decimals();

        // Actualizar estado
        tokensSold += amount;
        walletInvestments[msg.sender] += amount;

        // Mintear tokens al comprador
        _mint(msg.sender, amount);

        emit TokensPurchased(msg.sender, amount, totalCost);
    }

    /**
     * @dev Mintea tokens (solo para roles autorizados)
     * @param to Direccion destino
     * @param amount Cantidad de tokens
     */
    function mint(address to, uint256 amount) external onlyRole(MINTER_ROLE) {
        require(to != address(0), "Cannot mint to zero address");
        _mint(to, amount);
    }

    /**
     * @dev Actualiza el estado KYC de una cuenta
     * @param account Direccion de la cuenta
     * @param approved Estado de aprobacion
     */
    function setKYCStatus(address account, bool approved) external onlyRole(TRANSFER_AGENT_ROLE) {
        kycApproved[account] = approved;
        emit KYCStatusUpdated(account, approved);
    }

    /**
     * @dev Actualiza el estado KYC de multiples cuentas
     * @param accounts Lista de direcciones
     * @param approved Estado de aprobacion
     */
    function batchSetKYCStatus(address[] calldata accounts, bool approved) external onlyRole(TRANSFER_AGENT_ROLE) {
        for (uint256 i = 0; i < accounts.length; i++) {
            kycApproved[accounts[i]] = approved;
            emit KYCStatusUpdated(accounts[i], approved);
        }
    }

    /**
     * @dev Habilita o deshabilita transferencias
     * @param enabled Nuevo estado
     */
    function toggleTransfers(bool enabled) external onlyRole(DEFAULT_ADMIN_ROLE) {
        transfersEnabled = enabled;
        emit TransfersToggled(enabled);
    }

    /**
     * @dev Actualiza la valuacion del proyecto
     * @param newValuation Nueva valuacion total
     */
    function updateProjectValuation(uint256 newValuation) external onlyRole(DEFAULT_ADMIN_ROLE) {
        projectValuation = newValuation;
        pricePerToken = newValuation / totalSupply();
        emit ProjectValuationUpdated(newValuation);
    }

    /**
     * @dev Bloquea tokens hasta una fecha
     * @param account Direccion a bloquear
     * @param until Timestamp hasta cuando estan bloqueados
     */
    function lockTokens(address account, uint256 until) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(until > block.timestamp, "Lock time must be in future");
        lockedUntil[account] = until;
        emit TokensLocked(account, until);
    }

    /**
     * @dev Desbloquea tokens de una cuenta
     * @param account Direccion a desbloquear
     */
    function unlockTokens(address account) external onlyRole(DEFAULT_ADMIN_ROLE) {
        lockedUntil[account] = 0;
        emit TokensUnlocked(account);
    }

    /**
     * @dev Pausa el contrato
     */
    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /**
     * @dev Reanuda el contrato
     */
    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    /**
     * @dev Actualiza limites de inversion
     * @param minTokens Minimo de tokens por compra
     * @param maxPerWallet Maximo de tokens por wallet
     */
    function updateInvestmentLimits(
        uint256 minTokens,
        uint256 maxPerWallet
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        minInvestmentTokens = minTokens;
        maxInvestmentPerWallet = maxPerWallet;
    }

    /**
     * @dev Obtiene informacion del proyecto
     */
    function getProjectInfo() external view returns (
        bytes32 _projectId,
        uint256 _valuation,
        uint256 _totalForSale,
        uint256 _sold,
        uint256 _price,
        bool _transfersEnabled
    ) {
        return (
            projectId,
            projectValuation,
            totalTokensForSale,
            tokensSold,
            pricePerToken,
            transfersEnabled
        );
    }

    /**
     * @dev Balance disponible (no bloqueado) de una cuenta
     * @param account Direccion a consultar
     */
    function availableBalance(address account) external view returns (uint256) {
        if (block.timestamp < lockedUntil[account]) {
            return 0;
        }
        return balanceOf(account);
    }

    // ==================== OVERRIDES ====================

    /**
     * @dev Hook que se ejecuta antes de cada transferencia
     */
    function _update(
        address from,
        address to,
        uint256 amount
    ) internal virtual override(ERC20, ERC20Pausable) {
        // Permitir mint y burn siempre
        if (from != address(0) && to != address(0)) {
            // Verificar si las transferencias estan habilitadas
            require(
                transfersEnabled ||
                hasRole(TRANSFER_AGENT_ROLE, msg.sender),
                "Transfers not enabled"
            );

            // Verificar KYC si es requerido
            if (kycRequired) {
                require(kycApproved[to], "Recipient KYC not approved");
            }

            // Verificar bloqueo
            require(
                block.timestamp >= lockedUntil[from],
                "Tokens are locked"
            );
        }

        super._update(from, to, amount);
    }

    /**
     * @dev Verifica soporte de interfaces
     */
    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(AccessControl)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
