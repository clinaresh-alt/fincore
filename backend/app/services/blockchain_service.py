"""
Servicio Blockchain para FinCore.
Gestiona conexiones Web3, contratos inteligentes, tokens y transacciones.
Soporta Polygon (produccion) y testnets para desarrollo.
"""
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
import hashlib
import json
import os
import logging

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from web3.exceptions import ContractLogicError, TransactionNotFound
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_typing import ChecksumAddress

from sqlalchemy.orm import Session
from app.models.blockchain import (
    BlockchainNetwork,
    TransactionStatus,
    TransactionType,
    UserWallet,
    SmartContract,
    ProjectToken,
    TokenHolding,
    BlockchainTransaction,
    DividendDistribution,
    KYCBlockchainRecord,
)

logger = logging.getLogger(__name__)


@dataclass
class NetworkConfig:
    """Configuracion de red blockchain."""
    rpc_url: str
    chain_id: int
    name: str
    currency_symbol: str
    block_explorer: str
    is_testnet: bool = False


@dataclass
class TransactionResult:
    """Resultado de una transaccion blockchain."""
    success: bool
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    error: Optional[str] = None
    logs: Optional[List[Dict]] = None


@dataclass
class GasEstimate:
    """Estimacion de gas para una transaccion."""
    gas_limit: int
    gas_price_gwei: Decimal
    max_fee_gwei: Decimal
    priority_fee_gwei: Decimal
    estimated_cost_native: Decimal
    estimated_cost_usd: Decimal


# Configuraciones de redes soportadas
NETWORK_CONFIGS: Dict[BlockchainNetwork, NetworkConfig] = {
    # ==================== MAINNETS ====================
    BlockchainNetwork.POLYGON: NetworkConfig(
        rpc_url=os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
        chain_id=137,
        name="Polygon Mainnet",
        currency_symbol="MATIC",
        block_explorer="https://polygonscan.com",
        is_testnet=False,
    ),
    BlockchainNetwork.ETHEREUM: NetworkConfig(
        rpc_url=os.getenv("ETHEREUM_RPC_URL", "https://eth.llamarpc.com"),
        chain_id=1,
        name="Ethereum Mainnet",
        currency_symbol="ETH",
        block_explorer="https://etherscan.io",
        is_testnet=False,
    ),
    BlockchainNetwork.ARBITRUM: NetworkConfig(
        rpc_url=os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
        chain_id=42161,
        name="Arbitrum One",
        currency_symbol="ETH",
        block_explorer="https://arbiscan.io",
        is_testnet=False,
    ),
    BlockchainNetwork.BASE: NetworkConfig(
        rpc_url=os.getenv("BASE_RPC_URL", "https://mainnet.base.org"),
        chain_id=8453,
        name="Base",
        currency_symbol="ETH",
        block_explorer="https://basescan.org",
        is_testnet=False,
    ),
    # ==================== TESTNETS ====================
    BlockchainNetwork.POLYGON_AMOY: NetworkConfig(
        rpc_url=os.getenv("POLYGON_AMOY_RPC_URL", "https://rpc-amoy.polygon.technology"),
        chain_id=80002,
        name="Polygon Amoy Testnet",
        currency_symbol="MATIC",
        block_explorer="https://amoy.polygonscan.com",
        is_testnet=True,
    ),
    BlockchainNetwork.ETHEREUM_SEPOLIA: NetworkConfig(
        rpc_url=os.getenv("ETHEREUM_SEPOLIA_RPC_URL", "https://rpc.sepolia.org"),
        chain_id=11155111,
        name="Ethereum Sepolia Testnet",
        currency_symbol="ETH",
        block_explorer="https://sepolia.etherscan.io",
        is_testnet=True,
    ),
    # ==================== LEGACY (Deprecated) ====================
    BlockchainNetwork.POLYGON_MUMBAI: NetworkConfig(
        rpc_url=os.getenv("POLYGON_AMOY_RPC_URL", "https://rpc-amoy.polygon.technology"),  # Redirigir a Amoy
        chain_id=80002,  # Usar Amoy chain ID
        name="Polygon Mumbai (Deprecated -> Amoy)",
        currency_symbol="MATIC",
        block_explorer="https://amoy.polygonscan.com",
        is_testnet=True,
    ),
}


class BlockchainService:
    """
    Servicio principal de blockchain para FinCore.
    Maneja conexiones Web3, contratos y transacciones.
    """

    def __init__(
        self,
        network: BlockchainNetwork = BlockchainNetwork.POLYGON,
        private_key: Optional[str] = None
    ):
        """
        Inicializa el servicio blockchain.

        Args:
            network: Red blockchain a usar
            private_key: Clave privada del operador (opcional)
        """
        self.network = network
        self.config = NETWORK_CONFIGS[network]

        # Conectar a Web3 con timeout corto (3 segundos)
        self.w3 = Web3(Web3.HTTPProvider(
            self.config.rpc_url,
            request_kwargs={'timeout': 3}
        ))

        # Middleware para redes PoA (Polygon, etc)
        if network in [BlockchainNetwork.POLYGON, BlockchainNetwork.POLYGON_MUMBAI]:
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        # Cuenta operadora (para firmar transacciones del sistema)
        self._private_key = private_key or os.getenv("BLOCKCHAIN_OPERATOR_KEY")
        self._operator_account = None
        if self._private_key:
            self._operator_account = Account.from_key(self._private_key)

    @property
    def is_connected(self) -> bool:
        """Verifica conexion a la red."""
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    @property
    def operator_address(self) -> Optional[str]:
        """Direccion del operador."""
        return self._operator_account.address if self._operator_account else None

    def switch_network(self, network: BlockchainNetwork) -> bool:
        """
        Cambia a otra red blockchain.

        Args:
            network: Nueva red

        Returns:
            True si el cambio fue exitoso
        """
        try:
            self.network = network
            self.config = NETWORK_CONFIGS[network]
            self.w3 = Web3(Web3.HTTPProvider(self.config.rpc_url))

            if network in [BlockchainNetwork.POLYGON, BlockchainNetwork.POLYGON_MUMBAI]:
                self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

            return self.is_connected
        except Exception as e:
            logger.error(f"Error switching network: {e}")
            return False

    # ==================== WALLET OPERATIONS ====================

    def create_wallet(self) -> Tuple[str, str]:
        """
        Crea una nueva wallet.

        Returns:
            Tupla (address, private_key)
        """
        account = Account.create()
        return (account.address, account.key.hex())

    def verify_wallet_signature(
        self,
        address: str,
        message: str,
        signature: str
    ) -> bool:
        """
        Verifica que una firma corresponda a una direccion.
        Usado para autenticar que el usuario controla la wallet.

        Args:
            address: Direccion de la wallet
            message: Mensaje original firmado
            signature: Firma en formato hex

        Returns:
            True si la firma es valida
        """
        try:
            message_encoded = encode_defunct(text=message)
            recovered_address = Account.recover_message(message_encoded, signature=signature)
            return recovered_address.lower() == address.lower()
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    def get_balance(self, address: str) -> Decimal:
        """
        Obtiene el balance nativo de una direccion.

        Args:
            address: Direccion de wallet

        Returns:
            Balance en unidades nativas (ETH/MATIC)
        """
        try:
            checksum_address = Web3.to_checksum_address(address)
            balance_wei = self.w3.eth.get_balance(checksum_address)
            return Decimal(str(Web3.from_wei(balance_wei, 'ether')))
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return Decimal("0")

    def get_token_balance(
        self,
        token_address: str,
        wallet_address: str
    ) -> Decimal:
        """
        Obtiene el balance de un token ERC-20.

        Args:
            token_address: Direccion del contrato del token
            wallet_address: Direccion de la wallet

        Returns:
            Balance de tokens
        """
        try:
            # ABI minimo para balanceOf
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                }
            ]

            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi
            )

            balance = contract.functions.balanceOf(
                Web3.to_checksum_address(wallet_address)
            ).call()

            decimals = contract.functions.decimals().call()

            return Decimal(balance) / Decimal(10 ** decimals)
        except Exception as e:
            logger.error(f"Error getting token balance: {e}")
            return Decimal("0")

    # ==================== CONTRACT OPERATIONS ====================

    def deploy_contract(
        self,
        abi: List[Dict],
        bytecode: str,
        constructor_args: Optional[List] = None,
        gas_limit: Optional[int] = None
    ) -> TransactionResult:
        """
        Despliega un contrato inteligente.

        Args:
            abi: ABI del contrato
            bytecode: Bytecode compilado
            constructor_args: Argumentos del constructor
            gas_limit: Limite de gas (opcional)

        Returns:
            Resultado de la transaccion
        """
        if not self._operator_account:
            return TransactionResult(
                success=False,
                error="No operator account configured"
            )

        try:
            contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)

            # Construir transaccion
            if constructor_args:
                tx = contract.constructor(*constructor_args)
            else:
                tx = contract.constructor()

            # Estimar gas si no se proporciona
            if not gas_limit:
                gas_limit = tx.estimate_gas({
                    'from': self._operator_account.address
                })
                gas_limit = int(gas_limit * 1.2)  # 20% buffer

            # Obtener nonce y gas price
            nonce = self.w3.eth.get_transaction_count(self._operator_account.address)
            gas_price = self.w3.eth.gas_price

            # Construir transaccion final
            tx_dict = tx.build_transaction({
                'from': self._operator_account.address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.config.chain_id
            })

            # Firmar y enviar
            signed_tx = self._operator_account.sign_transaction(tx_dict)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Esperar confirmacion
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

            return TransactionResult(
                success=receipt['status'] == 1,
                tx_hash=tx_hash.hex(),
                block_number=receipt['blockNumber'],
                gas_used=receipt['gasUsed'],
                logs=self._parse_logs(receipt.get('logs', []))
            )

        except Exception as e:
            logger.error(f"Error deploying contract: {e}")
            return TransactionResult(success=False, error=str(e))

    def call_contract_function(
        self,
        contract_address: str,
        abi: List[Dict],
        function_name: str,
        args: Optional[List] = None
    ) -> Any:
        """
        Llama a una funcion de lectura del contrato (view/pure).

        Args:
            contract_address: Direccion del contrato
            abi: ABI del contrato
            function_name: Nombre de la funcion
            args: Argumentos de la funcion

        Returns:
            Resultado de la funcion
        """
        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=abi
            )

            func = getattr(contract.functions, function_name)
            if args:
                result = func(*args).call()
            else:
                result = func().call()

            return result
        except Exception as e:
            logger.error(f"Error calling contract function: {e}")
            raise

    def execute_contract_function(
        self,
        contract_address: str,
        abi: List[Dict],
        function_name: str,
        args: Optional[List] = None,
        value: int = 0,
        gas_limit: Optional[int] = None
    ) -> TransactionResult:
        """
        Ejecuta una funcion que modifica estado del contrato.

        Args:
            contract_address: Direccion del contrato
            abi: ABI del contrato
            function_name: Nombre de la funcion
            args: Argumentos de la funcion
            value: Valor en wei a enviar
            gas_limit: Limite de gas

        Returns:
            Resultado de la transaccion
        """
        if not self._operator_account:
            return TransactionResult(
                success=False,
                error="No operator account configured"
            )

        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=abi
            )

            func = getattr(contract.functions, function_name)
            if args:
                tx = func(*args)
            else:
                tx = func()

            # Estimar gas
            if not gas_limit:
                gas_limit = tx.estimate_gas({
                    'from': self._operator_account.address,
                    'value': value
                })
                gas_limit = int(gas_limit * 1.2)

            # Construir transaccion
            nonce = self.w3.eth.get_transaction_count(self._operator_account.address)
            gas_price = self.w3.eth.gas_price

            tx_dict = tx.build_transaction({
                'from': self._operator_account.address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': self.config.chain_id,
                'value': value
            })

            # Firmar y enviar
            signed_tx = self._operator_account.sign_transaction(tx_dict)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Esperar confirmacion
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

            return TransactionResult(
                success=receipt['status'] == 1,
                tx_hash=tx_hash.hex(),
                block_number=receipt['blockNumber'],
                gas_used=receipt['gasUsed'],
                logs=self._parse_logs(receipt.get('logs', []))
            )

        except ContractLogicError as e:
            logger.error(f"Contract logic error: {e}")
            return TransactionResult(success=False, error=f"Contract reverted: {str(e)}")
        except Exception as e:
            logger.error(f"Error executing contract function: {e}")
            return TransactionResult(success=False, error=str(e))

    # ==================== TOKEN OPERATIONS ====================

    def mint_tokens(
        self,
        token_contract_address: str,
        token_abi: List[Dict],
        to_address: str,
        amount: Decimal,
        decimals: int = 18
    ) -> TransactionResult:
        """
        Mintea tokens a una direccion.

        Args:
            token_contract_address: Direccion del contrato del token
            token_abi: ABI del token
            to_address: Direccion destino
            amount: Cantidad de tokens
            decimals: Decimales del token

        Returns:
            Resultado de la transaccion
        """
        amount_raw = int(amount * Decimal(10 ** decimals))

        return self.execute_contract_function(
            contract_address=token_contract_address,
            abi=token_abi,
            function_name="mint",
            args=[Web3.to_checksum_address(to_address), amount_raw]
        )

    def transfer_tokens(
        self,
        token_contract_address: str,
        token_abi: List[Dict],
        to_address: str,
        amount: Decimal,
        decimals: int = 18
    ) -> TransactionResult:
        """
        Transfiere tokens desde la cuenta operadora.

        Args:
            token_contract_address: Direccion del contrato del token
            token_abi: ABI del token
            to_address: Direccion destino
            amount: Cantidad de tokens
            decimals: Decimales del token

        Returns:
            Resultado de la transaccion
        """
        amount_raw = int(amount * Decimal(10 ** decimals))

        return self.execute_contract_function(
            contract_address=token_contract_address,
            abi=token_abi,
            function_name="transfer",
            args=[Web3.to_checksum_address(to_address), amount_raw]
        )

    # ==================== GAS ESTIMATION ====================

    def estimate_gas(
        self,
        to_address: Optional[str] = None,
        data: Optional[str] = None,
        value: int = 0
    ) -> GasEstimate:
        """
        Estima el costo de gas para una transaccion.

        Args:
            to_address: Direccion destino (opcional para deploy)
            data: Data de la transaccion
            value: Valor en wei

        Returns:
            Estimacion de gas
        """
        try:
            tx_params: Dict[str, Any] = {'value': value}

            if to_address:
                tx_params['to'] = Web3.to_checksum_address(to_address)
            if data:
                tx_params['data'] = data
            if self._operator_account:
                tx_params['from'] = self._operator_account.address

            gas_limit = self.w3.eth.estimate_gas(tx_params)
            gas_price = self.w3.eth.gas_price

            # Para EIP-1559
            try:
                fee_history = self.w3.eth.fee_history(1, 'latest', [50])
                base_fee = fee_history['baseFeePerGas'][-1]
                priority_fee = self.w3.eth.max_priority_fee
                max_fee = base_fee * 2 + priority_fee
            except Exception:
                base_fee = gas_price
                priority_fee = gas_price // 10
                max_fee = gas_price

            estimated_cost_wei = gas_limit * max_fee
            estimated_cost_native = Decimal(str(Web3.from_wei(estimated_cost_wei, 'ether')))

            # Precio aproximado (deberia venir de un oracle)
            native_price_usd = Decimal("0.50") if self.network in [
                BlockchainNetwork.POLYGON, BlockchainNetwork.POLYGON_MUMBAI
            ] else Decimal("2000")

            return GasEstimate(
                gas_limit=gas_limit,
                gas_price_gwei=Decimal(str(Web3.from_wei(gas_price, 'gwei'))),
                max_fee_gwei=Decimal(str(Web3.from_wei(max_fee, 'gwei'))),
                priority_fee_gwei=Decimal(str(Web3.from_wei(priority_fee, 'gwei'))),
                estimated_cost_native=estimated_cost_native,
                estimated_cost_usd=estimated_cost_native * native_price_usd
            )
        except Exception as e:
            logger.error(f"Error estimating gas: {e}")
            # Valores por defecto
            return GasEstimate(
                gas_limit=21000,
                gas_price_gwei=Decimal("30"),
                max_fee_gwei=Decimal("50"),
                priority_fee_gwei=Decimal("2"),
                estimated_cost_native=Decimal("0.001"),
                estimated_cost_usd=Decimal("0.01")
            )

    # ==================== TRANSACTION MONITORING ====================

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        """
        Obtiene detalles de una transaccion.

        Args:
            tx_hash: Hash de la transaccion

        Returns:
            Detalles de la transaccion o None
        """
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            return dict(tx)
        except TransactionNotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting transaction: {e}")
            return None

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict]:
        """
        Obtiene el recibo de una transaccion.

        Args:
            tx_hash: Hash de la transaccion

        Returns:
            Recibo de la transaccion o None
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            return dict(receipt)
        except TransactionNotFound:
            return None
        except Exception as e:
            logger.error(f"Error getting receipt: {e}")
            return None

    def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout: int = 300,
        confirmations: int = 1
    ) -> TransactionResult:
        """
        Espera confirmacion de una transaccion.

        Args:
            tx_hash: Hash de la transaccion
            timeout: Timeout en segundos
            confirmations: Numero de confirmaciones requeridas

        Returns:
            Resultado de la transaccion
        """
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)

            # Esperar confirmaciones adicionales si es necesario
            if confirmations > 1:
                while True:
                    current_block = self.w3.eth.block_number
                    if current_block - receipt['blockNumber'] >= confirmations:
                        break
                    import time
                    time.sleep(2)

            return TransactionResult(
                success=receipt['status'] == 1,
                tx_hash=tx_hash,
                block_number=receipt['blockNumber'],
                gas_used=receipt['gasUsed'],
                logs=self._parse_logs(receipt.get('logs', []))
            )
        except Exception as e:
            logger.error(f"Error waiting for confirmation: {e}")
            return TransactionResult(success=False, tx_hash=tx_hash, error=str(e))

    # ==================== KYC BLOCKCHAIN ====================

    def compute_kyc_hash(
        self,
        user_id: str,
        document_type: str,
        document_number: str,
        verification_date: datetime
    ) -> str:
        """
        Computa el hash de los datos KYC para registro on-chain.
        No almacena datos personales, solo el hash.

        Args:
            user_id: ID del usuario
            document_type: Tipo de documento
            document_number: Numero de documento
            verification_date: Fecha de verificacion

        Returns:
            Hash SHA-256 de los datos
        """
        data = f"{user_id}|{document_type}|{document_number}|{verification_date.isoformat()}"
        return "0x" + hashlib.sha256(data.encode()).hexdigest()

    def verify_kyc_hash(
        self,
        kyc_hash: str,
        user_id: str,
        document_type: str,
        document_number: str,
        verification_date: datetime
    ) -> bool:
        """
        Verifica que un hash KYC corresponda a los datos.

        Returns:
            True si el hash es valido
        """
        computed_hash = self.compute_kyc_hash(
            user_id, document_type, document_number, verification_date
        )
        return computed_hash.lower() == kyc_hash.lower()

    # ==================== MERKLE TREE (for dividends) ====================

    @staticmethod
    def compute_merkle_root(leaves: List[str]) -> str:
        """
        Computa la raiz de un Merkle tree.
        Usado para distribuciones masivas de dividendos.

        Args:
            leaves: Lista de hashes de hojas

        Returns:
            Raiz del Merkle tree
        """
        if not leaves:
            return "0x" + "0" * 64

        # Asegurar que los leaves son hashes
        leaves = [
            leaf if leaf.startswith("0x") else "0x" + leaf
            for leaf in leaves
        ]

        while len(leaves) > 1:
            if len(leaves) % 2 == 1:
                leaves.append(leaves[-1])  # Duplicar ultimo si es impar

            new_leaves = []
            for i in range(0, len(leaves), 2):
                combined = leaves[i][2:] + leaves[i+1][2:]  # Quitar 0x
                new_hash = "0x" + hashlib.sha256(bytes.fromhex(combined)).hexdigest()
                new_leaves.append(new_hash)

            leaves = new_leaves

        return leaves[0]

    @staticmethod
    def compute_dividend_leaf(
        wallet_address: str,
        amount: Decimal,
        decimals: int = 18
    ) -> str:
        """
        Computa la hoja del Merkle tree para un dividendo.

        Args:
            wallet_address: Direccion de la wallet
            amount: Monto del dividendo
            decimals: Decimales

        Returns:
            Hash de la hoja
        """
        amount_raw = int(amount * Decimal(10 ** decimals))
        data = f"{wallet_address.lower()}|{amount_raw}"
        return "0x" + hashlib.sha256(data.encode()).hexdigest()

    # ==================== HELPERS ====================

    def _parse_logs(self, logs: List) -> List[Dict]:
        """Parsea los logs de una transaccion."""
        parsed = []
        for log in logs:
            parsed.append({
                'address': log.get('address'),
                'topics': [t.hex() if hasattr(t, 'hex') else t for t in log.get('topics', [])],
                'data': log.get('data').hex() if hasattr(log.get('data'), 'hex') else log.get('data'),
                'block_number': log.get('blockNumber'),
                'log_index': log.get('logIndex'),
            })
        return parsed

    def get_current_block(self) -> int:
        """Obtiene el numero de bloque actual."""
        return self.w3.eth.block_number

    def get_chain_id(self) -> int:
        """Obtiene el chain ID de la red actual."""
        return self.w3.eth.chain_id


# Singleton para uso global
_blockchain_service: Optional[BlockchainService] = None


def get_blockchain_service(
    network: BlockchainNetwork = BlockchainNetwork.POLYGON
) -> BlockchainService:
    """
    Obtiene la instancia del servicio blockchain.

    Args:
        network: Red a usar

    Returns:
        Instancia de BlockchainService
    """
    global _blockchain_service

    if _blockchain_service is None or _blockchain_service.network != network:
        _blockchain_service = BlockchainService(network=network)

    return _blockchain_service
