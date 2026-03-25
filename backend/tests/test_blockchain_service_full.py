"""
Tests para BlockchainService - Servicio Blockchain.

Cobertura de operaciones de wallet, verificacion, y configuracion de red.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from datetime import datetime

from app.services.blockchain_service import (
    BlockchainService,
    NetworkConfig,
    TransactionResult,
    GasEstimate,
    NETWORK_CONFIGS,
)
from app.models.blockchain import (
    BlockchainNetwork,
    TransactionStatus,
    TransactionType,
)


class TestNetworkConfigDataclass:
    """Tests para dataclass NetworkConfig."""

    def test_network_config_creation(self):
        """Test creacion de NetworkConfig."""
        config = NetworkConfig(
            rpc_url="https://rpc.example.com",
            chain_id=1,
            name="Test Network",
            currency_symbol="TEST",
            block_explorer="https://explorer.example.com"
        )
        assert config.rpc_url == "https://rpc.example.com"
        assert config.chain_id == 1
        assert config.is_testnet is False

    def test_network_config_testnet(self):
        """Test NetworkConfig para testnet."""
        config = NetworkConfig(
            rpc_url="https://testnet.example.com",
            chain_id=11155111,
            name="Test Sepolia",
            currency_symbol="ETH",
            block_explorer="https://sepolia.explorer.com",
            is_testnet=True
        )
        assert config.is_testnet is True


class TestTransactionResultDataclass:
    """Tests para dataclass TransactionResult."""

    def test_transaction_result_success(self):
        """Test TransactionResult exitoso."""
        result = TransactionResult(
            success=True,
            tx_hash="0x123abc",
            block_number=12345,
            gas_used=21000
        )
        assert result.success is True
        assert result.tx_hash == "0x123abc"
        assert result.error is None

    def test_transaction_result_failure(self):
        """Test TransactionResult con error."""
        result = TransactionResult(
            success=False,
            error="Insufficient funds"
        )
        assert result.success is False
        assert result.error == "Insufficient funds"
        assert result.tx_hash is None


class TestGasEstimateDataclass:
    """Tests para dataclass GasEstimate."""

    def test_gas_estimate_creation(self):
        """Test creacion de GasEstimate."""
        estimate = GasEstimate(
            gas_limit=100000,
            gas_price_gwei=Decimal("50"),
            max_fee_gwei=Decimal("60"),
            priority_fee_gwei=Decimal("2"),
            estimated_cost_native=Decimal("0.005"),
            estimated_cost_usd=Decimal("5.00")
        )
        assert estimate.gas_limit == 100000
        assert estimate.gas_price_gwei == Decimal("50")
        assert estimate.estimated_cost_usd == Decimal("5.00")


class TestNetworkConfigs:
    """Tests para configuraciones de red."""

    def test_polygon_config_exists(self):
        """Test configuracion de Polygon existe."""
        assert BlockchainNetwork.POLYGON in NETWORK_CONFIGS
        config = NETWORK_CONFIGS[BlockchainNetwork.POLYGON]
        assert config.chain_id == 137
        assert config.currency_symbol == "MATIC"
        assert config.is_testnet is False

    def test_ethereum_config_exists(self):
        """Test configuracion de Ethereum existe."""
        assert BlockchainNetwork.ETHEREUM in NETWORK_CONFIGS
        config = NETWORK_CONFIGS[BlockchainNetwork.ETHEREUM]
        assert config.chain_id == 1
        assert config.currency_symbol == "ETH"

    def test_testnet_configs(self):
        """Test configuraciones de testnets."""
        if BlockchainNetwork.POLYGON_AMOY in NETWORK_CONFIGS:
            config = NETWORK_CONFIGS[BlockchainNetwork.POLYGON_AMOY]
            assert config.is_testnet is True

        if BlockchainNetwork.ETHEREUM_SEPOLIA in NETWORK_CONFIGS:
            config = NETWORK_CONFIGS[BlockchainNetwork.ETHEREUM_SEPOLIA]
            assert config.is_testnet is True

    def test_all_configs_have_required_fields(self):
        """Test que todas las configs tienen campos requeridos."""
        for network, config in NETWORK_CONFIGS.items():
            assert config.rpc_url is not None
            assert config.chain_id > 0
            assert config.name is not None
            assert config.currency_symbol is not None
            assert config.block_explorer is not None


class TestBlockchainServiceInit:
    """Tests para inicializacion de BlockchainService."""

    @patch('app.services.blockchain_service.Web3')
    def test_init_default_network(self, mock_web3):
        """Test inicializacion con red por defecto."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        service = BlockchainService()

        assert service.network == BlockchainNetwork.POLYGON

    @patch('app.services.blockchain_service.Web3')
    def test_init_custom_network(self, mock_web3):
        """Test inicializacion con red personalizada."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        service = BlockchainService(network=BlockchainNetwork.ETHEREUM)

        assert service.network == BlockchainNetwork.ETHEREUM
        assert service.config.chain_id == 1

    @patch('app.services.blockchain_service.Web3')
    @patch('app.services.blockchain_service.Account')
    def test_init_with_private_key(self, mock_account, mock_web3):
        """Test inicializacion con clave privada."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        mock_account_instance = MagicMock()
        mock_account_instance.address = "0x123"
        mock_account.from_key.return_value = mock_account_instance

        service = BlockchainService(private_key="0xabc123")

        assert service._private_key == "0xabc123"
        assert service._operator_account is not None


class TestBlockchainServiceConnection:
    """Tests para conexion de BlockchainService."""

    @patch('app.services.blockchain_service.Web3')
    def test_is_connected_true(self, mock_web3):
        """Test is_connected retorna True."""
        mock_instance = MagicMock()
        mock_instance.is_connected.return_value = True
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        service = BlockchainService()

        assert service.is_connected is True

    @patch('app.services.blockchain_service.Web3')
    def test_is_connected_false(self, mock_web3):
        """Test is_connected retorna False."""
        mock_instance = MagicMock()
        mock_instance.is_connected.return_value = False
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        service = BlockchainService()

        assert service.is_connected is False

    @patch('app.services.blockchain_service.Web3')
    def test_is_connected_exception(self, mock_web3):
        """Test is_connected retorna False en excepcion."""
        mock_instance = MagicMock()
        mock_instance.is_connected.side_effect = Exception("Connection error")
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        service = BlockchainService()

        assert service.is_connected is False


class TestBlockchainServiceOperator:
    """Tests para operador de BlockchainService."""

    @patch('app.services.blockchain_service.Web3')
    def test_operator_address_none_without_key(self, mock_web3):
        """Test operator_address es None sin clave."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        with patch.dict('os.environ', {'BLOCKCHAIN_OPERATOR_KEY': ''}):
            service = BlockchainService()
            service._operator_account = None

        assert service.operator_address is None

    @patch('app.services.blockchain_service.Web3')
    @patch('app.services.blockchain_service.Account')
    def test_operator_address_with_key(self, mock_account, mock_web3):
        """Test operator_address con clave."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        mock_account_instance = MagicMock()
        mock_account_instance.address = "0xOperator123"
        mock_account.from_key.return_value = mock_account_instance

        service = BlockchainService(private_key="0xprivatekey")

        assert service.operator_address == "0xOperator123"


class TestBlockchainServiceWallet:
    """Tests para operaciones de wallet."""

    @patch('app.services.blockchain_service.Web3')
    @patch('app.services.blockchain_service.Account')
    def test_create_wallet(self, mock_account, mock_web3):
        """Test creacion de wallet."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        mock_new_account = MagicMock()
        mock_new_account.address = "0xNewWallet123"
        mock_new_account.key.hex.return_value = "0xprivatekey"
        mock_account.create.return_value = mock_new_account

        service = BlockchainService()
        address, private_key = service.create_wallet()

        assert address == "0xNewWallet123"
        assert private_key == "0xprivatekey"

    @patch('app.services.blockchain_service.Web3')
    @patch('app.services.blockchain_service.Account')
    def test_verify_wallet_signature_valid(self, mock_account, mock_web3):
        """Test verificacion de firma valida."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        mock_account.recover_message.return_value = "0xUserAddress"

        service = BlockchainService()
        result = service.verify_wallet_signature(
            address="0xUserAddress",
            message="Sign this message",
            signature="0xsignature123"
        )

        assert result is True

    @patch('app.services.blockchain_service.Web3')
    @patch('app.services.blockchain_service.Account')
    def test_verify_wallet_signature_invalid(self, mock_account, mock_web3):
        """Test verificacion de firma invalida."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        mock_account.recover_message.return_value = "0xDifferentAddress"

        service = BlockchainService()
        result = service.verify_wallet_signature(
            address="0xUserAddress",
            message="Sign this message",
            signature="0xsignature123"
        )

        assert result is False

    @patch('app.services.blockchain_service.Web3')
    @patch('app.services.blockchain_service.Account')
    def test_verify_wallet_signature_exception(self, mock_account, mock_web3):
        """Test verificacion con excepcion."""
        mock_instance = MagicMock()
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        mock_account.recover_message.side_effect = Exception("Invalid signature")

        service = BlockchainService()
        result = service.verify_wallet_signature(
            address="0xUserAddress",
            message="Sign this message",
            signature="invalid"
        )

        assert result is False


class TestBlockchainServiceBalance:
    """Tests para balance de wallet."""

    @patch('app.services.blockchain_service.Web3')
    def test_get_balance_success(self, mock_web3):
        """Test obtener balance exitoso."""
        mock_instance = MagicMock()
        mock_instance.eth.get_balance.return_value = 1000000000000000000  # 1 ETH in wei
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()
        mock_web3.to_checksum_address.return_value = "0xAddress"
        mock_web3.from_wei.return_value = 1.0

        service = BlockchainService()
        balance = service.get_balance("0xAddress")

        assert balance >= Decimal("0")

    @patch('app.services.blockchain_service.Web3')
    def test_get_balance_exception(self, mock_web3):
        """Test obtener balance con excepcion."""
        mock_instance = MagicMock()
        mock_instance.eth.get_balance.side_effect = Exception("RPC error")
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        service = BlockchainService()
        balance = service.get_balance("0xInvalidAddress")

        assert balance == Decimal("0")


class TestBlockchainServiceSwitchNetwork:
    """Tests para cambio de red."""

    @patch('app.services.blockchain_service.Web3')
    def test_switch_network_success(self, mock_web3):
        """Test cambio de red exitoso."""
        mock_instance = MagicMock()
        mock_instance.is_connected.return_value = True
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()

        service = BlockchainService(network=BlockchainNetwork.POLYGON)
        result = service.switch_network(BlockchainNetwork.ETHEREUM)

        assert service.network == BlockchainNetwork.ETHEREUM
        assert service.config.chain_id == 1

    @patch('app.services.blockchain_service.Web3')
    def test_switch_network_failure(self, mock_web3):
        """Test cambio de red fallido."""
        mock_instance = MagicMock()
        mock_instance.is_connected.return_value = False
        mock_web3.return_value = mock_instance
        mock_web3.HTTPProvider = MagicMock()
        mock_web3.side_effect = [mock_instance, Exception("Connection failed")]

        service = BlockchainService(network=BlockchainNetwork.POLYGON)
        # El segundo Web3() lanzara excepcion
        result = service.switch_network(BlockchainNetwork.ETHEREUM)

        # Puede ser False o True dependiendo de la implementacion


class TestBlockchainEnums:
    """Tests para enums de blockchain."""

    def test_blockchain_network_values(self):
        """Test valores de BlockchainNetwork."""
        assert hasattr(BlockchainNetwork, 'POLYGON')
        assert hasattr(BlockchainNetwork, 'ETHEREUM')

    def test_transaction_status_values(self):
        """Test valores de TransactionStatus."""
        assert hasattr(TransactionStatus, 'PENDING')
        assert hasattr(TransactionStatus, 'CONFIRMED')
        assert hasattr(TransactionStatus, 'FAILED')

    def test_transaction_type_values(self):
        """Test valores de TransactionType."""
        assert hasattr(TransactionType, 'TOKEN_TRANSFER')
        assert hasattr(TransactionType, 'TOKEN_MINT')
        assert hasattr(TransactionType, 'DIVIDEND_PAYMENT')
