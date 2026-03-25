"""
Endpoints para gestion de Smart Contract Deployments.
Permite desplegar, verificar y consultar contratos desde el panel admin.
"""
import os
import json
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from app.api.v1.endpoints.admin import require_admin
from app.models.user import User

router = APIRouter()

# Ruta base de contratos
CONTRACTS_PATH = Path(__file__).parent.parent.parent.parent.parent / "contracts"
DEPLOYMENTS_PATH = CONTRACTS_PATH / "deployments"

# Redes soportadas
SUPPORTED_NETWORKS = {
    "polygonAmoy": {"name": "Polygon Amoy", "chainId": 80002, "isTestnet": True},
    "sepolia": {"name": "Sepolia", "chainId": 11155111, "isTestnet": True},
    "polygon": {"name": "Polygon", "chainId": 137, "isTestnet": False},
    "arbitrum": {"name": "Arbitrum One", "chainId": 42161, "isTestnet": False},
    "base": {"name": "Base", "chainId": 8453, "isTestnet": False},
}


# Schemas
class DeployedContract(BaseModel):
    """Contrato desplegado."""
    name: str
    address: str
    network: str
    chainId: int
    deployedAt: str
    verified: bool = False
    constructorArgs: Optional[List] = None


class DeploymentStatus(BaseModel):
    """Estado de deployment en una red."""
    network: str
    chainId: int
    contracts: List[DeployedContract]
    lastDeployment: Optional[str] = None


class DeployInfraRequest(BaseModel):
    """Request para desplegar infraestructura."""
    network: str = Field(..., description="ID de la red (polygonAmoy, polygon, etc)")


class DeployTokenRequest(BaseModel):
    """Request para desplegar token de proyecto."""
    network: str
    projectName: str = Field(..., min_length=3, max_length=100)
    projectSymbol: str = Field(..., min_length=2, max_length=5)
    totalSupply: str
    projectUri: Optional[str] = ""


class VerifyRequest(BaseModel):
    """Request para verificar contratos."""
    network: str


class DeploymentResult(BaseModel):
    """Resultado de deployment."""
    success: bool
    network: str
    contracts: Optional[dict] = None
    message: Optional[str] = None
    error: Optional[str] = None


# Helpers
def get_deployment_file(network: str) -> Optional[Path]:
    """Obtiene el archivo de deployment para una red."""
    network_config = SUPPORTED_NETWORKS.get(network)
    if not network_config:
        return None

    filename = f"{network}-{network_config['chainId']}.json"
    filepath = DEPLOYMENTS_PATH / filename

    if filepath.exists():
        return filepath
    return None


def read_deployment_data(network: str) -> Optional[dict]:
    """Lee datos de deployment de una red."""
    filepath = get_deployment_file(network)
    if filepath and filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return None


def get_all_deployments() -> List[DeploymentStatus]:
    """Obtiene todos los deployments existentes."""
    deployments = []

    if not DEPLOYMENTS_PATH.exists():
        return deployments

    for network_id, network_config in SUPPORTED_NETWORKS.items():
        data = read_deployment_data(network_id)
        if data:
            contracts = []
            for name, contract_data in data.get("contracts", {}).items():
                contracts.append(DeployedContract(
                    name=name,
                    address=contract_data.get("address", ""),
                    network=network_id,
                    chainId=network_config["chainId"],
                    deployedAt=data.get("deployedAt", ""),
                    verified=contract_data.get("verified", False),
                    constructorArgs=contract_data.get("constructorArgs")
                ))

            # Agregar tokens si existen
            tokens_path = DEPLOYMENTS_PATH / "tokens"
            if tokens_path.exists():
                for token_file in tokens_path.glob(f"*-{network_id}-{network_config['chainId']}.json"):
                    with open(token_file, "r") as f:
                        token_data = json.load(f)
                        token = token_data.get("token", {})
                        contracts.append(DeployedContract(
                            name=f"Token: {token.get('symbol', 'Unknown')}",
                            address=token.get("address", ""),
                            network=network_id,
                            chainId=network_config["chainId"],
                            deployedAt=token_data.get("deployedAt", ""),
                            verified=token.get("verified", False)
                        ))

            deployments.append(DeploymentStatus(
                network=network_id,
                chainId=network_config["chainId"],
                contracts=contracts,
                lastDeployment=data.get("deployedAt")
            ))

    return deployments


async def run_hardhat_command(command: str, env: Optional[dict] = None) -> tuple[bool, str]:
    """Ejecuta un comando de Hardhat de forma asincrona."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(CONTRACTS_PATH),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=300  # 5 minutos max
        )

        output = stdout.decode() + stderr.decode()
        success = process.returncode == 0

        return success, output
    except asyncio.TimeoutError:
        return False, "Timeout: El proceso tardo mas de 5 minutos"
    except Exception as e:
        return False, str(e)


# Endpoints
@router.get("/deployments", response_model=List[DeploymentStatus])
async def get_deployments(
    current_user: User = Depends(require_admin)
):
    """
    Obtiene el estado de todos los deployments.
    Solo accesible para administradores.
    """
    return get_all_deployments()


@router.get("/deployments/{network}", response_model=Optional[DeploymentStatus])
async def get_network_deployment(
    network: str,
    current_user: User = Depends(require_admin)
):
    """
    Obtiene el deployment de una red especifica.
    """
    if network not in SUPPORTED_NETWORKS:
        raise HTTPException(status_code=400, detail=f"Red no soportada: {network}")

    deployments = get_all_deployments()
    for d in deployments:
        if d.network == network:
            return d

    return None


@router.post("/deployments/infrastructure", response_model=DeploymentResult)
async def deploy_infrastructure(
    request: DeployInfraRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin)
):
    """
    Despliega los contratos de infraestructura (KYC, Investment, Dividends).
    IMPORTANTE: Requiere que BLOCKCHAIN_OPERATOR_KEY este configurado.
    """
    if request.network not in SUPPORTED_NETWORKS:
        raise HTTPException(status_code=400, detail=f"Red no soportada: {request.network}")

    # Verificar que existe la clave del operador
    if not os.getenv("BLOCKCHAIN_OPERATOR_KEY"):
        raise HTTPException(
            status_code=400,
            detail="BLOCKCHAIN_OPERATOR_KEY no configurado. Configure la clave privada en las variables de entorno."
        )

    command = f"npx hardhat run scripts/deploy.js --network {request.network}"

    success, output = await run_hardhat_command(command)

    if success:
        deployment_data = read_deployment_data(request.network)
        return DeploymentResult(
            success=True,
            network=request.network,
            contracts=deployment_data.get("contracts") if deployment_data else None,
            message="Deployment completado exitosamente"
        )
    else:
        return DeploymentResult(
            success=False,
            network=request.network,
            error=output[:1000]  # Limitar output de error
        )


@router.post("/deployments/token", response_model=DeploymentResult)
async def deploy_token(
    request: DeployTokenRequest,
    current_user: User = Depends(require_admin)
):
    """
    Despliega un nuevo token de proyecto.
    """
    if request.network not in SUPPORTED_NETWORKS:
        raise HTTPException(status_code=400, detail=f"Red no soportada: {request.network}")

    if not os.getenv("BLOCKCHAIN_OPERATOR_KEY"):
        raise HTTPException(
            status_code=400,
            detail="BLOCKCHAIN_OPERATOR_KEY no configurado"
        )

    env = {
        "PROJECT_NAME": request.projectName,
        "PROJECT_SYMBOL": request.projectSymbol,
        "TOTAL_SUPPLY": request.totalSupply,
        "PROJECT_URI": request.projectUri or ""
    }

    command = f"npx hardhat run scripts/deploy-token.js --network {request.network}"

    success, output = await run_hardhat_command(command, env)

    if success:
        # Buscar la direccion del token en el output o archivo
        network_config = SUPPORTED_NETWORKS[request.network]
        token_file = DEPLOYMENTS_PATH / "tokens" / f"{request.projectSymbol.lower()}-{request.network}-{network_config['chainId']}.json"

        address = None
        if token_file.exists():
            with open(token_file, "r") as f:
                token_data = json.load(f)
                address = token_data.get("token", {}).get("address")

        return DeploymentResult(
            success=True,
            network=request.network,
            contracts={"address": address, "symbol": request.projectSymbol},
            message=f"Token {request.projectSymbol} desplegado exitosamente"
        )
    else:
        return DeploymentResult(
            success=False,
            network=request.network,
            error=output[:1000]
        )


@router.post("/deployments/verify")
async def verify_contracts(
    request: VerifyRequest,
    current_user: User = Depends(require_admin)
):
    """
    Verifica todos los contratos desplegados en una red.
    """
    if request.network not in SUPPORTED_NETWORKS:
        raise HTTPException(status_code=400, detail=f"Red no soportada: {request.network}")

    command = f"npx hardhat run scripts/verify-contracts.js --network {request.network}"

    success, output = await run_hardhat_command(command)

    # Parsear resultados del output
    results = []
    deployment_data = read_deployment_data(request.network)

    if deployment_data:
        for name in deployment_data.get("contracts", {}).keys():
            verified = "verificado exitosamente" in output.lower() or "already verified" in output.lower()
            results.append({"name": name, "verified": verified})

    return {
        "success": success,
        "network": request.network,
        "results": results,
        "output": output[:2000] if not success else None
    }


@router.get("/deployments/networks")
async def get_supported_networks(
    current_user: User = Depends(require_admin)
):
    """
    Lista las redes soportadas para deployment.
    """
    return [
        {
            "id": network_id,
            **config
        }
        for network_id, config in SUPPORTED_NETWORKS.items()
    ]
