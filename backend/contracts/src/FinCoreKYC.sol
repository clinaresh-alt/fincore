// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

/**
 * @title FinCoreKYC
 * @dev Contrato de verificacion KYC on-chain.
 * Almacena hashes de verificacion KYC sin datos personales.
 * Permite verificar que un usuario ha pasado KYC sin exponer informacion sensible.
 */
contract FinCoreKYC is AccessControl, Pausable {
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant REVOKER_ROLE = keccak256("REVOKER_ROLE");

    // Niveles de verificacion KYC
    enum KYCLevel {
        None,       // Sin verificacion
        Basic,      // Email + telefono verificado
        Standard,   // Documento de identidad verificado
        Enhanced    // Verificacion completa con prueba de direccion
    }

    // Registro KYC
    struct KYCRecord {
        bytes32 kycHash;           // Hash de los datos KYC
        KYCLevel level;            // Nivel de verificacion
        uint256 verifiedAt;        // Timestamp de verificacion
        uint256 expiresAt;         // Timestamp de expiracion
        address verifier;          // Quien verifico
        bool revoked;              // Si fue revocado
        string revokeReason;       // Razon de revocacion
    }

    // Almacenamiento
    mapping(address => KYCRecord) public kycRecords;
    mapping(bytes32 => address) public hashToAddress;  // Para buscar por hash

    // Configuracion
    uint256 public defaultValidityPeriod;  // Periodo de validez en segundos
    mapping(KYCLevel => uint256) public levelValidityPeriods;

    // Contadores
    uint256 public totalVerified;
    uint256 public totalRevoked;

    // Eventos
    event KYCVerified(
        address indexed account,
        bytes32 indexed kycHash,
        KYCLevel level,
        address verifier,
        uint256 expiresAt
    );
    event KYCRevoked(
        address indexed account,
        bytes32 indexed kycHash,
        address revoker,
        string reason
    );
    event KYCRenewed(
        address indexed account,
        bytes32 indexed kycHash,
        uint256 newExpiresAt
    );
    event KYCLevelUpgraded(
        address indexed account,
        KYCLevel oldLevel,
        KYCLevel newLevel
    );
    event ValidityPeriodUpdated(KYCLevel level, uint256 period);

    /**
     * @dev Constructor
     * @param admin Administrador del contrato
     * @param _defaultValidityPeriod Periodo de validez por defecto en dias
     */
    constructor(address admin, uint256 _defaultValidityPeriod) {
        require(admin != address(0), "Invalid admin");
        require(_defaultValidityPeriod > 0, "Invalid validity period");

        defaultValidityPeriod = _defaultValidityPeriod * 1 days;

        // Periodos por defecto por nivel
        levelValidityPeriods[KYCLevel.Basic] = 90 days;
        levelValidityPeriods[KYCLevel.Standard] = 365 days;
        levelValidityPeriods[KYCLevel.Enhanced] = 730 days; // 2 anios

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(VERIFIER_ROLE, admin);
        _grantRole(REVOKER_ROLE, admin);
    }

    // ==================== VERIFICATION FUNCTIONS ====================

    /**
     * @dev Registra una verificacion KYC
     * @param account Direccion del usuario
     * @param kycHash Hash de los datos KYC
     * @param level Nivel de verificacion
     */
    function verifyKYC(
        address account,
        bytes32 kycHash,
        KYCLevel level
    ) external onlyRole(VERIFIER_ROLE) whenNotPaused {
        require(account != address(0), "Invalid account");
        require(kycHash != bytes32(0), "Invalid KYC hash");
        require(level != KYCLevel.None, "Invalid level");
        require(hashToAddress[kycHash] == address(0), "Hash already used");

        // Verificar si ya tiene un registro anterior
        KYCRecord storage existingRecord = kycRecords[account];
        if (existingRecord.kycHash != bytes32(0) && !existingRecord.revoked) {
            // Limpiar hash anterior
            delete hashToAddress[existingRecord.kycHash];
        }

        // Calcular expiracion
        uint256 validity = levelValidityPeriods[level];
        if (validity == 0) {
            validity = defaultValidityPeriod;
        }
        uint256 expiresAt = block.timestamp + validity;

        // Crear registro
        kycRecords[account] = KYCRecord({
            kycHash: kycHash,
            level: level,
            verifiedAt: block.timestamp,
            expiresAt: expiresAt,
            verifier: msg.sender,
            revoked: false,
            revokeReason: ""
        });

        hashToAddress[kycHash] = account;
        totalVerified++;

        emit KYCVerified(account, kycHash, level, msg.sender, expiresAt);
    }

    /**
     * @dev Registra multiples verificaciones KYC en batch
     * @param accounts Lista de direcciones
     * @param kycHashes Lista de hashes
     * @param levels Lista de niveles
     */
    function batchVerifyKYC(
        address[] calldata accounts,
        bytes32[] calldata kycHashes,
        KYCLevel[] calldata levels
    ) external onlyRole(VERIFIER_ROLE) whenNotPaused {
        require(
            accounts.length == kycHashes.length && kycHashes.length == levels.length,
            "Length mismatch"
        );

        for (uint256 i = 0; i < accounts.length; i++) {
            address account = accounts[i];
            bytes32 kycHash = kycHashes[i];
            KYCLevel level = levels[i];

            if (account == address(0) || kycHash == bytes32(0) || level == KYCLevel.None) {
                continue;
            }

            if (hashToAddress[kycHash] != address(0)) {
                continue;
            }

            // Limpiar registro anterior si existe
            KYCRecord storage existingRecord = kycRecords[account];
            if (existingRecord.kycHash != bytes32(0) && !existingRecord.revoked) {
                delete hashToAddress[existingRecord.kycHash];
            }

            uint256 validity = levelValidityPeriods[level];
            if (validity == 0) {
                validity = defaultValidityPeriod;
            }
            uint256 expiresAt = block.timestamp + validity;

            kycRecords[account] = KYCRecord({
                kycHash: kycHash,
                level: level,
                verifiedAt: block.timestamp,
                expiresAt: expiresAt,
                verifier: msg.sender,
                revoked: false,
                revokeReason: ""
            });

            hashToAddress[kycHash] = account;
            totalVerified++;

            emit KYCVerified(account, kycHash, level, msg.sender, expiresAt);
        }
    }

    /**
     * @dev Revoca una verificacion KYC
     * @param account Direccion del usuario
     * @param reason Razon de la revocacion
     */
    function revokeKYC(
        address account,
        string calldata reason
    ) external onlyRole(REVOKER_ROLE) {
        KYCRecord storage record = kycRecords[account];
        require(record.kycHash != bytes32(0), "No KYC record");
        require(!record.revoked, "Already revoked");

        record.revoked = true;
        record.revokeReason = reason;
        totalRevoked++;

        emit KYCRevoked(account, record.kycHash, msg.sender, reason);
    }

    /**
     * @dev Renueva una verificacion KYC existente
     * @param account Direccion del usuario
     * @param additionalTime Tiempo adicional en segundos
     */
    function renewKYC(
        address account,
        uint256 additionalTime
    ) external onlyRole(VERIFIER_ROLE) whenNotPaused {
        KYCRecord storage record = kycRecords[account];
        require(record.kycHash != bytes32(0), "No KYC record");
        require(!record.revoked, "KYC revoked");

        // Extender desde ahora o desde la expiracion actual, lo que sea mayor
        uint256 baseTime = record.expiresAt > block.timestamp
            ? record.expiresAt
            : block.timestamp;

        record.expiresAt = baseTime + additionalTime;

        emit KYCRenewed(account, record.kycHash, record.expiresAt);
    }

    /**
     * @dev Actualiza el nivel de KYC de un usuario
     * @param account Direccion del usuario
     * @param newLevel Nuevo nivel
     */
    function upgradeKYCLevel(
        address account,
        KYCLevel newLevel
    ) external onlyRole(VERIFIER_ROLE) whenNotPaused {
        KYCRecord storage record = kycRecords[account];
        require(record.kycHash != bytes32(0), "No KYC record");
        require(!record.revoked, "KYC revoked");
        require(newLevel > record.level, "Can only upgrade");

        KYCLevel oldLevel = record.level;
        record.level = newLevel;

        // Extender validez segun nuevo nivel
        uint256 validity = levelValidityPeriods[newLevel];
        if (validity == 0) {
            validity = defaultValidityPeriod;
        }
        record.expiresAt = block.timestamp + validity;

        emit KYCLevelUpgraded(account, oldLevel, newLevel);
    }

    // ==================== VIEW FUNCTIONS ====================

    /**
     * @dev Verifica si una cuenta tiene KYC valido
     * @param account Direccion a verificar
     */
    function isKYCValid(address account) external view returns (bool) {
        KYCRecord storage record = kycRecords[account];
        return record.kycHash != bytes32(0) &&
               !record.revoked &&
               record.expiresAt > block.timestamp;
    }

    /**
     * @dev Verifica si una cuenta tiene un nivel minimo de KYC
     * @param account Direccion a verificar
     * @param minLevel Nivel minimo requerido
     */
    function hasMinimumKYCLevel(
        address account,
        KYCLevel minLevel
    ) external view returns (bool) {
        KYCRecord storage record = kycRecords[account];
        return record.kycHash != bytes32(0) &&
               !record.revoked &&
               record.expiresAt > block.timestamp &&
               record.level >= minLevel;
    }

    /**
     * @dev Obtiene el registro KYC completo de una cuenta
     * @param account Direccion a consultar
     */
    function getKYCRecord(address account) external view returns (
        bytes32 kycHash,
        KYCLevel level,
        uint256 verifiedAt,
        uint256 expiresAt,
        address verifier,
        bool revoked,
        string memory revokeReason
    ) {
        KYCRecord storage record = kycRecords[account];
        return (
            record.kycHash,
            record.level,
            record.verifiedAt,
            record.expiresAt,
            record.verifier,
            record.revoked,
            record.revokeReason
        );
    }

    /**
     * @dev Verifica si un hash KYC especifico es valido para una cuenta
     * @param account Direccion del usuario
     * @param kycHash Hash a verificar
     */
    function verifyKYCHash(
        address account,
        bytes32 kycHash
    ) external view returns (bool) {
        KYCRecord storage record = kycRecords[account];
        return record.kycHash == kycHash &&
               !record.revoked &&
               record.expiresAt > block.timestamp;
    }

    /**
     * @dev Obtiene la direccion asociada a un hash KYC
     * @param kycHash Hash a buscar
     */
    function getAddressForHash(bytes32 kycHash) external view returns (address) {
        return hashToAddress[kycHash];
    }

    /**
     * @dev Obtiene estadisticas generales
     */
    function getStats() external view returns (
        uint256 _totalVerified,
        uint256 _totalRevoked,
        uint256 _activeCount
    ) {
        return (totalVerified, totalRevoked, totalVerified - totalRevoked);
    }

    // ==================== ADMIN FUNCTIONS ====================

    /**
     * @dev Actualiza el periodo de validez para un nivel
     * @param level Nivel de KYC
     * @param period Periodo en segundos
     */
    function setValidityPeriod(
        KYCLevel level,
        uint256 period
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(level != KYCLevel.None, "Invalid level");
        require(period > 0, "Invalid period");
        levelValidityPeriods[level] = period;
        emit ValidityPeriodUpdated(level, period);
    }

    /**
     * @dev Actualiza el periodo de validez por defecto
     * @param period Periodo en dias
     */
    function setDefaultValidityPeriod(uint256 period) external onlyRole(DEFAULT_ADMIN_ROLE) {
        require(period > 0, "Invalid period");
        defaultValidityPeriod = period * 1 days;
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
}
