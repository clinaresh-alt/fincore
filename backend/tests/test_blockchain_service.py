"""
Tests unitarios para BlockchainService.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from decimal import Decimal
from datetime import datetime

from app.services.blockchain_service import (
    BlockchainService,
    TransactionResult,
    GasEstimate,
    NetworkConfig,
    NETWORK_CONFIGS,
)
from app.models.blockchain import BlockchainNetwork


class TestBlockchainServiceInit:
    """Tests de inicializacion del servicio."""

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_init_default_network(self):
        """Test inicializacion con red por defecto (Polygon)."""
        with patch('app.services.blockchain_service.Web3') as mock_web3:
            mock_web3.return_value.is_connected.return_value = True
            service = BlockchainService()

            assert service.network == BlockchainNetwork.POLYGON
            assert service.config.chain_id == 137

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_init_testnet(self):
        """Test inicializacion con testnet."""
        with patch('app.services.blockchain_service.Web3') as mock_web3:
            mock_web3.return_value.is_connected.return_value = True
            service = BlockchainService(network=BlockchainNetwork.POLYGON_AMOY)

            assert service.network == BlockchainNetwork.POLYGON_AMOY
            assert service.config.is_testnet is True
            assert service.config.chain_id == 80002

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_init_with_private_key(self):
        """Test inicializacion con clave privada."""
        test_key = "0x" + "a" * 64

        with patch('app.services.blockchain_service.Web3') as mock_web3:
            with patch('app.services.blockchain_service.Account') as mock_account:
                mock_web3.return_value.is_connected.return_value = True
                mock_acc = MagicMock()
                mock_acc.address = "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"
                mock_account.from_key.return_value = mock_acc

                service = BlockchainService(private_key=test_key)

                assert service.operator_address == "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"


class TestBlockchainServiceConnection:
    """Tests de conexion a red."""

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_is_connected_true(self, mock_web3):
        """Test conexion exitosa."""
        with patch('app.services.blockchain_service.Web3') as mock_w3_class:
            mock_w3_class.return_value = mock_web3
            service = BlockchainService()

            assert service.is_connected is True

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_is_connected_false(self):
        """Test conexion fallida."""
        with patch('app.services.blockchain_service.Web3') as mock_w3_class:
            mock_w3_class.return_value.is_connected.return_value = False
            service = BlockchainService()

            assert service.is_connected is False

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_switch_network(self, mock_web3):
        """Test cambio de red."""
        with patch('app.services.blockchain_service.Web3') as mock_w3_class:
            mock_w3_class.return_value = mock_web3
            service = BlockchainService(network=BlockchainNetwork.POLYGON)

            result = service.switch_network(BlockchainNetwork.ETHEREUM)

            assert result is True
            assert service.network == BlockchainNetwork.ETHEREUM


class TestWalletOperations:
    """Tests de operaciones de wallet."""

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_create_wallet(self):
        """Test creacion de wallet."""
        with patch('app.services.blockchain_service.Web3'):
            with patch('app.services.blockchain_service.Account') as mock_account:
                mock_acc = MagicMock()
                mock_acc.address = "0x1234567890123456789012345678901234567890"
                mock_acc.key.hex.return_value = "0x" + "a" * 64
                mock_account.create.return_value = mock_acc

                service = BlockchainService()
                address, private_key = service.create_wallet()

                assert address.startswith("0x")
                assert len(address) == 42
                assert private_key.startswith("0x")

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_verify_wallet_signature_valid(self):
        """Test verificacion de firma valida."""
        with patch('app.services.blockchain_service.Web3'):
            with patch('app.services.blockchain_service.Account') as mock_account:
                mock_account.recover_message.return_value = "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"

                service = BlockchainService()
                result = service.verify_wallet_signature(
                    address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16",
                    message="Sign this message",
                    signature="0x" + "a" * 130
                )

                assert result is True

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_verify_wallet_signature_invalid(self):
        """Test verificacion de firma invalida."""
        with patch('app.services.blockchain_service.Web3'):
            with patch('app.services.blockchain_service.Account') as mock_account:
                mock_account.recover_message.return_value = "0xDifferentAddress1234567890123456789012345"

                service = BlockchainService()
                result = service.verify_wallet_signature(
                    address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16",
                    message="Sign this message",
                    signature="0x" + "a" * 130
                )

                assert result is False

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_get_balance(self, mock_web3, sample_wallet_address):
        """Test obtencion de balance."""
        with patch('app.services.blockchain_service.Web3') as mock_w3_class:
            mock_w3_class.return_value = mock_web3
            mock_w3_class.to_checksum_address = lambda x: x
            mock_w3_class.from_wei = lambda x, unit: Decimal(str(x)) / Decimal("1e18")

            service = BlockchainService()
            balance = service.get_balance(sample_wallet_address)

            assert isinstance(balance, Decimal)
            assert balance >= 0


class TestTokenOperations:
    """Tests de operaciones con tokens."""

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_get_token_balance(self, mock_web3, sample_wallet_address, sample_contract_address, sample_contract_abi):
        """Test obtencion de balance de token."""
        with patch('app.services.blockchain_service.Web3') as mock_w3_class:
            mock_contract = MagicMock()
            mock_contract.functions.balanceOf.return_value.call.return_value = 1000000000  # 1000 con 6 decimales
            mock_contract.functions.decimals.return_value.call.return_value = 6

            mock_web3.eth.contract.return_value = mock_contract
            mock_w3_class.return_value = mock_web3
            mock_w3_class.to_checksum_address = lambda x: x

            service = BlockchainService()
            balance = service.get_token_balance(sample_contract_address, sample_wallet_address)

            assert isinstance(balance, Decimal)


class TestKYCOperations:
    """Tests de operaciones KYC en blockchain."""

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_compute_kyc_hash(self):
        """Test computacion de hash KYC."""
        with patch('app.services.blockchain_service.Web3'):
            service = BlockchainService()

            kyc_hash = service.compute_kyc_hash(
                user_id="user-123",
                document_type="INE",
                document_number="ABC123456",
                verification_date=datetime(2024, 1, 15, 10, 30, 0)
            )

            assert kyc_hash.startswith("0x")
            assert len(kyc_hash) == 66  # 0x + 64 chars

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_verify_kyc_hash_valid(self):
        """Test verificacion de hash KYC valido."""
        with patch('app.services.blockchain_service.Web3'):
            service = BlockchainService()

            verification_date = datetime(2024, 1, 15, 10, 30, 0)
            kyc_hash = service.compute_kyc_hash(
                user_id="user-123",
                document_type="INE",
                document_number="ABC123456",
                verification_date=verification_date
            )

            result = service.verify_kyc_hash(
                kyc_hash=kyc_hash,
                user_id="user-123",
                document_type="INE",
                document_number="ABC123456",
                verification_date=verification_date
            )

            assert result is True

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_verify_kyc_hash_invalid(self):
        """Test verificacion de hash KYC invalido."""
        with patch('app.services.blockchain_service.Web3'):
            service = BlockchainService()

            result = service.verify_kyc_hash(
                kyc_hash="0x" + "a" * 64,
                user_id="user-123",
                document_type="INE",
                document_number="ABC123456",
                verification_date=datetime(2024, 1, 15, 10, 30, 0)
            )

            assert result is False


class TestMerkleTree:
    """Tests de operaciones Merkle Tree."""

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_compute_merkle_root_empty(self):
        """Test Merkle root con lista vacia."""
        result = BlockchainService.compute_merkle_root([])
        assert result == "0x" + "0" * 64

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_compute_merkle_root_single(self):
        """Test Merkle root con un solo elemento."""
        leaves = ["0x" + "a" * 64]
        result = BlockchainService.compute_merkle_root(leaves)

        assert result.startswith("0x")
        assert len(result) == 66

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_compute_merkle_root_multiple(self):
        """Test Merkle root con multiples elementos."""
        leaves = [
            "0x" + "a" * 64,
            "0x" + "b" * 64,
            "0x" + "c" * 64,
            "0x" + "d" * 64,
        ]
        result = BlockchainService.compute_merkle_root(leaves)

        assert result.startswith("0x")
        assert len(result) == 66

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_compute_merkle_root_odd_count(self):
        """Test Merkle root con cantidad impar de elementos."""
        leaves = [
            "0x" + "a" * 64,
            "0x" + "b" * 64,
            "0x" + "c" * 64,
        ]
        result = BlockchainService.compute_merkle_root(leaves)

        assert result.startswith("0x")
        assert len(result) == 66

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_compute_dividend_leaf(self):
        """Test computacion de hoja de dividendo."""
        leaf = BlockchainService.compute_dividend_leaf(
            wallet_address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16",
            amount=Decimal("100.50"),
            decimals=18
        )

        assert leaf.startswith("0x")
        assert len(leaf) == 66


class TestGasEstimation:
    """Tests de estimacion de gas."""

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_estimate_gas_default(self, mock_web3):
        """Test estimacion de gas con valores por defecto."""
        mock_web3.eth.estimate_gas.return_value = 21000

        with patch('app.services.blockchain_service.Web3') as mock_w3_class:
            mock_w3_class.return_value = mock_web3
            mock_w3_class.to_checksum_address = lambda x: x
            mock_w3_class.from_wei = lambda x, unit: Decimal(str(x)) / Decimal("1e9") if unit == 'gwei' else Decimal(str(x)) / Decimal("1e18")

            service = BlockchainService()
            estimate = service.estimate_gas()

            assert isinstance(estimate, GasEstimate)
            assert estimate.gas_limit > 0
            assert estimate.gas_price_gwei > 0


class TestTransactionResult:
    """Tests de TransactionResult dataclass."""

    @pytest.mark.unit
    def test_transaction_result_success(self):
        """Test resultado de transaccion exitosa."""
        result = TransactionResult(
            success=True,
            tx_hash="0x" + "a" * 64,
            block_number=50000001,
            gas_used=21000
        )

        assert result.success is True
        assert result.error is None

    @pytest.mark.unit
    def test_transaction_result_failure(self):
        """Test resultado de transaccion fallida."""
        result = TransactionResult(
            success=False,
            error="Insufficient funds"
        )

        assert result.success is False
        assert result.error == "Insufficient funds"


class TestNetworkConfigs:
    """Tests de configuraciones de red."""

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_all_networks_configured(self):
        """Test que todas las redes tienen configuracion."""
        for network in BlockchainNetwork:
            assert network in NETWORK_CONFIGS, f"Missing config for {network}"

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_mainnet_not_testnet(self):
        """Test que mainnets no estan marcadas como testnet."""
        mainnet_networks = [
            BlockchainNetwork.POLYGON,
            BlockchainNetwork.ETHEREUM,
            BlockchainNetwork.ARBITRUM,
            BlockchainNetwork.BASE,
        ]

        for network in mainnet_networks:
            config = NETWORK_CONFIGS[network]
            assert config.is_testnet is False, f"{network} should not be testnet"

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_testnets_marked_correctly(self):
        """Test que testnets estan marcadas correctamente."""
        testnet_networks = [
            BlockchainNetwork.POLYGON_AMOY,
            BlockchainNetwork.ETHEREUM_SEPOLIA,
        ]

        for network in testnet_networks:
            config = NETWORK_CONFIGS[network]
            assert config.is_testnet is True, f"{network} should be testnet"

    @pytest.mark.unit
    @pytest.mark.blockchain
    def test_chain_ids_unique(self):
        """Test que los chain IDs son unicos (excepto legacy)."""
        seen_ids = {}
        for network, config in NETWORK_CONFIGS.items():
            if network == BlockchainNetwork.POLYGON_MUMBAI:
                continue  # Skip deprecated
            if config.chain_id in seen_ids:
                pytest.fail(f"Duplicate chain_id {config.chain_id}: {network} and {seen_ids[config.chain_id]}")
            seen_ids[config.chain_id] = network
