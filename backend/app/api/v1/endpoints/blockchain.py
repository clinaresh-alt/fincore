"""
Endpoints de Blockchain y Tokenizacion.
Gestiona wallets, tokens, dividendos y transacciones on-chain.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.blockchain import (
    BlockchainNetwork,
    TransactionStatus,
    UserWallet,
    ProjectToken,
    TokenHolding,
    BlockchainTransaction,
    DividendDistribution,
    KYCBlockchainRecord,
)
from app.schemas.blockchain import (
    WalletCreate,
    WalletVerify,
    WalletResponse,
    WalletBalanceResponse,
    CustodialWalletCreate,
    TokenCreate,
    TokenResponse,
    TokenStatsResponse,
    TokenPurchase,
    TokenTransfer,
    TokenPurchaseResponse,
    TokenHoldingResponse,
    PortfolioTokenResponse,
    DividendCreate,
    DividendDistributionResponse,
    DividendCalculation,
    ClaimDividendsRequest,
    BlockchainTransactionResponse,
    KYCBlockchainCreate,
    KYCBlockchainResponse,
    NetworkInfoResponse,
    GasEstimateResponse,
    BlockchainNetworkEnum,
    TransactionStatusEnum,
    # Nuevos schemas para retiro/depósito
    WithdrawalRequest,
    WithdrawalResponse,
    WithdrawalFeeEstimate,
    DepositAddressResponse,
    DepositHistoryResponse,
    DepositHistoryItem,
    ConsolidatedBalanceResponse,
    WalletConsolidatedBalance,
    TokenBalance,
)
from app.models.security import WithdrawalWhitelist, WhitelistStatus, AccountFreeze
from app.models.audit import AuditLog, AuditAction
from app.core.security import verify_mfa_code
import hashlib
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64
import logging

logger = logging.getLogger(__name__)
from app.services.blockchain_service import (
    BlockchainService,
    get_blockchain_service,
    NETWORK_CONFIGS,
)
from app.services.tokenization_service import (
    TokenizationService,
    TokenizationConfig,
    DividendInfo,
)

router = APIRouter(prefix="/blockchain", tags=["Blockchain"])


# ==================== NETWORK ENDPOINTS ====================

@router.get("/networks", response_model=List[NetworkInfoResponse])
async def list_networks():
    """
    Lista todas las redes blockchain soportadas.
    Usa conexiones paralelas para reducir latencia.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    def get_network_info(network, config):
        """Obtiene info de una red con timeout rapido."""
        try:
            service = get_blockchain_service(network)
            is_connected = service.is_connected
            current_block = None
            if is_connected:
                try:
                    current_block = service.get_current_block()
                except Exception:
                    pass
            return {
                "network": network.value,
                "name": config.name,
                "chain_id": config.chain_id,
                "currency_symbol": config.currency_symbol,
                "block_explorer": config.block_explorer,
                "is_testnet": config.is_testnet,
                "is_connected": is_connected,
                "current_block": current_block
            }
        except Exception:
            return {
                "network": network.value,
                "name": config.name,
                "chain_id": config.chain_id,
                "currency_symbol": config.currency_symbol,
                "block_explorer": config.block_explorer,
                "is_testnet": config.is_testnet,
                "is_connected": False,
                "current_block": None
            }

    # Ejecutar en paralelo con timeout de 5 segundos por red
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=6) as executor:
        tasks = []
        for network, config in NETWORK_CONFIGS.items():
            task = loop.run_in_executor(executor, get_network_info, network, config)
            tasks.append(task)

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=10.0  # Timeout total de 10 segundos
            )
        except asyncio.TimeoutError:
            # Si timeout, devolver lo que tenemos
            results = []
            for network, config in NETWORK_CONFIGS.items():
                results.append({
                    "network": network.value,
                    "name": config.name,
                    "chain_id": config.chain_id,
                    "currency_symbol": config.currency_symbol,
                    "block_explorer": config.block_explorer,
                    "is_testnet": config.is_testnet,
                    "is_connected": False,
                    "current_block": None
                })

    # Convertir a response model
    networks = []
    for result in results:
        if isinstance(result, dict):
            networks.append(NetworkInfoResponse(**result))
        elif isinstance(result, Exception):
            # En caso de excepcion, agregar red como desconectada
            pass

    return networks


@router.get("/networks/{network}/status", response_model=NetworkInfoResponse)
async def get_network_status(network: BlockchainNetworkEnum):
    """
    Obtiene el estado de una red especifica.
    """
    try:
        net = BlockchainNetwork(network.value)
        config = NETWORK_CONFIGS[net]
        service = get_blockchain_service(net)

        current_block = None
        if service.is_connected:
            try:
                current_block = service.get_current_block()
            except Exception:
                pass

        return NetworkInfoResponse(
            network=net.value,
            name=config.name,
            chain_id=config.chain_id,
            currency_symbol=config.currency_symbol,
            block_explorer=config.block_explorer,
            is_testnet=config.is_testnet,
            is_connected=service.is_connected,
            current_block=current_block
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/gas-estimate", response_model=GasEstimateResponse)
async def estimate_gas(
    network: BlockchainNetworkEnum = BlockchainNetworkEnum.POLYGON,
    to_address: Optional[str] = None,
):
    """
    Estima el costo de gas para una transaccion.
    """
    service = get_blockchain_service(BlockchainNetwork(network.value))
    estimate = service.estimate_gas(to_address=to_address)

    return GasEstimateResponse(
        gas_limit=estimate.gas_limit,
        gas_price_gwei=estimate.gas_price_gwei,
        max_fee_gwei=estimate.max_fee_gwei,
        priority_fee_gwei=estimate.priority_fee_gwei,
        estimated_cost_native=estimate.estimated_cost_native,
        estimated_cost_usd=estimate.estimated_cost_usd
    )


# ==================== WALLET ENDPOINTS ====================

@router.post("/wallets", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
async def register_wallet(
    wallet_data: WalletCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registra una wallet para el usuario actual.
    """
    # Verificar que la wallet no existe
    existing = db.query(UserWallet).filter(
        UserWallet.address == wallet_data.address.lower()
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet already registered"
        )

    # Verificar si es la primera wallet del usuario
    user_wallets = db.query(UserWallet).filter(
        UserWallet.user_id == current_user.id
    ).count()

    wallet = UserWallet(
        user_id=current_user.id,
        address=wallet_data.address.lower(),
        wallet_type=wallet_data.wallet_type,
        label=wallet_data.label,
        preferred_network=BlockchainNetwork(wallet_data.preferred_network.value),
        is_primary=user_wallets == 0  # Primera wallet es primaria
    )

    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return wallet


@router.post("/wallets/custodial", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
async def create_custodial_wallet(
    wallet_data: CustodialWalletCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crea una wallet custodial para el usuario.
    FinCore genera y controla la llave privada (encriptada en DB).
    Ideal para usuarios que no quieren manejar sus propias llaves.
    """
    from app.services.encryption_service import encrypt_private_key

    # Generar nueva wallet
    service = get_blockchain_service(BlockchainNetwork(wallet_data.preferred_network.value))
    address, private_key = service.create_wallet()

    # Encriptar la llave privada
    encrypted_key = encrypt_private_key(private_key)

    # Verificar si es la primera wallet del usuario
    user_wallets = db.query(UserWallet).filter(
        UserWallet.user_id == current_user.id
    ).count()

    wallet = UserWallet(
        user_id=current_user.id,
        address=address.lower(),
        wallet_type="custodial",
        label=wallet_data.label or "Wallet Custodial FinCore",
        preferred_network=BlockchainNetwork(wallet_data.preferred_network.value),
        is_primary=user_wallets == 0,
        is_custodial=True,
        is_verified=True,  # Custodial wallets se verifican automaticamente
        verified_at=datetime.utcnow(),
        encrypted_private_key=encrypted_key
    )

    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return wallet


@router.post("/wallets/verify", response_model=WalletResponse)
async def verify_wallet_ownership(
    verify_data: WalletVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verifica que el usuario controla la wallet mediante firma.
    """
    wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.address == verify_data.address.lower(),
            UserWallet.user_id == current_user.id
        )
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    service = get_blockchain_service()
    is_valid = service.verify_wallet_signature(
        address=verify_data.address,
        message=verify_data.message,
        signature=verify_data.signature
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    wallet.is_verified = True
    wallet.verified_at = datetime.utcnow()
    wallet.verification_signature = verify_data.signature

    db.commit()
    db.refresh(wallet)

    return wallet


@router.get("/wallets", response_model=List[WalletResponse])
async def list_user_wallets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista las wallets del usuario actual.
    """
    wallets = db.query(UserWallet).filter(
        UserWallet.user_id == current_user.id
    ).all()

    return wallets


@router.get("/wallets/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene una wallet especifica.
    """
    wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.id == wallet_id,
            UserWallet.user_id == current_user.id
        )
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    return wallet


@router.get("/wallets/{wallet_id}/balance", response_model=WalletBalanceResponse)
async def get_wallet_balance(
    wallet_id: UUID,
    network: BlockchainNetworkEnum = BlockchainNetworkEnum.POLYGON,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene el balance de una wallet.
    """
    wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.id == wallet_id,
            UserWallet.user_id == current_user.id
        )
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    service = get_blockchain_service(BlockchainNetwork(network.value))
    balance = service.get_balance(wallet.address)

    # Obtener holdings de tokens
    holdings = db.query(TokenHolding).filter(
        TokenHolding.wallet_id == wallet.id
    ).all()

    tokens = []
    for holding in holdings:
        token = db.query(ProjectToken).get(holding.project_token_id)
        if token and holding.balance > 0:
            tokens.append({
                "symbol": token.token_symbol,
                "name": token.token_name,
                "balance": float(holding.balance),
                "value_usd": float(holding.balance * token.price_per_token)
            })

    return WalletBalanceResponse(
        address=wallet.address,
        native_balance=balance,
        network=network.value,
        tokens=tokens
    )


@router.delete("/wallets/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wallet(
    wallet_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Elimina una wallet del usuario.
    """
    wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.id == wallet_id,
            UserWallet.user_id == current_user.id
        )
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    # Verificar que no tiene tokens
    holdings = db.query(TokenHolding).filter(
        and_(
            TokenHolding.wallet_id == wallet.id,
            TokenHolding.balance > 0
        )
    ).count()

    if holdings > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete wallet with token holdings"
        )

    db.delete(wallet)
    db.commit()


# ==================== TOKEN ENDPOINTS ====================

@router.post("/tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_project_token(
    token_data: TokenCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ANALISTA])),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo token para un proyecto. Solo admin/gestor.
    """
    service = TokenizationService(db, BlockchainNetwork(token_data.network.value))

    try:
        config = TokenizationConfig(
            project_id=str(token_data.project_id),
            token_name=token_data.token_name,
            token_symbol=token_data.token_symbol,
            total_supply=token_data.total_supply,
            price_per_token=token_data.price_per_token,
            min_purchase=token_data.min_purchase,
            decimals=token_data.decimals,
            is_transferable=token_data.is_transferable,
            allows_fractional=token_data.allows_fractional,
            dividend_frequency=token_data.dividend_frequency,
            network=BlockchainNetwork(token_data.network.value)
        )

        token, _ = service.create_project_token(config)

        return token

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/tokens", response_model=List[TokenResponse])
async def list_tokens(
    network: Optional[BlockchainNetworkEnum] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Lista todos los tokens.
    """
    query = db.query(ProjectToken)

    if network:
        query = query.filter(ProjectToken.network == BlockchainNetwork(network.value))

    if is_active is not None:
        query = query.filter(ProjectToken.is_active == is_active)

    return query.all()


@router.get("/tokens/{token_id}", response_model=TokenResponse)
async def get_token(
    token_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Obtiene un token especifico.
    """
    token = db.query(ProjectToken).get(token_id)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )

    return token


@router.get("/tokens/{token_id}/stats", response_model=TokenStatsResponse)
async def get_token_stats(
    token_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Obtiene estadisticas de un token.
    """
    service = TokenizationService(db)

    try:
        stats = service.get_token_stats(str(token_id))
        return TokenStatsResponse(**stats)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/tokens/{token_id}/activate", response_model=TokenResponse)
async def activate_token(
    token_id: UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Activa un token para permitir compras. Solo admin.
    """
    service = TokenizationService(db)

    try:
        token = service.activate_token(str(token_id))
        return token
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/tokens/{token_id}/holders", response_model=List[TokenHoldingResponse])
async def get_token_holders(
    token_id: UUID,
    min_balance: Decimal = Decimal("0"),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ANALISTA])),
    db: Session = Depends(get_db)
):
    """
    Obtiene la lista de holders de un token. Solo admin/gestor.
    """
    service = TokenizationService(db)

    try:
        holders = service.get_token_holders(str(token_id), min_balance)
        return [TokenHoldingResponse(**h) for h in holders]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ==================== PURCHASE ENDPOINTS ====================

@router.post("/tokens/purchase", response_model=TokenPurchaseResponse)
async def purchase_tokens(
    purchase_data: TokenPurchase,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compra tokens de un proyecto.
    """
    # Verificar que la wallet pertenece al usuario
    wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.id == purchase_data.wallet_id,
            UserWallet.user_id == current_user.id
        )
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wallet does not belong to user"
        )

    service = TokenizationService(db)

    result = service.purchase_tokens(
        token_id=str(purchase_data.token_id),
        wallet_id=str(purchase_data.wallet_id),
        amount=purchase_data.amount,
        record_on_chain=purchase_data.record_on_chain
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return TokenPurchaseResponse(
        success=result.success,
        holding_id=UUID(result.holding_id) if result.holding_id else None,
        tokens_purchased=result.tokens_purchased,
        total_cost=result.total_cost,
        tx_hash=result.tx_hash,
        error=result.error
    )


@router.post("/tokens/transfer", response_model=TokenPurchaseResponse)
async def transfer_tokens(
    transfer_data: TokenTransfer,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transfiere tokens entre wallets.
    """
    # Verificar que la wallet origen pertenece al usuario
    from_wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.id == transfer_data.from_wallet_id,
            UserWallet.user_id == current_user.id
        )
    ).first()

    if not from_wallet:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Source wallet does not belong to user"
        )

    service = TokenizationService(db)

    result = service.transfer_tokens(
        from_wallet_id=str(transfer_data.from_wallet_id),
        to_wallet_id=str(transfer_data.to_wallet_id),
        token_id=str(transfer_data.token_id),
        amount=transfer_data.amount
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error
        )

    return TokenPurchaseResponse(
        success=result.success,
        holding_id=UUID(result.holding_id) if result.holding_id else None,
        tokens_purchased=result.tokens_purchased,
        total_cost=result.total_cost,
        tx_hash=result.tx_hash,
        error=result.error
    )


# ==================== PORTFOLIO ENDPOINTS ====================

@router.get("/portfolio", response_model=List[PortfolioTokenResponse])
async def get_token_portfolio(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene el portfolio de tokens del usuario actual.
    """
    service = TokenizationService(db)
    portfolio = service.get_holder_portfolio(str(current_user.id))

    return [PortfolioTokenResponse(**item) for item in portfolio]


# ==================== DIVIDEND ENDPOINTS ====================

@router.post("/dividends", response_model=DividendDistributionResponse, status_code=status.HTTP_201_CREATED)
async def create_dividend_distribution(
    dividend_data: DividendCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Crea una distribucion de dividendos. Solo admin.
    """
    service = TokenizationService(db)

    try:
        info = DividendInfo(
            project_token_id=str(dividend_data.project_token_id),
            total_amount=dividend_data.total_amount,
            period_start=dividend_data.period_start,
            period_end=dividend_data.period_end,
            description=dividend_data.description
        )

        distribution = service.distribute_dividends(
            info=info,
            record_on_chain=dividend_data.record_on_chain
        )

        return distribution

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/dividends/calculate/{token_id}", response_model=List[DividendCalculation])
async def calculate_dividends(
    token_id: UUID,
    total_amount: Decimal = Query(..., gt=0),
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Calcula la distribucion de dividendos sin ejecutarla. Solo admin.
    """
    service = TokenizationService(db)

    try:
        distribution = service.calculate_dividends(str(token_id), total_amount)
        return [DividendCalculation(**d) for d in distribution]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/dividends/claim", response_model=dict)
async def claim_dividends(
    claim_data: ClaimDividendsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reclama dividendos pendientes.
    """
    # Verificar que la wallet pertenece al usuario
    wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.id == claim_data.wallet_id,
            UserWallet.user_id == current_user.id
        )
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wallet does not belong to user"
        )

    service = TokenizationService(db)

    try:
        amount = service.claim_dividends(
            wallet_id=str(claim_data.wallet_id),
            token_id=str(claim_data.token_id)
        )

        return {
            "success": True,
            "amount_claimed": float(amount),
            "message": f"Successfully claimed {amount} in dividends"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/dividends/{token_id}/history", response_model=List[DividendDistributionResponse])
async def get_dividend_history(
    token_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Obtiene el historial de dividendos de un token.
    """
    distributions = db.query(DividendDistribution).filter(
        DividendDistribution.project_token_id == token_id
    ).order_by(DividendDistribution.created_at.desc()).all()

    return distributions


# ==================== TRANSACTION ENDPOINTS ====================

@router.get("/transactions", response_model=List[BlockchainTransactionResponse])
async def list_user_transactions(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[TransactionStatusEnum] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista las transacciones blockchain del usuario.
    """
    query = db.query(BlockchainTransaction).filter(
        BlockchainTransaction.user_id == current_user.id
    )

    if status_filter:
        query = query.filter(
            BlockchainTransaction.status == TransactionStatus(status_filter.value)
        )

    transactions = query.order_by(
        BlockchainTransaction.created_at.desc()
    ).offset(offset).limit(limit).all()

    return transactions


@router.get("/transactions/{tx_id}", response_model=BlockchainTransactionResponse)
async def get_transaction(
    tx_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene una transaccion especifica.
    """
    transaction = db.query(BlockchainTransaction).filter(
        and_(
            BlockchainTransaction.id == tx_id,
            BlockchainTransaction.user_id == current_user.id
        )
    ).first()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    return transaction


# ==================== KYC BLOCKCHAIN ENDPOINTS ====================

@router.post("/kyc/register", response_model=KYCBlockchainResponse, status_code=status.HTTP_201_CREATED)
async def register_kyc_on_chain(
    kyc_data: KYCBlockchainCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Registra verificacion KYC en blockchain. Solo admin.
    """
    # Verificar que no existe registro previo
    existing = db.query(KYCBlockchainRecord).filter(
        KYCBlockchainRecord.user_id == kyc_data.user_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="KYC record already exists for this user"
        )

    service = get_blockchain_service()

    # Generar hash KYC
    kyc_hash = service.compute_kyc_hash(
        user_id=str(kyc_data.user_id),
        document_type=kyc_data.document_type,
        verification_date=datetime.utcnow()
    )

    record = KYCBlockchainRecord(
        user_id=kyc_data.user_id,
        kyc_hash=kyc_hash,
        verification_level=kyc_data.verification_level,
        network=BlockchainNetwork.POLYGON,
        is_verified=True,
        verified_at=datetime.utcnow()
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@router.get("/kyc/{user_id}", response_model=KYCBlockchainResponse)
async def get_kyc_status(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene el estado KYC blockchain de un usuario.
    """
    # Solo admin puede ver KYC de otros usuarios
    if current_user.id != user_id and current_user.rol != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this KYC record"
        )

    record = db.query(KYCBlockchainRecord).filter(
        KYCBlockchainRecord.user_id == user_id
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC record not found"
        )

    return record


# ==================== WITHDRAWAL ENDPOINTS ====================

# Constantes para retiros
MFA_REQUIRED_THRESHOLD_USD = Decimal("100")  # MFA requerido para retiros > $100
PLATFORM_FEE_PERCENT = Decimal("0.001")  # 0.1% fee de plataforma
MIN_WITHDRAWAL = {
    "polygon": Decimal("1"),  # 1 MATIC mínimo
    "ethereum": Decimal("0.01"),  # 0.01 ETH mínimo
}


def _check_account_frozen(user_id: UUID, db: Session) -> bool:
    """Verifica si la cuenta está congelada."""
    freeze = db.query(AccountFreeze).filter(
        and_(
            AccountFreeze.user_id == user_id,
            AccountFreeze.is_active == True
        )
    ).first()
    return freeze is not None


def _verify_whitelist(user_id: UUID, address: str, db: Session) -> WithdrawalWhitelist:
    """Verifica que la dirección esté en whitelist y activa."""
    address_hash = hashlib.sha256(address.lower().encode()).hexdigest()

    whitelist_entry = db.query(WithdrawalWhitelist).filter(
        and_(
            WithdrawalWhitelist.user_id == user_id,
            WithdrawalWhitelist.address_hash == address_hash
        )
    ).first()

    if not whitelist_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dirección no está en tu whitelist. Agrégala primero en Configuración > Seguridad."
        )

    if whitelist_entry.status == WhitelistStatus.PENDING:
        hours_remaining = (whitelist_entry.quarantine_ends_at.replace(tzinfo=None) - datetime.utcnow()).total_seconds() / 3600
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dirección en cuarentena. Disponible en {max(0, hours_remaining):.1f} horas."
        )

    if whitelist_entry.status != WhitelistStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dirección no activa. Estado: {whitelist_entry.status.value}"
        )

    return whitelist_entry


@router.get("/withdraw/fee-estimate", response_model=WithdrawalFeeEstimate)
async def estimate_withdrawal_fee(
    amount: Decimal = Query(..., gt=0),
    network: BlockchainNetworkEnum = BlockchainNetworkEnum.POLYGON,
    token_address: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Estima los fees para un retiro.
    """
    service = get_blockchain_service(BlockchainNetwork(network.value))
    config = NETWORK_CONFIGS[BlockchainNetwork(network.value)]

    # Estimar gas
    gas_estimate = service.estimate_gas(to_address=token_address)

    # Fee de red (en token nativo)
    network_fee = gas_estimate.estimated_cost_native

    # Fee de plataforma (0.1% del monto)
    platform_fee = amount * PLATFORM_FEE_PERCENT

    # Total fee
    total_fee = network_fee + platform_fee
    net_amount = amount - total_fee

    return WithdrawalFeeEstimate(
        network_fee=network_fee,
        platform_fee=platform_fee,
        total_fee=total_fee,
        net_amount=max(Decimal("0"), net_amount),
        fee_currency=config.currency_symbol,
        estimated_usd=gas_estimate.estimated_cost_usd + (platform_fee * Decimal("1"))  # Simplificado
    )


@router.post("/withdraw", response_model=WithdrawalResponse)
async def withdraw_crypto(
    withdrawal: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retiro de crypto a dirección whitelisted.

    Validaciones:
    - Cuenta no congelada
    - Dirección en whitelist (cuarentena 24h pasada)
    - MFA requerido para retiros > $100 USD
    - Balance suficiente
    - Wallet custodial del usuario
    """
    # 1. Verificar cuenta no congelada
    if _check_account_frozen(current_user.id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta está congelada. Contacta a soporte para descongelarla."
        )

    # 2. Verificar wallet pertenece al usuario y es custodial
    wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.id == withdrawal.wallet_id,
            UserWallet.user_id == current_user.id
        )
    ).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet no encontrada"
        )

    if not wallet.is_custodial:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo puedes retirar desde wallets custodiales de FinCore"
        )

    # 3. Verificar whitelist
    whitelist_entry = _verify_whitelist(current_user.id, withdrawal.to_address, db)

    # 4. Verificar MFA si es necesario (retiros > $100 USD)
    # Simplificado: asumimos que 100 MATIC ≈ $100 USD
    if withdrawal.amount > MFA_REQUIRED_THRESHOLD_USD:
        if not current_user.mfa_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Habilita MFA para retiros mayores a $100 USD"
            )

        if not withdrawal.mfa_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Código MFA requerido para este monto"
            )

        if not verify_mfa_code(current_user.mfa_secret, withdrawal.mfa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Código MFA incorrecto"
            )

    # 5. Obtener servicio blockchain y verificar balance
    service = get_blockchain_service(BlockchainNetwork(withdrawal.network.value))
    config = NETWORK_CONFIGS[BlockchainNetwork(withdrawal.network.value)]

    current_balance = service.get_balance(wallet.address)
    if current_balance < withdrawal.amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Balance insuficiente. Tienes {current_balance} {config.currency_symbol}"
        )

    # 6. Calcular fees
    gas_estimate = service.estimate_gas(to_address=withdrawal.to_address)
    network_fee = gas_estimate.estimated_cost_native
    platform_fee = withdrawal.amount * PLATFORM_FEE_PERCENT
    total_fee = network_fee + platform_fee
    net_amount = withdrawal.amount - total_fee

    if net_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monto muy pequeño. Los fees exceden el monto a retirar."
        )

    # 7. Ejecutar transferencia
    try:
        from app.services.encryption_service import decrypt_private_key

        # Desencriptar llave privada
        private_key = decrypt_private_key(wallet.encrypted_private_key)

        # Enviar transacción
        tx_hash = service.send_native_token(
            from_address=wallet.address,
            to_address=withdrawal.to_address,
            amount=net_amount,
            private_key=private_key
        )

        # Registrar transacción en DB
        transaction = BlockchainTransaction(
            user_id=current_user.id,
            wallet_id=wallet.id,
            network=BlockchainNetwork(withdrawal.network.value),
            tx_type="withdrawal",
            tx_hash=tx_hash,
            from_address=wallet.address,
            to_address=withdrawal.to_address,
            value=net_amount,
            status=TransactionStatus.SUBMITTED,
            gas_price=Decimal(str(gas_estimate.gas_price_gwei)),
            description=f"Retiro de {net_amount} {config.currency_symbol}"
        )
        db.add(transaction)

        # Actualizar whitelist
        whitelist_entry.times_used += 1
        whitelist_entry.last_used_at = datetime.utcnow()
        whitelist_entry.total_withdrawn = str(
            Decimal(whitelist_entry.total_withdrawn or "0") + net_amount
        )

        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.WHITELIST_ADDRESS_USED,
            resource_type="withdrawal",
            resource_id=transaction.id,
            description=f"Retiro de {net_amount} {config.currency_symbol} a {withdrawal.to_address[:10]}..."
        )
        db.add(audit)

        db.commit()
        db.refresh(transaction)

        return WithdrawalResponse(
            success=True,
            transaction_id=transaction.id,
            tx_hash=tx_hash,
            status="submitted",
            amount=withdrawal.amount,
            fee=total_fee,
            net_amount=net_amount,
            to_address=withdrawal.to_address,
            estimated_confirmation_time="~30 segundos",
            message=f"Retiro enviado. TX: {tx_hash[:20]}..."
        )

    except Exception as e:
        logger.error(f"Error en retiro: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando retiro: {str(e)}"
        )


# ==================== DEPOSIT ENDPOINTS ====================

@router.get("/deposit/address", response_model=DepositAddressResponse)
async def get_deposit_address(
    network: BlockchainNetworkEnum = BlockchainNetworkEnum.POLYGON,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene la dirección de depósito del usuario.
    Si no tiene wallet custodial, crea una automáticamente.
    """
    net = BlockchainNetwork(network.value)
    config = NETWORK_CONFIGS[net]

    # Buscar wallet custodial existente
    wallet = db.query(UserWallet).filter(
        and_(
            UserWallet.user_id == current_user.id,
            UserWallet.is_custodial == True,
            UserWallet.preferred_network == net
        )
    ).first()

    # Si no existe, crear una
    if not wallet:
        from app.services.encryption_service import encrypt_private_key

        service = get_blockchain_service(net)
        address, private_key = service.create_wallet()
        encrypted_key = encrypt_private_key(private_key)

        wallet = UserWallet(
            user_id=current_user.id,
            address=address.lower(),
            wallet_type="custodial",
            label=f"Wallet de Depósito ({config.name})",
            preferred_network=net,
            is_primary=True,
            is_custodial=True,
            is_verified=True,
            verified_at=datetime.utcnow(),
            encrypted_private_key=encrypted_key
        )
        db.add(wallet)
        db.commit()
        db.refresh(wallet)

    # Generar QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(wallet.address)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Confirmaciones según red
    confirmations_map = {
        "polygon": 128,
        "ethereum": 12,
        "arbitrum": 64,
        "base": 64,
    }

    return DepositAddressResponse(
        address=wallet.address,
        network=network.value,
        currency_symbol=config.currency_symbol,
        qr_code_base64=qr_base64,
        minimum_deposit=MIN_WITHDRAWAL.get(network.value, Decimal("0.01")),
        confirmations_required=confirmations_map.get(network.value, 12),
        warning=f"Solo envía {config.currency_symbol} y tokens en la red {config.name}. Enviar otros activos puede resultar en pérdida de fondos."
    )


@router.get("/deposit/history", response_model=DepositHistoryResponse)
async def get_deposit_history(
    network: Optional[BlockchainNetworkEnum] = None,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene el historial de depósitos del usuario.
    """
    # Obtener wallets del usuario
    wallets_query = db.query(UserWallet).filter(
        UserWallet.user_id == current_user.id
    )

    if network:
        wallets_query = wallets_query.filter(
            UserWallet.preferred_network == BlockchainNetwork(network.value)
        )

    wallet_ids = [w.id for w in wallets_query.all()]

    if not wallet_ids:
        return DepositHistoryResponse(
            deposits=[],
            total=0,
            pending_count=0,
            total_deposited_usd=Decimal("0")
        )

    # Buscar transacciones de depósito (tx_type = 'deposit' o transacciones entrantes)
    query = db.query(BlockchainTransaction).filter(
        and_(
            BlockchainTransaction.wallet_id.in_(wallet_ids),
            BlockchainTransaction.tx_type == "deposit"
        )
    )

    total = query.count()
    pending_count = query.filter(
        BlockchainTransaction.status.in_([TransactionStatus.PENDING, TransactionStatus.SUBMITTED])
    ).count()

    transactions = query.order_by(
        BlockchainTransaction.created_at.desc()
    ).offset(offset).limit(limit).all()

    # Calcular total depositado (simplificado)
    total_deposited = sum(t.value for t in transactions if t.status == TransactionStatus.CONFIRMED)

    deposits = []
    for tx in transactions:
        config = NETWORK_CONFIGS.get(tx.network, NETWORK_CONFIGS[BlockchainNetwork.POLYGON])
        deposits.append(DepositHistoryItem(
            id=tx.id,
            tx_hash=tx.tx_hash or "",
            amount=tx.value,
            token_symbol=config.currency_symbol if not tx.token_address else "TOKEN",
            token_address=tx.token_address,
            network=tx.network.value,
            status=tx.status.value,
            confirmations=tx.confirmations,
            confirmations_required=12,
            from_address=tx.from_address,
            created_at=tx.created_at,
            confirmed_at=tx.confirmed_at
        ))

    return DepositHistoryResponse(
        deposits=deposits,
        total=total,
        pending_count=pending_count,
        total_deposited_usd=total_deposited  # Simplificado, debería convertir a USD
    )


# ==================== CONSOLIDATED BALANCE ENDPOINTS ====================

@router.get("/balances", response_model=ConsolidatedBalanceResponse)
async def get_consolidated_balances(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene los balances consolidados de todas las wallets del usuario.
    """
    wallets = db.query(UserWallet).filter(
        UserWallet.user_id == current_user.id
    ).all()

    wallet_balances = []
    all_tokens = []
    total_usd = Decimal("0")

    for wallet in wallets:
        try:
            net = wallet.preferred_network
            config = NETWORK_CONFIGS.get(net, NETWORK_CONFIGS[BlockchainNetwork.POLYGON])
            service = get_blockchain_service(net)

            # Balance nativo
            native_balance = service.get_balance(wallet.address)
            # Precio simplificado (en producción usar oracle o API de precios)
            native_price = Decimal("0.5") if "polygon" in net.value else Decimal("2000")
            native_usd = native_balance * native_price

            # Holdings de tokens del proyecto
            holdings = db.query(TokenHolding).filter(
                TokenHolding.wallet_id == wallet.id
            ).all()

            tokens = []
            wallet_total = native_usd

            # Token nativo
            native_token = TokenBalance(
                symbol=config.currency_symbol,
                name=config.name,
                contract_address=None,
                balance=native_balance,
                balance_usd=native_usd,
                price_usd=native_price,
                change_24h=None,
                logo_url=None
            )
            tokens.append(native_token)
            all_tokens.append(native_token)

            # Tokens de proyectos
            for holding in holdings:
                if holding.balance > 0:
                    token = db.query(ProjectToken).get(holding.project_token_id)
                    if token:
                        token_usd = holding.balance * token.price_per_token
                        wallet_total += token_usd

                        token_balance = TokenBalance(
                            symbol=token.token_symbol,
                            name=token.token_name,
                            contract_address=token.token_address,
                            balance=holding.balance,
                            balance_usd=token_usd,
                            price_usd=token.price_per_token,
                            change_24h=None,
                            logo_url=None
                        )
                        tokens.append(token_balance)
                        all_tokens.append(token_balance)

            total_usd += wallet_total

            wallet_balances.append(WalletConsolidatedBalance(
                wallet_id=wallet.id,
                wallet_address=wallet.address,
                wallet_label=wallet.label,
                is_custodial=wallet.is_custodial,
                network=net.value,
                native_balance=native_balance,
                native_balance_usd=native_usd,
                tokens=tokens,
                total_balance_usd=wallet_total
            ))

        except Exception as e:
            logger.warning(f"Error obteniendo balance de wallet {wallet.id}: {e}")
            continue

    # Top 5 assets por valor
    all_tokens.sort(key=lambda x: x.balance_usd, reverse=True)
    top_assets = all_tokens[:5]

    return ConsolidatedBalanceResponse(
        total_balance_usd=total_usd,
        change_24h_usd=None,
        change_24h_percent=None,
        wallets=wallet_balances,
        top_assets=top_assets,
        last_updated=datetime.utcnow()
    )
