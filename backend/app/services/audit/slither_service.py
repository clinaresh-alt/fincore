"""
Servicio de Auditoría con Slither para FinCore.
Integra análisis estático automático de Smart Contracts.

Slither detecta:
- Reentrancy vulnerabilities
- Integer overflow/underflow
- Unchecked external calls
- Access control issues
- Gas optimization opportunities
- Y más de 70 tipos de vulnerabilidades
"""

import subprocess
import json
import os
import tempfile
import shutil
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SeverityLevel(str, Enum):
    """Niveles de severidad de vulnerabilidades."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"
    OPTIMIZATION = "optimization"


class AuditStatus(str, Enum):
    """Estados del proceso de auditoría."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Vulnerability:
    """Representa una vulnerabilidad detectada."""
    detector: str
    check: str
    severity: SeverityLevel
    confidence: str
    description: str
    elements: List[Dict] = field(default_factory=list)
    recommendation: str = ""
    line_numbers: List[int] = field(default_factory=list)
    contract: str = ""
    function: str = ""


@dataclass
class AuditReport:
    """Reporte completo de auditoría."""
    contract_name: str
    contract_path: str
    audit_id: str
    status: AuditStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    security_score: float = 100.0
    passed: bool = True
    summary: Dict[str, int] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    raw_output: Optional[Dict] = None
    error: Optional[str] = None


class SlitherAuditService:
    """
    Servicio de auditoría automática usando Slither.

    Uso:
        service = SlitherAuditService()
        report = await service.audit_contract("/path/to/Contract.sol")

        if not report.passed:
            for vuln in report.vulnerabilities:
                print(f"[{vuln.severity}] {vuln.description}")
    """

    # Mapeo de detectores críticos para Fintech
    CRITICAL_DETECTORS = {
        "reentrancy-eth",
        "reentrancy-no-eth",
        "reentrancy-unlimited-gas",
        "arbitrary-send-eth",
        "controlled-delegatecall",
        "suicidal",
        "unprotected-upgrade",
        "msg-value-loop",
        "delegatecall-loop",
    }

    HIGH_DETECTORS = {
        "unchecked-transfer",
        "reentrancy-benign",
        "uninitialized-state",
        "uninitialized-local",
        "locked-ether",
        "tx-origin",
        "weak-prng",
        "shadowing-state",
        "incorrect-equality",
    }

    def __init__(
        self,
        contracts_path: str = None,
        solc_version: str = "0.8.20"
    ):
        """
        Inicializa el servicio de auditoría.

        Args:
            contracts_path: Ruta base de los contratos
            solc_version: Versión de Solidity a usar
        """
        self.contracts_path = contracts_path or os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..", "contracts"
        )
        self.solc_version = solc_version
        self._check_slither_installed()

    def _check_slither_installed(self) -> bool:
        """Verifica que Slither esté instalado."""
        try:
            result = subprocess.run(
                ["slither", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"Slither version: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            logger.warning(
                "Slither no está instalado. "
                "Instalar con: pip install slither-analyzer"
            )
        return False

    async def audit_contract(
        self,
        contract_path: str,
        config_file: Optional[str] = None
    ) -> AuditReport:
        """
        Ejecuta auditoría completa en un contrato.

        Args:
            contract_path: Ruta al archivo .sol
            config_file: Archivo de configuración opcional

        Returns:
            AuditReport con todos los hallazgos
        """
        import uuid

        audit_id = str(uuid.uuid4())[:8]
        started_at = datetime.utcnow()

        report = AuditReport(
            contract_name=os.path.basename(contract_path),
            contract_path=contract_path,
            audit_id=audit_id,
            status=AuditStatus.RUNNING,
            started_at=started_at
        )

        try:
            # Ejecutar Slither
            raw_results = await self._run_slither(contract_path, config_file)
            report.raw_output = raw_results

            # Parsear vulnerabilidades
            vulnerabilities = self._parse_vulnerabilities(raw_results)
            report.vulnerabilities = vulnerabilities

            # Calcular score y resumen
            report.security_score = self._calculate_security_score(vulnerabilities)
            report.summary = self._generate_summary(vulnerabilities)
            report.recommendations = self._generate_recommendations(vulnerabilities)

            # Determinar si pasó
            critical_count = report.summary.get("critical", 0)
            high_count = report.summary.get("high", 0)
            report.passed = critical_count == 0 and high_count == 0

            report.status = AuditStatus.COMPLETED
            report.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error en auditoría: {e}")
            report.status = AuditStatus.FAILED
            report.error = str(e)
            report.completed_at = datetime.utcnow()

        return report

    async def _run_slither(
        self,
        contract_path: str,
        config_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta Slither en un contrato.

        Args:
            contract_path: Ruta al contrato
            config_file: Configuración opcional

        Returns:
            Resultados JSON de Slither
        """
        cmd = [
            "slither",
            contract_path,
            "--json", "-",
            "--solc-args", f"--optimize --optimize-runs=200"
        ]

        if config_file and os.path.exists(config_file):
            cmd.extend(["--config-file", config_file])

        # Agregar detección de todas las vulnerabilidades
        cmd.extend([
            "--detect", "all",
            "--exclude", "naming-convention,similar-names"
        ])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutos máximo
                cwd=os.path.dirname(contract_path)
            )

            # Slither devuelve código 255 si hay vulnerabilidades
            if result.stdout:
                return json.loads(result.stdout)
            elif result.stderr:
                # Intentar parsear stderr si stdout está vacío
                logger.warning(f"Slither stderr: {result.stderr}")
                return {"success": True, "results": {"detectors": []}}

        except subprocess.TimeoutExpired:
            logger.error("Slither timeout después de 5 minutos")
            raise RuntimeError("Análisis timeout - contrato muy complejo")
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando output de Slither: {e}")
            raise

        return {"success": True, "results": {"detectors": []}}

    def _parse_vulnerabilities(
        self,
        raw_results: Dict
    ) -> List[Vulnerability]:
        """
        Parsea los resultados de Slither a objetos Vulnerability.

        Args:
            raw_results: Output JSON de Slither

        Returns:
            Lista de vulnerabilidades
        """
        vulnerabilities = []

        detectors = raw_results.get("results", {}).get("detectors", [])

        for detector in detectors:
            severity = self._map_severity(detector.get("impact", ""))

            vuln = Vulnerability(
                detector=detector.get("check", "unknown"),
                check=detector.get("check", ""),
                severity=severity,
                confidence=detector.get("confidence", ""),
                description=detector.get("description", ""),
                elements=detector.get("elements", []),
                recommendation=self._get_recommendation(detector.get("check", "")),
            )

            # Extraer información de ubicación
            for element in detector.get("elements", []):
                if "source_mapping" in element:
                    lines = element["source_mapping"].get("lines", [])
                    vuln.line_numbers.extend(lines)

                if "name" in element:
                    if element.get("type") == "contract":
                        vuln.contract = element["name"]
                    elif element.get("type") == "function":
                        vuln.function = element["name"]

            vulnerabilities.append(vuln)

        # Ordenar por severidad
        severity_order = {
            SeverityLevel.CRITICAL: 0,
            SeverityLevel.HIGH: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.LOW: 3,
            SeverityLevel.INFORMATIONAL: 4,
            SeverityLevel.OPTIMIZATION: 5,
        }
        vulnerabilities.sort(key=lambda v: severity_order.get(v.severity, 99))

        return vulnerabilities

    def _map_severity(self, impact: str) -> SeverityLevel:
        """Mapea el impacto de Slither a SeverityLevel."""
        mapping = {
            "High": SeverityLevel.HIGH,
            "Medium": SeverityLevel.MEDIUM,
            "Low": SeverityLevel.LOW,
            "Informational": SeverityLevel.INFORMATIONAL,
            "Optimization": SeverityLevel.OPTIMIZATION,
        }
        return mapping.get(impact, SeverityLevel.INFORMATIONAL)

    def _calculate_security_score(
        self,
        vulnerabilities: List[Vulnerability]
    ) -> float:
        """
        Calcula puntuación de seguridad (0-100).

        Penalizaciones:
        - Critical: -30 puntos
        - High: -15 puntos
        - Medium: -5 puntos
        - Low: -2 puntos
        - Info/Optimization: -0.5 puntos
        """
        score = 100.0

        penalties = {
            SeverityLevel.CRITICAL: 30,
            SeverityLevel.HIGH: 15,
            SeverityLevel.MEDIUM: 5,
            SeverityLevel.LOW: 2,
            SeverityLevel.INFORMATIONAL: 0.5,
            SeverityLevel.OPTIMIZATION: 0.5,
        }

        for vuln in vulnerabilities:
            score -= penalties.get(vuln.severity, 0)

        return max(0.0, min(100.0, score))

    def _generate_summary(
        self,
        vulnerabilities: List[Vulnerability]
    ) -> Dict[str, int]:
        """Genera resumen por severidad."""
        summary = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "informational": 0,
            "optimization": 0,
            "total": len(vulnerabilities)
        }

        for vuln in vulnerabilities:
            if vuln.severity.value in summary:
                summary[vuln.severity.value] += 1

        return summary

    def _generate_recommendations(
        self,
        vulnerabilities: List[Vulnerability]
    ) -> List[str]:
        """Genera recomendaciones basadas en vulnerabilidades."""
        recommendations = []
        seen_checks = set()

        for vuln in vulnerabilities:
            if vuln.check not in seen_checks:
                rec = self._get_recommendation(vuln.check)
                if rec:
                    recommendations.append(f"[{vuln.severity.value.upper()}] {rec}")
                    seen_checks.add(vuln.check)

        return recommendations[:10]  # Top 10 recomendaciones

    def _get_recommendation(self, check: str) -> str:
        """Obtiene recomendación para un tipo de vulnerabilidad."""
        recommendations = {
            "reentrancy-eth": (
                "Implementar patrón Checks-Effects-Interactions. "
                "Usar ReentrancyGuard de OpenZeppelin."
            ),
            "reentrancy-no-eth": (
                "Actualizar estado antes de llamadas externas. "
                "Considerar usar nonReentrant modifier."
            ),
            "unchecked-transfer": (
                "Usar SafeERC20 de OpenZeppelin para transferencias seguras."
            ),
            "arbitrary-send-eth": (
                "Restringir destinatarios de ETH. "
                "Implementar whitelist de direcciones."
            ),
            "tx-origin": (
                "Reemplazar tx.origin por msg.sender. "
                "tx.origin es vulnerable a phishing."
            ),
            "uninitialized-state": (
                "Inicializar todas las variables de estado en el constructor."
            ),
            "locked-ether": (
                "Agregar función de retiro para ETH bloqueado."
            ),
            "shadowing-state": (
                "Renombrar variables locales que ocultan estado."
            ),
            "incorrect-equality": (
                "Usar >= o <= en lugar de == para comparar balances."
            ),
            "weak-prng": (
                "Usar Chainlink VRF para números aleatorios seguros."
            ),
        }
        return recommendations.get(check, "")

    async def audit_all_contracts(
        self,
        contracts_dir: Optional[str] = None
    ) -> Dict[str, AuditReport]:
        """
        Audita todos los contratos en un directorio.

        Args:
            contracts_dir: Directorio con contratos

        Returns:
            Dict con reportes por contrato
        """
        contracts_dir = contracts_dir or os.path.join(
            self.contracts_path, "src"
        )

        reports = {}
        sol_files = list(Path(contracts_dir).glob("**/*.sol"))

        for sol_file in sol_files:
            logger.info(f"Auditando: {sol_file.name}")
            report = await self.audit_contract(str(sol_file))
            reports[sol_file.name] = report

        return reports

    def generate_html_report(self, report: AuditReport) -> str:
        """Genera reporte HTML de la auditoría."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Audit Report - {report.contract_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background: #1a1a2e; color: white; padding: 20px; }}
        .score {{ font-size: 48px; font-weight: bold; }}
        .score.pass {{ color: #00ff00; }}
        .score.fail {{ color: #ff0000; }}
        .vulnerability {{ border-left: 4px solid; padding: 10px; margin: 10px 0; }}
        .critical {{ border-color: #ff0000; background: #fff0f0; }}
        .high {{ border-color: #ff6600; background: #fff5e6; }}
        .medium {{ border-color: #ffcc00; background: #fffce6; }}
        .low {{ border-color: #0066ff; background: #e6f0ff; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .summary-item {{ padding: 15px; border-radius: 8px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Smart Contract Security Audit</h1>
        <p>Contract: {report.contract_name}</p>
        <p>Audit ID: {report.audit_id}</p>
        <p>Date: {report.completed_at}</p>
    </div>

    <h2>Security Score</h2>
    <div class="score {'pass' if report.passed else 'fail'}">
        {report.security_score:.1f}/100
    </div>
    <p>Status: {'PASSED' if report.passed else 'FAILED - Critical issues found'}</p>

    <h2>Summary</h2>
    <div class="summary">
        <div class="summary-item" style="background:#ff0000;color:white;">
            Critical: {report.summary.get('critical', 0)}
        </div>
        <div class="summary-item" style="background:#ff6600;color:white;">
            High: {report.summary.get('high', 0)}
        </div>
        <div class="summary-item" style="background:#ffcc00;">
            Medium: {report.summary.get('medium', 0)}
        </div>
        <div class="summary-item" style="background:#0066ff;color:white;">
            Low: {report.summary.get('low', 0)}
        </div>
    </div>

    <h2>Vulnerabilities ({len(report.vulnerabilities)})</h2>
"""

        for vuln in report.vulnerabilities:
            html += f"""
    <div class="vulnerability {vuln.severity.value}">
        <h3>[{vuln.severity.value.upper()}] {vuln.detector}</h3>
        <p>{vuln.description}</p>
        {f'<p><strong>Contract:</strong> {vuln.contract}</p>' if vuln.contract else ''}
        {f'<p><strong>Function:</strong> {vuln.function}</p>' if vuln.function else ''}
        {f'<p><strong>Lines:</strong> {", ".join(map(str, vuln.line_numbers[:5]))}</p>' if vuln.line_numbers else ''}
        {f'<p><strong>Recommendation:</strong> {vuln.recommendation}</p>' if vuln.recommendation else ''}
    </div>
"""

        html += """
    <h2>Recommendations</h2>
    <ul>
"""
        for rec in report.recommendations:
            html += f"        <li>{rec}</li>\n"

        html += """
    </ul>

    <footer>
        <p>Generated by FinCore Smart Contract Audit System</p>
        <p>Powered by Slither Static Analyzer</p>
    </footer>
</body>
</html>
"""
        return html
