"""
Servicio de Tokenizacion para FinCore.
Gestiona la creacion y manejo de tokens para proyectos de inversion.
"""
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
import hashlib
import json
import logging
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.blockchain import (
    BlockchainNetwork,
    TokenType,
    TransactionStatus,
    TransactionType,
    ProjectToken,
    TokenHolding,
    SmartContract,
    BlockchainTransaction,
    DividendDistribution,
    UserWallet,
)
from app.services.blockchain_service import (
    BlockchainService,
    get_blockchain_service,
    TransactionResult,
)

logger = logging.getLogger(__name__)


@dataclass
class TokenizationConfig:
    """Configuracion para tokenizacion de proyecto."""
    project_id: str
    token_name: str
    token_symbol: str
    total_supply: Decimal
    price_per_token: Decimal
    min_purchase: Decimal = Decimal("1")
    decimals: int = 18
    is_transferable: bool = True
    allows_fractional: bool = True
    dividend_frequency: Optional[str] = None  # monthly, quarterly, yearly
    network: BlockchainNetwork = BlockchainNetwork.POLYGON


@dataclass
class TokenPurchaseResult:
    """Resultado de una compra de tokens."""
    success: bool
    holding_id: Optional[str] = None
    tokens_purchased: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    tx_hash: Optional[str] = None
    error: Optional[str] = None


@dataclass
class DividendInfo:
    """Informacion de dividendos a distribuir."""
    project_token_id: str
    total_amount: Decimal
    period_start: datetime
    period_end: datetime
    description: str


class TokenizationService:
    """
    Servicio principal de tokenizacion.
    Gestiona el ciclo de vida completo de tokens de proyectos.
    """

    # ABIs minimos para interaccion con contratos
    PROJECT_TOKEN_ABI = [
        {
            "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
            "name": "mint",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "account", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "inputs": [{"name": "account", "type": "address"}, {"name": "approved", "type": "bool"}],
            "name": "setKYCStatus",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "enabled", "type": "bool"}],
            "name": "toggleTransfers",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [],
            "name": "getProjectInfo",
            "outputs": [
                {"name": "_projectId", "type": "bytes32"},
                {"name": "_valuation", "type": "uint256"},
                {"name": "_totalForSale", "type": "uint256"},
                {"name": "_sold", "type": "uint256"},
                {"name": "_price", "type": "uint256"},
                {"name": "_transfersEnabled", "type": "bool"}
            ],
            "stateMutability": "view",
            "type": "function"
        }
    ]

    def __init__(
        self,
        db: Session,
        network: BlockchainNetwork = BlockchainNetwork.POLYGON
    ):
        """
        Inicializa el servicio de tokenizacion.

        Args:
            db: Sesion de base de datos
            network: Red blockchain a usar
        """
        self.db = db
        self.blockchain = get_blockchain_service(network)
        self.network = network

    # ==================== TOKEN CREATION ====================

    def create_project_token(
        self,
        config: TokenizationConfig,
        deploy_contract: bool = False
    ) -> Tuple[ProjectToken, Optional[TransactionResult]]:
        """
        Crea un nuevo token para un proyecto.

        Args:
            config: Configuracion de tokenizacion
            deploy_contract: Si se debe desplegar el contrato on-chain

        Returns:
            Tupla (ProjectToken, TransactionResult opcional)
        """
        # Verificar que no existe un token para este proyecto
        existing = self.db.query(ProjectToken).filter(
            ProjectToken.project_id == uuid.UUID(config.project_id)
        ).first()

        if existing:
            raise ValueError(f"Project {config.project_id} already has a token")

        # Generar project ID hash para el contrato
        project_id_hash = "0x" + hashlib.sha256(
            config.project_id.encode()
        ).hexdigest()

        # Crear registro de token
        token = ProjectToken(
            project_id=uuid.UUID(config.project_id),
            token_symbol=config.token_symbol.upper(),
            token_name=config.token_name,
            token_type=TokenType.PROJECT,
            network=config.network,
            total_supply=config.total_supply,
            tokens_available=config.total_supply,
            tokens_sold=Decimal("0"),
            price_per_token=config.price_per_token,
            min_purchase=config.min_purchase,
            decimals=config.decimals,
            is_transferable=config.is_transferable,
            allows_fractional=config.allows_fractional,
            dividend_frequency=config.dividend_frequency,
            is_active=False  # Se activa cuando se despliega o manualmente
        )

        self.db.add(token)
        self.db.flush()

        tx_result = None

        if deploy_contract:
            # TODO: Implementar despliegue real del contrato
            # Por ahora solo registramos que se intentaria
            logger.info(f"Contract deployment requested for token {token.id}")

        self.db.commit()

        return (token, tx_result)

    def activate_token(self, token_id: str) -> ProjectToken:
        """
        Activa un token para permitir compras.

        Args:
            token_id: ID del token

        Returns:
            Token actualizado
        """
        token = self.db.query(ProjectToken).filter(
            ProjectToken.id == uuid.UUID(token_id)
        ).first()

        if not token:
            raise ValueError(f"Token {token_id} not found")

        token.is_active = True
        token.launched_at = datetime.utcnow()

        self.db.commit()

        return token

    # ==================== TOKEN PURCHASES ====================

    def purchase_tokens(
        self,
        token_id: str,
        wallet_id: str,
        amount: Decimal,
        record_on_chain: bool = False
    ) -> TokenPurchaseResult:
        """
        Procesa una compra de tokens.

        Args:
            token_id: ID del token a comprar
            wallet_id: ID de la wallet del comprador
            amount: Cantidad de tokens a comprar
            record_on_chain: Si se debe registrar on-chain

        Returns:
            Resultado de la compra
        """
        # Obtener token y wallet
        token = self.db.query(ProjectToken).filter(
            ProjectToken.id == uuid.UUID(token_id)
        ).first()

        if not token:
            return TokenPurchaseResult(
                success=False,
                error=f"Token {token_id} not found"
            )

        if not token.is_active:
            return TokenPurchaseResult(
                success=False,
                error="Token not active for purchases"
            )

        wallet = self.db.query(UserWallet).filter(
            UserWallet.id == uuid.UUID(wallet_id)
        ).first()

        if not wallet:
            return TokenPurchaseResult(
                success=False,
                error=f"Wallet {wallet_id} not found"
            )

        # Validaciones
        if amount < token.min_purchase:
            return TokenPurchaseResult(
                success=False,
                error=f"Minimum purchase is {token.min_purchase} tokens"
            )

        if amount > token.tokens_available:
            return TokenPurchaseResult(
                success=False,
                error=f"Only {token.tokens_available} tokens available"
            )

        # Calcular costo
        total_cost = amount * token.price_per_token

        # Buscar o crear holding
        holding = self.db.query(TokenHolding).filter(
            and_(
                TokenHolding.wallet_id == wallet.id,
                TokenHolding.project_token_id == token.id
            )
        ).first()

        if not holding:
            holding = TokenHolding(
                wallet_id=wallet.id,
                project_token_id=token.id,
                balance=Decimal("0"),
                average_cost_basis=token.price_per_token,
                total_invested=Decimal("0"),
                first_purchase_at=datetime.utcnow()
            )
            self.db.add(holding)

        # Actualizar costo promedio
        total_tokens = holding.balance + amount
        if total_tokens > 0:
            holding.average_cost_basis = (
                (holding.total_invested + total_cost) / total_tokens
            )

        # Actualizar balances
        holding.balance += amount
        holding.total_invested += total_cost
        holding.last_activity_at = datetime.utcnow()

        # Actualizar token
        token.tokens_sold += amount
        token.tokens_available -= amount

        self.db.flush()

        tx_hash = None

        # Registrar on-chain si se solicita
        if record_on_chain and token.token_address:
            tx_result = self.blockchain.mint_tokens(
                token_contract_address=token.token_address,
                token_abi=self.PROJECT_TOKEN_ABI,
                to_address=wallet.address,
                amount=amount,
                decimals=token.decimals
            )

            if tx_result.success:
                tx_hash = tx_result.tx_hash

                # Registrar transaccion
                blockchain_tx = BlockchainTransaction(
                    user_id=wallet.user_id,
                    project_token_id=token.id,
                    tx_type=TransactionType.TOKEN_MINT,
                    network=self.network,
                    tx_hash=tx_hash,
                    from_address=self.blockchain.operator_address or "0x0",
                    to_address=wallet.address,
                    token_amount=amount,
                    token_address=token.token_address,
                    status=TransactionStatus.CONFIRMED,
                    block_number=tx_result.block_number,
                    gas_used=tx_result.gas_used,
                    method_name="mint",
                    confirmed_at=datetime.utcnow()
                )
                self.db.add(blockchain_tx)

        self.db.commit()

        return TokenPurchaseResult(
            success=True,
            holding_id=str(holding.id),
            tokens_purchased=amount,
            total_cost=total_cost,
            tx_hash=tx_hash
        )

    def transfer_tokens(
        self,
        from_wallet_id: str,
        to_wallet_id: str,
        token_id: str,
        amount: Decimal
    ) -> TokenPurchaseResult:
        """
        Transfiere tokens entre wallets.

        Args:
            from_wallet_id: Wallet origen
            to_wallet_id: Wallet destino
            token_id: ID del token
            amount: Cantidad a transferir

        Returns:
            Resultado de la transferencia
        """
        # Obtener datos
        token = self.db.query(ProjectToken).get(uuid.UUID(token_id))
        if not token:
            return TokenPurchaseResult(success=False, error="Token not found")

        if not token.is_transferable:
            return TokenPurchaseResult(
                success=False,
                error="Token transfers are disabled"
            )

        from_wallet = self.db.query(UserWallet).get(uuid.UUID(from_wallet_id))
        to_wallet = self.db.query(UserWallet).get(uuid.UUID(to_wallet_id))

        if not from_wallet or not to_wallet:
            return TokenPurchaseResult(success=False, error="Wallet not found")

        # Obtener holding origen
        from_holding = self.db.query(TokenHolding).filter(
            and_(
                TokenHolding.wallet_id == from_wallet.id,
                TokenHolding.project_token_id == token.id
            )
        ).first()

        if not from_holding or from_holding.available_balance < amount:
            return TokenPurchaseResult(
                success=False,
                error="Insufficient balance"
            )

        # Obtener o crear holding destino
        to_holding = self.db.query(TokenHolding).filter(
            and_(
                TokenHolding.wallet_id == to_wallet.id,
                TokenHolding.project_token_id == token.id
            )
        ).first()

        if not to_holding:
            to_holding = TokenHolding(
                wallet_id=to_wallet.id,
                project_token_id=token.id,
                balance=Decimal("0"),
                average_cost_basis=from_holding.average_cost_basis,
                first_purchase_at=datetime.utcnow()
            )
            self.db.add(to_holding)

        # Actualizar balances
        from_holding.balance -= amount
        from_holding.last_activity_at = datetime.utcnow()

        to_holding.balance += amount
        to_holding.last_activity_at = datetime.utcnow()

        self.db.commit()

        return TokenPurchaseResult(
            success=True,
            holding_id=str(to_holding.id),
            tokens_purchased=amount
        )

    # ==================== DIVIDENDS ====================

    def calculate_dividends(
        self,
        token_id: str,
        total_amount: Decimal
    ) -> List[Dict[str, Any]]:
        """
        Calcula la distribucion de dividendos proporcional.

        Args:
            token_id: ID del token
            total_amount: Monto total a distribuir

        Returns:
            Lista de dividendos por holder
        """
        token = self.db.query(ProjectToken).get(uuid.UUID(token_id))
        if not token:
            raise ValueError(f"Token {token_id} not found")

        # Obtener todos los holdings con balance > 0
        holdings = self.db.query(TokenHolding).filter(
            and_(
                TokenHolding.project_token_id == token.id,
                TokenHolding.balance > 0
            )
        ).all()

        if not holdings:
            return []

        # Calcular total de tokens en circulacion
        total_tokens = sum(h.balance for h in holdings)

        if total_tokens == 0:
            return []

        # Calcular dividendo por token
        dividend_per_token = total_amount / total_tokens

        # Generar distribucion
        distribution = []
        for holding in holdings:
            dividend_amount = holding.balance * dividend_per_token

            # Obtener direccion de wallet
            wallet = self.db.query(UserWallet).get(holding.wallet_id)

            distribution.append({
                "wallet_id": str(holding.wallet_id),
                "wallet_address": wallet.address if wallet else None,
                "user_id": str(wallet.user_id) if wallet else None,
                "token_balance": float(holding.balance),
                "dividend_amount": float(dividend_amount),
                "percentage": float(holding.balance / total_tokens * 100)
            })

        return distribution

    def distribute_dividends(
        self,
        info: DividendInfo,
        record_on_chain: bool = False
    ) -> DividendDistribution:
        """
        Registra una distribucion de dividendos.

        Args:
            info: Informacion de dividendos
            record_on_chain: Si se debe registrar on-chain

        Returns:
            Registro de distribucion
        """
        token = self.db.query(ProjectToken).get(
            uuid.UUID(info.project_token_id)
        )

        if not token:
            raise ValueError(f"Token {info.project_token_id} not found")

        # Calcular distribucion
        distribution_list = self.calculate_dividends(
            info.project_token_id,
            info.total_amount
        )

        if not distribution_list:
            raise ValueError("No holders to distribute to")

        # Calcular dividendo por token
        total_tokens = sum(d["token_balance"] for d in distribution_list)
        amount_per_token = info.total_amount / Decimal(str(total_tokens))

        # Crear registro de distribucion
        distribution = DividendDistribution(
            project_token_id=token.id,
            period_start=info.period_start,
            period_end=info.period_end,
            total_amount=info.total_amount,
            amount_per_token=amount_per_token,
            description=info.description
        )

        self.db.add(distribution)

        # Actualizar dividendos no reclamados en holdings
        for holding_info in distribution_list:
            holding = self.db.query(TokenHolding).get(
                uuid.UUID(holding_info["wallet_id"])
            )
            if holding:
                holding.unclaimed_dividends += Decimal(
                    str(holding_info["dividend_amount"])
                )

        # Actualizar token
        token.total_dividends_paid += info.total_amount
        token.last_dividend_date = datetime.utcnow()

        # Registrar on-chain si se solicita
        if record_on_chain:
            # Calcular merkle root para distribucion
            leaves = [
                self.blockchain.compute_dividend_leaf(
                    d["wallet_address"],
                    Decimal(str(d["dividend_amount"]))
                )
                for d in distribution_list if d["wallet_address"]
            ]
            merkle_root = self.blockchain.compute_merkle_root(leaves)
            distribution.merkle_root = merkle_root

        self.db.commit()

        return distribution

    def claim_dividends(
        self,
        wallet_id: str,
        token_id: str
    ) -> Decimal:
        """
        Reclama dividendos pendientes.

        Args:
            wallet_id: ID de la wallet
            token_id: ID del token

        Returns:
            Monto reclamado
        """
        holding = self.db.query(TokenHolding).filter(
            and_(
                TokenHolding.wallet_id == uuid.UUID(wallet_id),
                TokenHolding.project_token_id == uuid.UUID(token_id)
            )
        ).first()

        if not holding:
            raise ValueError("No holding found")

        if holding.unclaimed_dividends <= 0:
            raise ValueError("No dividends to claim")

        amount = holding.unclaimed_dividends
        holding.unclaimed_dividends = Decimal("0")
        holding.total_dividends_received += amount
        holding.last_dividend_claim = datetime.utcnow()

        self.db.commit()

        return amount

    # ==================== QUERIES ====================

    def get_token_holders(
        self,
        token_id: str,
        min_balance: Decimal = Decimal("0")
    ) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de holders de un token.

        Args:
            token_id: ID del token
            min_balance: Balance minimo para incluir

        Returns:
            Lista de holders con sus balances
        """
        holdings = self.db.query(TokenHolding).filter(
            and_(
                TokenHolding.project_token_id == uuid.UUID(token_id),
                TokenHolding.balance >= min_balance
            )
        ).all()

        result = []
        for holding in holdings:
            wallet = self.db.query(UserWallet).get(holding.wallet_id)
            result.append({
                "wallet_id": str(holding.wallet_id),
                "wallet_address": wallet.address if wallet else None,
                "user_id": str(wallet.user_id) if wallet else None,
                "balance": float(holding.balance),
                "locked_balance": float(holding.locked_balance),
                "available_balance": float(holding.available_balance),
                "total_invested": float(holding.total_invested),
                "average_cost": float(holding.average_cost_basis or 0),
                "unclaimed_dividends": float(holding.unclaimed_dividends),
                "total_dividends": float(holding.total_dividends_received)
            })

        return result

    def get_holder_portfolio(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el portfolio de tokens de un usuario.

        Args:
            user_id: ID del usuario

        Returns:
            Lista de tokens y sus balances
        """
        # Obtener wallets del usuario
        wallets = self.db.query(UserWallet).filter(
            UserWallet.user_id == uuid.UUID(user_id)
        ).all()

        if not wallets:
            return []

        wallet_ids = [w.id for w in wallets]

        # Obtener holdings de todas las wallets
        holdings = self.db.query(TokenHolding).filter(
            TokenHolding.wallet_id.in_(wallet_ids)
        ).all()

        result = []
        for holding in holdings:
            token = self.db.query(ProjectToken).get(holding.project_token_id)
            if token:
                current_value = holding.balance * token.price_per_token

                result.append({
                    "token_id": str(token.id),
                    "token_symbol": token.token_symbol,
                    "token_name": token.token_name,
                    "project_id": str(token.project_id),
                    "balance": float(holding.balance),
                    "available_balance": float(holding.available_balance),
                    "average_cost": float(holding.average_cost_basis or 0),
                    "current_price": float(token.price_per_token),
                    "total_invested": float(holding.total_invested),
                    "current_value": float(current_value),
                    "unrealized_pnl": float(holding.unrealized_pnl),
                    "unclaimed_dividends": float(holding.unclaimed_dividends),
                    "total_dividends": float(holding.total_dividends_received)
                })

        return result

    def get_token_stats(self, token_id: str) -> Dict[str, Any]:
        """
        Obtiene estadisticas de un token.

        Args:
            token_id: ID del token

        Returns:
            Estadisticas del token
        """
        token = self.db.query(ProjectToken).get(uuid.UUID(token_id))
        if not token:
            raise ValueError(f"Token {token_id} not found")

        # Contar holders
        holders_count = self.db.query(TokenHolding).filter(
            and_(
                TokenHolding.project_token_id == token.id,
                TokenHolding.balance > 0
            )
        ).count()

        # Calcular market cap
        market_cap = token.tokens_sold * token.price_per_token

        return {
            "token_id": str(token.id),
            "token_symbol": token.token_symbol,
            "token_name": token.token_name,
            "network": token.network.value,
            "total_supply": float(token.total_supply),
            "tokens_sold": float(token.tokens_sold),
            "tokens_available": float(token.tokens_available),
            "price_per_token": float(token.price_per_token),
            "market_cap": float(market_cap),
            "holders_count": holders_count,
            "percentage_sold": token.percentage_sold,
            "is_active": token.is_active,
            "launched_at": token.launched_at.isoformat() if token.launched_at else None,
            "total_dividends_paid": float(token.total_dividends_paid),
            "last_dividend_date": token.last_dividend_date.isoformat() if token.last_dividend_date else None
        }
