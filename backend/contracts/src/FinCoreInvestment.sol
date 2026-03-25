// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title FinCoreInvestment
 * @dev Contrato principal de inversiones con escrow.
 * Gestiona depositos, liberaciones y distribucion de dividendos.
 */
contract FinCoreInvestment is AccessControl, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    bytes32 public constant DIVIDEND_MANAGER_ROLE = keccak256("DIVIDEND_MANAGER_ROLE");

    // Token de pago (USDC)
    IERC20 public paymentToken;
    uint8 public paymentTokenDecimals;

    // Estructura de inversion
    struct Investment {
        bytes32 projectId;
        address investor;
        uint256 amount;
        uint256 tokenAmount;
        uint256 createdAt;
        bool released;
        bool refunded;
    }

    // Estructura de proyecto
    struct Project {
        bytes32 id;
        address tokenContract;
        uint256 targetAmount;
        uint256 raisedAmount;
        uint256 startTime;
        uint256 endTime;
        bool fundingComplete;
        bool fundsReleased;
        ProjectStatus status;
    }

    enum ProjectStatus {
        Draft,
        Active,
        Funded,
        Cancelled,
        Completed
    }

    // Almacenamiento
    mapping(bytes32 => Project) public projects;
    mapping(uint256 => Investment) public investments;
    mapping(bytes32 => uint256[]) public projectInvestments;
    mapping(address => uint256[]) public investorInvestments;
    mapping(bytes32 => mapping(address => uint256)) public investorProjectBalance;

    uint256 public nextInvestmentId;

    // Fees
    uint256 public platformFeePercent;  // En basis points (100 = 1%)
    address public feeRecipient;

    // Limites
    uint256 public minInvestmentAmount;
    uint256 public maxInvestmentAmount;

    // Eventos
    event ProjectCreated(bytes32 indexed projectId, address tokenContract, uint256 targetAmount);
    event ProjectStatusUpdated(bytes32 indexed projectId, ProjectStatus status);
    event InvestmentCreated(
        uint256 indexed investmentId,
        bytes32 indexed projectId,
        address indexed investor,
        uint256 amount,
        uint256 tokenAmount
    );
    event InvestmentReleased(uint256 indexed investmentId, bytes32 indexed projectId);
    event InvestmentRefunded(uint256 indexed investmentId, address indexed investor, uint256 amount);
    event FundsReleased(bytes32 indexed projectId, address recipient, uint256 amount);
    event DividendDistributed(bytes32 indexed projectId, uint256 totalAmount, uint256 holdersCount);
    event FeeUpdated(uint256 newFeePercent);
    event PaymentTokenUpdated(address newToken);

    /**
     * @dev Constructor
     * @param _paymentToken Direccion del token de pago (USDC)
     * @param _paymentTokenDecimals Decimales del token de pago
     * @param _feeRecipient Direccion que recibe los fees
     * @param _admin Administrador del contrato
     */
    constructor(
        address _paymentToken,
        uint8 _paymentTokenDecimals,
        address _feeRecipient,
        address _admin
    ) {
        require(_paymentToken != address(0), "Invalid payment token");
        require(_feeRecipient != address(0), "Invalid fee recipient");
        require(_admin != address(0), "Invalid admin");

        paymentToken = IERC20(_paymentToken);
        paymentTokenDecimals = _paymentTokenDecimals;
        feeRecipient = _feeRecipient;

        platformFeePercent = 100; // 1%
        minInvestmentAmount = 100 * 10**_paymentTokenDecimals; // 100 USDC
        maxInvestmentAmount = 1000000 * 10**_paymentTokenDecimals; // 1M USDC

        _grantRole(DEFAULT_ADMIN_ROLE, _admin);
        _grantRole(OPERATOR_ROLE, _admin);
        _grantRole(DIVIDEND_MANAGER_ROLE, _admin);
    }

    // ==================== PROJECT MANAGEMENT ====================

    /**
     * @dev Crea un nuevo proyecto
     * @param projectId ID unico del proyecto
     * @param tokenContract Direccion del contrato del token del proyecto
     * @param targetAmount Monto objetivo de recaudacion
     * @param startTime Inicio del periodo de inversion
     * @param endTime Fin del periodo de inversion
     */
    function createProject(
        bytes32 projectId,
        address tokenContract,
        uint256 targetAmount,
        uint256 startTime,
        uint256 endTime
    ) external onlyRole(OPERATOR_ROLE) {
        require(projects[projectId].id == bytes32(0), "Project already exists");
        require(tokenContract != address(0), "Invalid token contract");
        require(targetAmount > 0, "Target must be positive");
        require(startTime >= block.timestamp, "Start time must be in future");
        require(endTime > startTime, "End must be after start");

        projects[projectId] = Project({
            id: projectId,
            tokenContract: tokenContract,
            targetAmount: targetAmount,
            raisedAmount: 0,
            startTime: startTime,
            endTime: endTime,
            fundingComplete: false,
            fundsReleased: false,
            status: ProjectStatus.Draft
        });

        emit ProjectCreated(projectId, tokenContract, targetAmount);
    }

    /**
     * @dev Activa un proyecto para recibir inversiones
     * @param projectId ID del proyecto
     */
    function activateProject(bytes32 projectId) external onlyRole(OPERATOR_ROLE) {
        Project storage project = projects[projectId];
        require(project.id != bytes32(0), "Project not found");
        require(project.status == ProjectStatus.Draft, "Project not in draft");

        project.status = ProjectStatus.Active;
        emit ProjectStatusUpdated(projectId, ProjectStatus.Active);
    }

    /**
     * @dev Cancela un proyecto y permite reembolsos
     * @param projectId ID del proyecto
     */
    function cancelProject(bytes32 projectId) external onlyRole(OPERATOR_ROLE) {
        Project storage project = projects[projectId];
        require(project.id != bytes32(0), "Project not found");
        require(
            project.status == ProjectStatus.Draft || project.status == ProjectStatus.Active,
            "Cannot cancel"
        );
        require(!project.fundsReleased, "Funds already released");

        project.status = ProjectStatus.Cancelled;
        emit ProjectStatusUpdated(projectId, ProjectStatus.Cancelled);
    }

    // ==================== INVESTMENT OPERATIONS ====================

    /**
     * @dev Realiza una inversion en un proyecto
     * @param projectId ID del proyecto
     * @param amount Monto a invertir
     * @param tokenAmount Cantidad de tokens a recibir
     */
    function invest(
        bytes32 projectId,
        uint256 amount,
        uint256 tokenAmount
    ) external nonReentrant whenNotPaused {
        Project storage project = projects[projectId];

        require(project.id != bytes32(0), "Project not found");
        require(project.status == ProjectStatus.Active, "Project not active");
        require(block.timestamp >= project.startTime, "Funding not started");
        require(block.timestamp <= project.endTime, "Funding ended");
        require(amount >= minInvestmentAmount, "Below minimum investment");
        require(amount <= maxInvestmentAmount, "Above maximum investment");
        require(project.raisedAmount + amount <= project.targetAmount, "Exceeds target");

        // Transferir tokens del inversor al contrato (escrow)
        paymentToken.safeTransferFrom(msg.sender, address(this), amount);

        // Crear registro de inversion
        uint256 investmentId = nextInvestmentId++;
        investments[investmentId] = Investment({
            projectId: projectId,
            investor: msg.sender,
            amount: amount,
            tokenAmount: tokenAmount,
            createdAt: block.timestamp,
            released: false,
            refunded: false
        });

        // Actualizar indices
        projectInvestments[projectId].push(investmentId);
        investorInvestments[msg.sender].push(investmentId);
        investorProjectBalance[projectId][msg.sender] += amount;

        // Actualizar monto recaudado
        project.raisedAmount += amount;

        // Verificar si se completo el funding
        if (project.raisedAmount >= project.targetAmount) {
            project.fundingComplete = true;
            project.status = ProjectStatus.Funded;
            emit ProjectStatusUpdated(projectId, ProjectStatus.Funded);
        }

        emit InvestmentCreated(investmentId, projectId, msg.sender, amount, tokenAmount);
    }

    /**
     * @dev Libera los fondos de un proyecto al beneficiario
     * @param projectId ID del proyecto
     * @param recipient Direccion que recibe los fondos
     */
    function releaseFunds(
        bytes32 projectId,
        address recipient
    ) external onlyRole(OPERATOR_ROLE) nonReentrant {
        Project storage project = projects[projectId];

        require(project.id != bytes32(0), "Project not found");
        require(project.status == ProjectStatus.Funded, "Not funded");
        require(!project.fundsReleased, "Already released");
        require(recipient != address(0), "Invalid recipient");

        uint256 totalAmount = project.raisedAmount;
        uint256 fee = (totalAmount * platformFeePercent) / 10000;
        uint256 netAmount = totalAmount - fee;

        project.fundsReleased = true;
        project.status = ProjectStatus.Completed;

        // Marcar inversiones como liberadas
        uint256[] storage invIds = projectInvestments[projectId];
        for (uint256 i = 0; i < invIds.length; i++) {
            investments[invIds[i]].released = true;
            emit InvestmentReleased(invIds[i], projectId);
        }

        // Transferir fondos
        if (fee > 0) {
            paymentToken.safeTransfer(feeRecipient, fee);
        }
        paymentToken.safeTransfer(recipient, netAmount);

        emit FundsReleased(projectId, recipient, netAmount);
        emit ProjectStatusUpdated(projectId, ProjectStatus.Completed);
    }

    /**
     * @dev Reembolsa una inversion (solo si el proyecto fue cancelado)
     * @param investmentId ID de la inversion
     */
    function refundInvestment(uint256 investmentId) external nonReentrant {
        Investment storage investment = investments[investmentId];

        require(investment.investor == msg.sender, "Not your investment");
        require(!investment.released, "Already released");
        require(!investment.refunded, "Already refunded");

        Project storage project = projects[investment.projectId];
        require(
            project.status == ProjectStatus.Cancelled ||
            (project.status == ProjectStatus.Active && block.timestamp > project.endTime && !project.fundingComplete),
            "Refund not available"
        );

        investment.refunded = true;
        investorProjectBalance[investment.projectId][msg.sender] -= investment.amount;

        paymentToken.safeTransfer(msg.sender, investment.amount);

        emit InvestmentRefunded(investmentId, msg.sender, investment.amount);
    }

    // ==================== DIVIDEND DISTRIBUTION ====================

    /**
     * @dev Distribuye dividendos a los holders de un proyecto
     * @param projectId ID del proyecto
     * @param totalAmount Monto total a distribuir
     * @param holders Lista de direcciones de holders
     * @param amounts Lista de montos para cada holder
     */
    function distributeDividends(
        bytes32 projectId,
        uint256 totalAmount,
        address[] calldata holders,
        uint256[] calldata amounts
    ) external onlyRole(DIVIDEND_MANAGER_ROLE) nonReentrant {
        require(holders.length == amounts.length, "Length mismatch");
        require(holders.length > 0, "No holders");

        Project storage project = projects[projectId];
        require(project.id != bytes32(0), "Project not found");
        require(project.status == ProjectStatus.Completed, "Project not completed");

        // Verificar que el total coincide
        uint256 sum = 0;
        for (uint256 i = 0; i < amounts.length; i++) {
            sum += amounts[i];
        }
        require(sum == totalAmount, "Amount mismatch");

        // Transferir desde el caller al contrato
        paymentToken.safeTransferFrom(msg.sender, address(this), totalAmount);

        // Distribuir a cada holder
        for (uint256 i = 0; i < holders.length; i++) {
            if (amounts[i] > 0) {
                paymentToken.safeTransfer(holders[i], amounts[i]);
            }
        }

        emit DividendDistributed(projectId, totalAmount, holders.length);
    }

    // ==================== ADMIN FUNCTIONS ====================

    /**
     * @dev Actualiza el fee de la plataforma
     * @param newFeePercent Nuevo fee en basis points
     */
    function setFee(uint256 newFeePercent) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newFeePercent <= 1000, "Fee too high"); // Max 10%
        platformFeePercent = newFeePercent;
        emit FeeUpdated(newFeePercent);
    }

    /**
     * @dev Actualiza el token de pago
     * @param newToken Direccion del nuevo token
     * @param decimals Decimales del token
     */
    function setPaymentToken(address newToken, uint8 decimals) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newToken != address(0), "Invalid token");
        paymentToken = IERC20(newToken);
        paymentTokenDecimals = decimals;
        emit PaymentTokenUpdated(newToken);
    }

    /**
     * @dev Actualiza los limites de inversion
     * @param minAmount Minimo
     * @param maxAmount Maximo
     */
    function setInvestmentLimits(
        uint256 minAmount,
        uint256 maxAmount
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(minAmount < maxAmount, "Invalid limits");
        minInvestmentAmount = minAmount;
        maxInvestmentAmount = maxAmount;
    }

    /**
     * @dev Actualiza el receptor de fees
     * @param newRecipient Nueva direccion
     */
    function setFeeRecipient(address newRecipient) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newRecipient != address(0), "Invalid recipient");
        feeRecipient = newRecipient;
    }

    /**
     * @dev Pausa el contrato
     */
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    /**
     * @dev Reanuda el contrato
     */
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    // ==================== VIEW FUNCTIONS ====================

    /**
     * @dev Obtiene informacion de un proyecto
     * @param projectId ID del proyecto
     */
    function getProject(bytes32 projectId) external view returns (
        address tokenContract,
        uint256 targetAmount,
        uint256 raisedAmount,
        uint256 startTime,
        uint256 endTime,
        bool fundingComplete,
        bool fundsReleased,
        ProjectStatus status
    ) {
        Project storage p = projects[projectId];
        return (
            p.tokenContract,
            p.targetAmount,
            p.raisedAmount,
            p.startTime,
            p.endTime,
            p.fundingComplete,
            p.fundsReleased,
            p.status
        );
    }

    /**
     * @dev Obtiene inversiones de un proyecto
     * @param projectId ID del proyecto
     */
    function getProjectInvestments(bytes32 projectId) external view returns (uint256[] memory) {
        return projectInvestments[projectId];
    }

    /**
     * @dev Obtiene inversiones de un inversor
     * @param investor Direccion del inversor
     */
    function getInvestorInvestments(address investor) external view returns (uint256[] memory) {
        return investorInvestments[investor];
    }

    /**
     * @dev Obtiene el balance total en escrow
     */
    function getEscrowBalance() external view returns (uint256) {
        return paymentToken.balanceOf(address(this));
    }
}
