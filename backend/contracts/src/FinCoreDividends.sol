// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";

/**
 * @title FinCoreDividends
 * @dev Contrato de distribucion de dividendos usando Merkle Trees.
 * Permite distribuciones eficientes a miles de holders con una sola transaccion.
 */
contract FinCoreDividends is AccessControl, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    bytes32 public constant DISTRIBUTOR_ROLE = keccak256("DISTRIBUTOR_ROLE");

    // Token de pago (USDC)
    IERC20 public paymentToken;

    // Estructura de distribucion
    struct Distribution {
        bytes32 projectId;
        bytes32 merkleRoot;
        uint256 totalAmount;
        uint256 claimedAmount;
        uint256 periodStart;
        uint256 periodEnd;
        uint256 createdAt;
        uint256 expiresAt;
        bool active;
        string description;
    }

    // Almacenamiento
    mapping(uint256 => Distribution) public distributions;
    mapping(uint256 => mapping(address => bool)) public hasClaimed;
    mapping(bytes32 => uint256[]) public projectDistributions;

    uint256 public nextDistributionId;
    uint256 public claimExpirationPeriod;  // Periodo para reclamar despues de distribucion

    // Contadores
    uint256 public totalDistributed;
    uint256 public totalClaimed;

    // Eventos
    event DistributionCreated(
        uint256 indexed distributionId,
        bytes32 indexed projectId,
        bytes32 merkleRoot,
        uint256 totalAmount,
        uint256 expiresAt
    );
    event DividendClaimed(
        uint256 indexed distributionId,
        address indexed account,
        uint256 amount
    );
    event DistributionCancelled(uint256 indexed distributionId);
    event UnclaimedFundsRecovered(uint256 indexed distributionId, uint256 amount);
    event ExpirationPeriodUpdated(uint256 newPeriod);

    /**
     * @dev Constructor
     * @param _paymentToken Token de pago (USDC)
     * @param _claimExpirationDays Dias para reclamar dividendos
     * @param admin Administrador
     */
    constructor(
        address _paymentToken,
        uint256 _claimExpirationDays,
        address admin
    ) {
        require(_paymentToken != address(0), "Invalid payment token");
        require(admin != address(0), "Invalid admin");

        paymentToken = IERC20(_paymentToken);
        claimExpirationPeriod = _claimExpirationDays * 1 days;

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(DISTRIBUTOR_ROLE, admin);
    }

    // ==================== DISTRIBUTION FUNCTIONS ====================

    /**
     * @dev Crea una nueva distribucion de dividendos
     * @param projectId ID del proyecto
     * @param merkleRoot Raiz del Merkle tree con los reclamos
     * @param totalAmount Monto total a distribuir
     * @param periodStart Inicio del periodo de dividendos
     * @param periodEnd Fin del periodo de dividendos
     * @param description Descripcion de la distribucion
     */
    function createDistribution(
        bytes32 projectId,
        bytes32 merkleRoot,
        uint256 totalAmount,
        uint256 periodStart,
        uint256 periodEnd,
        string calldata description
    ) external onlyRole(DISTRIBUTOR_ROLE) whenNotPaused returns (uint256) {
        require(merkleRoot != bytes32(0), "Invalid merkle root");
        require(totalAmount > 0, "Invalid amount");
        require(periodStart < periodEnd, "Invalid period");

        // Transferir fondos al contrato
        paymentToken.safeTransferFrom(msg.sender, address(this), totalAmount);

        uint256 distributionId = nextDistributionId++;
        uint256 expiresAt = block.timestamp + claimExpirationPeriod;

        distributions[distributionId] = Distribution({
            projectId: projectId,
            merkleRoot: merkleRoot,
            totalAmount: totalAmount,
            claimedAmount: 0,
            periodStart: periodStart,
            periodEnd: periodEnd,
            createdAt: block.timestamp,
            expiresAt: expiresAt,
            active: true,
            description: description
        });

        projectDistributions[projectId].push(distributionId);
        totalDistributed += totalAmount;

        emit DistributionCreated(
            distributionId,
            projectId,
            merkleRoot,
            totalAmount,
            expiresAt
        );

        return distributionId;
    }

    /**
     * @dev Reclama dividendos usando una prueba Merkle
     * @param distributionId ID de la distribucion
     * @param amount Monto a reclamar
     * @param merkleProof Prueba Merkle
     */
    function claimDividend(
        uint256 distributionId,
        uint256 amount,
        bytes32[] calldata merkleProof
    ) external nonReentrant whenNotPaused {
        Distribution storage dist = distributions[distributionId];

        require(dist.active, "Distribution not active");
        require(block.timestamp <= dist.expiresAt, "Distribution expired");
        require(!hasClaimed[distributionId][msg.sender], "Already claimed");
        require(amount > 0, "Invalid amount");

        // Verificar prueba Merkle
        bytes32 leaf = keccak256(
            bytes.concat(keccak256(abi.encode(msg.sender, amount)))
        );
        require(
            MerkleProof.verify(merkleProof, dist.merkleRoot, leaf),
            "Invalid proof"
        );

        // Marcar como reclamado
        hasClaimed[distributionId][msg.sender] = true;
        dist.claimedAmount += amount;
        totalClaimed += amount;

        // Transferir dividendo
        paymentToken.safeTransfer(msg.sender, amount);

        emit DividendClaimed(distributionId, msg.sender, amount);
    }

    /**
     * @dev Reclama multiples dividendos en una transaccion
     * @param distributionIds IDs de las distribuciones
     * @param amounts Montos a reclamar
     * @param merkleProofs Pruebas Merkle (array de arrays)
     */
    function batchClaimDividends(
        uint256[] calldata distributionIds,
        uint256[] calldata amounts,
        bytes32[][] calldata merkleProofs
    ) external nonReentrant whenNotPaused {
        require(
            distributionIds.length == amounts.length &&
            amounts.length == merkleProofs.length,
            "Length mismatch"
        );

        uint256 totalToClaim = 0;

        for (uint256 i = 0; i < distributionIds.length; i++) {
            uint256 distId = distributionIds[i];
            uint256 amount = amounts[i];
            bytes32[] calldata proof = merkleProofs[i];

            Distribution storage dist = distributions[distId];

            if (!dist.active || block.timestamp > dist.expiresAt) {
                continue;
            }

            if (hasClaimed[distId][msg.sender] || amount == 0) {
                continue;
            }

            // Verificar prueba
            bytes32 leaf = keccak256(
                bytes.concat(keccak256(abi.encode(msg.sender, amount)))
            );

            if (!MerkleProof.verify(proof, dist.merkleRoot, leaf)) {
                continue;
            }

            hasClaimed[distId][msg.sender] = true;
            dist.claimedAmount += amount;
            totalClaimed += amount;
            totalToClaim += amount;

            emit DividendClaimed(distId, msg.sender, amount);
        }

        if (totalToClaim > 0) {
            paymentToken.safeTransfer(msg.sender, totalToClaim);
        }
    }

    // ==================== ADMIN FUNCTIONS ====================

    /**
     * @dev Cancela una distribucion activa
     * @param distributionId ID de la distribucion
     */
    function cancelDistribution(
        uint256 distributionId
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        Distribution storage dist = distributions[distributionId];
        require(dist.active, "Not active");

        dist.active = false;

        // Devolver fondos no reclamados
        uint256 unclaimed = dist.totalAmount - dist.claimedAmount;
        if (unclaimed > 0) {
            paymentToken.safeTransfer(msg.sender, unclaimed);
        }

        emit DistributionCancelled(distributionId);
    }

    /**
     * @dev Recupera fondos no reclamados de distribuciones expiradas
     * @param distributionIds IDs de las distribuciones
     */
    function recoverUnclaimedFunds(
        uint256[] calldata distributionIds
    ) external onlyRole(DEFAULT_ADMIN_ROLE) nonReentrant {
        uint256 totalRecovered = 0;

        for (uint256 i = 0; i < distributionIds.length; i++) {
            Distribution storage dist = distributions[distributionIds[i]];

            if (!dist.active || block.timestamp <= dist.expiresAt) {
                continue;
            }

            uint256 unclaimed = dist.totalAmount - dist.claimedAmount;
            if (unclaimed > 0) {
                dist.active = false;
                totalRecovered += unclaimed;
                emit UnclaimedFundsRecovered(distributionIds[i], unclaimed);
            }
        }

        if (totalRecovered > 0) {
            paymentToken.safeTransfer(msg.sender, totalRecovered);
        }
    }

    /**
     * @dev Actualiza el periodo de expiracion para nuevas distribuciones
     * @param newPeriodDays Nuevo periodo en dias
     */
    function setClaimExpirationPeriod(
        uint256 newPeriodDays
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(newPeriodDays > 0, "Invalid period");
        claimExpirationPeriod = newPeriodDays * 1 days;
        emit ExpirationPeriodUpdated(claimExpirationPeriod);
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
     * @dev Obtiene informacion de una distribucion
     * @param distributionId ID de la distribucion
     */
    function getDistribution(uint256 distributionId) external view returns (
        bytes32 projectId,
        bytes32 merkleRoot,
        uint256 totalAmount,
        uint256 claimedAmount,
        uint256 periodStart,
        uint256 periodEnd,
        uint256 createdAt,
        uint256 expiresAt,
        bool active
    ) {
        Distribution storage dist = distributions[distributionId];
        return (
            dist.projectId,
            dist.merkleRoot,
            dist.totalAmount,
            dist.claimedAmount,
            dist.periodStart,
            dist.periodEnd,
            dist.createdAt,
            dist.expiresAt,
            dist.active
        );
    }

    /**
     * @dev Verifica si una cuenta puede reclamar dividendos
     * @param distributionId ID de la distribucion
     * @param account Direccion a verificar
     * @param amount Monto esperado
     * @param merkleProof Prueba Merkle
     */
    function canClaim(
        uint256 distributionId,
        address account,
        uint256 amount,
        bytes32[] calldata merkleProof
    ) external view returns (bool) {
        Distribution storage dist = distributions[distributionId];

        if (!dist.active || block.timestamp > dist.expiresAt) {
            return false;
        }

        if (hasClaimed[distributionId][account]) {
            return false;
        }

        bytes32 leaf = keccak256(
            bytes.concat(keccak256(abi.encode(account, amount)))
        );

        return MerkleProof.verify(merkleProof, dist.merkleRoot, leaf);
    }

    /**
     * @dev Obtiene las distribuciones de un proyecto
     * @param projectId ID del proyecto
     */
    function getProjectDistributions(
        bytes32 projectId
    ) external view returns (uint256[] memory) {
        return projectDistributions[projectId];
    }

    /**
     * @dev Obtiene el monto pendiente de una distribucion
     * @param distributionId ID de la distribucion
     */
    function getUnclaimedAmount(uint256 distributionId) external view returns (uint256) {
        Distribution storage dist = distributions[distributionId];
        return dist.totalAmount - dist.claimedAmount;
    }

    /**
     * @dev Obtiene estadisticas generales
     */
    function getStats() external view returns (
        uint256 _totalDistributed,
        uint256 _totalClaimed,
        uint256 _totalPending,
        uint256 _distributionCount
    ) {
        return (
            totalDistributed,
            totalClaimed,
            totalDistributed - totalClaimed,
            nextDistributionId
        );
    }

    /**
     * @dev Obtiene el balance total en el contrato
     */
    function getContractBalance() external view returns (uint256) {
        return paymentToken.balanceOf(address(this));
    }
}
