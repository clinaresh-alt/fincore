"""
Servicio de Reportes Regulatorios para UIF.

Genera reportes segun LFPIORPI:
- ROS: Reporte de Operaciones Sospechosas
- ROV: Reporte de Operaciones con Activos Virtuales
- ROI: Reporte de Operaciones Internas

Formato: XML segun especificaciones UIF Mexico.
"""

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import hashlib

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.compliance import (
    RegulatoryReport,
    AMLAlert,
    TransactionMonitor,
    KYCProfile,
    ReportType,
    AlertStatus,
)


@dataclass
class ReportContent:
    """Contenido estructurado del reporte."""
    reference_number: str
    report_type: ReportType
    period_start: datetime
    period_end: datetime
    transactions: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    total_amount: Decimal
    xml_content: str


class ReportingService:
    """Servicio de reportes regulatorios."""

    # Codigo de institucion (asignado por UIF)
    INSTITUTION_CODE = "FINCORE001"  # Placeholder - obtener de configuracion

    def __init__(self, db: Session):
        self.db = db

    # ============ Report Generation ============

    def generate_rov(
        self,
        period_start: datetime,
        period_end: datetime,
        generated_by: uuid.UUID
    ) -> RegulatoryReport:
        """
        Genera Reporte de Operaciones con Activos Virtuales (ROV).
        Requerido mensualmente para operaciones >= 15,000 USD.
        """
        # Obtener transacciones del periodo
        threshold = Decimal("290000")  # ~15,000 USD en MXN

        transactions = self.db.query(TransactionMonitor).filter(
            TransactionMonitor.executed_at >= period_start,
            TransactionMonitor.executed_at <= period_end,
            TransactionMonitor.amount >= threshold,
        ).all()

        # Estructurar datos
        tx_data = []
        total_amount = Decimal("0")

        for tx in transactions:
            # Obtener datos KYC del usuario
            profile = self.db.query(KYCProfile).filter(
                KYCProfile.user_id == tx.user_id
            ).first()

            tx_data.append({
                "id": str(tx.id),
                "fecha": tx.executed_at.isoformat(),
                "tipo": tx.transaction_type,
                "monto": float(tx.amount),
                "moneda": tx.currency,
                "origen_tipo": tx.source_type,
                "origen_id": tx.source_identifier,
                "destino_tipo": tx.destination_type,
                "destino_id": tx.destination_identifier,
                "red_blockchain": tx.blockchain_network,
                "hash_tx": tx.tx_hash,
                "cliente": {
                    "curp": profile.curp if profile else None,
                    "rfc": profile.rfc if profile else None,
                    "nombre": f"{profile.first_name} {profile.last_name}" if profile else None,
                },
            })
            total_amount += tx.amount

        # Generar XML
        xml_content = self._generate_rov_xml(tx_data, period_start, period_end)

        # Crear reporte
        reference = self._generate_reference_number(ReportType.ROV)

        report = RegulatoryReport(
            report_type=ReportType.ROV,
            reference_number=reference,
            period_start=period_start,
            period_end=period_end,
            report_data={"transactions": tx_data},
            xml_content=xml_content,
            transactions_count=len(transactions),
            total_amount=total_amount,
            status="ready",
            generated_by=generated_by,
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return report

    def generate_ros(
        self,
        alert_ids: List[uuid.UUID],
        generated_by: uuid.UUID,
        narrative: str
    ) -> RegulatoryReport:
        """
        Genera Reporte de Operaciones Sospechosas (ROS).
        Para alertas que requieren reporte a UIF.
        """
        alerts = self.db.query(AMLAlert).filter(
            AMLAlert.id.in_(alert_ids)
        ).all()

        if not alerts:
            raise ValueError("No se encontraron alertas")

        # Estructurar datos de alertas
        alert_data = []
        total_amount = Decimal("0")
        user_ids = set()

        for alert in alerts:
            alert_data.append({
                "id": str(alert.id),
                "tipo": alert.alert_type.value,
                "severidad": alert.severity.value,
                "titulo": alert.title,
                "descripcion": alert.description,
                "monto": float(alert.amount) if alert.amount else 0,
                "fecha_deteccion": alert.detected_at.isoformat(),
                "notas_investigacion": alert.investigation_notes,
            })
            if alert.amount:
                total_amount += alert.amount
            user_ids.add(alert.user_id)

        # Obtener datos de usuarios involucrados
        users_data = []
        for user_id in user_ids:
            profile = self.db.query(KYCProfile).filter(
                KYCProfile.user_id == user_id
            ).first()
            if profile:
                users_data.append({
                    "curp": profile.curp,
                    "rfc": profile.rfc,
                    "nombre": f"{profile.first_name} {profile.last_name}",
                    "nacionalidad": profile.nationality,
                    "is_pep": profile.is_pep,
                })

        # Periodo basado en alertas
        period_start = min(a.detected_at for a in alerts)
        period_end = max(a.detected_at for a in alerts)

        # Generar XML
        xml_content = self._generate_ros_xml(
            alert_data, users_data, narrative, period_start, period_end
        )

        reference = self._generate_reference_number(ReportType.ROS)

        report = RegulatoryReport(
            report_type=ReportType.ROS,
            reference_number=reference,
            period_start=period_start,
            period_end=period_end,
            report_data={
                "alerts": alert_data,
                "users": users_data,
                "narrative": narrative,
            },
            xml_content=xml_content,
            transactions_count=len(alerts),
            total_amount=total_amount,
            related_alerts=[str(a) for a in alert_ids],
            status="ready",
            generated_by=generated_by,
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        # Marcar alertas como reportadas
        for alert in alerts:
            alert.reported_to_uif = True
            alert.uif_report_id = report.id
            alert.status = AlertStatus.REPORTED

        self.db.commit()

        return report

    # ============ XML Generation ============

    def _generate_rov_xml(
        self,
        transactions: List[Dict],
        period_start: datetime,
        period_end: datetime
    ) -> str:
        """Genera XML de ROV segun formato UIF."""
        root = ET.Element("ReporteOperacionesVirtuales")
        root.set("version", "1.0")

        # Header
        header = ET.SubElement(root, "Encabezado")
        ET.SubElement(header, "CodigoInstitucion").text = self.INSTITUTION_CODE
        ET.SubElement(header, "TipoReporte").text = "ROV"
        ET.SubElement(header, "PeriodoInicio").text = period_start.strftime("%Y-%m-%d")
        ET.SubElement(header, "PeriodoFin").text = period_end.strftime("%Y-%m-%d")
        ET.SubElement(header, "FechaGeneracion").text = datetime.utcnow().isoformat()

        # Operaciones
        ops = ET.SubElement(root, "Operaciones")
        for tx in transactions:
            op = ET.SubElement(ops, "Operacion")
            ET.SubElement(op, "Folio").text = tx["id"][:20]
            ET.SubElement(op, "FechaOperacion").text = tx["fecha"][:10]
            ET.SubElement(op, "TipoOperacion").text = tx["tipo"]
            ET.SubElement(op, "Monto").text = str(tx["monto"])
            ET.SubElement(op, "Moneda").text = tx["moneda"]

            if tx.get("red_blockchain"):
                ET.SubElement(op, "RedBlockchain").text = tx["red_blockchain"]
            if tx.get("hash_tx"):
                ET.SubElement(op, "HashTransaccion").text = tx["hash_tx"]

            # Cliente
            if tx.get("cliente"):
                cliente = ET.SubElement(op, "Cliente")
                if tx["cliente"].get("curp"):
                    ET.SubElement(cliente, "CURP").text = tx["cliente"]["curp"]
                if tx["cliente"].get("rfc"):
                    ET.SubElement(cliente, "RFC").text = tx["cliente"]["rfc"]
                if tx["cliente"].get("nombre"):
                    ET.SubElement(cliente, "Nombre").text = tx["cliente"]["nombre"]

        # Totales
        totales = ET.SubElement(root, "Totales")
        ET.SubElement(totales, "NumeroOperaciones").text = str(len(transactions))
        ET.SubElement(totales, "MontoTotal").text = str(sum(t["monto"] for t in transactions))

        return ET.tostring(root, encoding="unicode", method="xml")

    def _generate_ros_xml(
        self,
        alerts: List[Dict],
        users: List[Dict],
        narrative: str,
        period_start: datetime,
        period_end: datetime
    ) -> str:
        """Genera XML de ROS segun formato UIF."""
        root = ET.Element("ReporteOperacionSospechosa")
        root.set("version", "1.0")

        # Header
        header = ET.SubElement(root, "Encabezado")
        ET.SubElement(header, "CodigoInstitucion").text = self.INSTITUTION_CODE
        ET.SubElement(header, "TipoReporte").text = "ROS"
        ET.SubElement(header, "FechaDeteccion").text = period_start.strftime("%Y-%m-%d")
        ET.SubElement(header, "FechaReporte").text = datetime.utcnow().isoformat()

        # Personas involucradas
        personas = ET.SubElement(root, "PersonasInvolucradas")
        for user in users:
            persona = ET.SubElement(personas, "Persona")
            if user.get("curp"):
                ET.SubElement(persona, "CURP").text = user["curp"]
            if user.get("rfc"):
                ET.SubElement(persona, "RFC").text = user["rfc"]
            if user.get("nombre"):
                ET.SubElement(persona, "Nombre").text = user["nombre"]
            ET.SubElement(persona, "EsPEP").text = "Si" if user.get("is_pep") else "No"

        # Alertas/Operaciones
        operaciones = ET.SubElement(root, "OperacionesSospechosas")
        for alert in alerts:
            op = ET.SubElement(operaciones, "Operacion")
            ET.SubElement(op, "TipoAlerta").text = alert["tipo"]
            ET.SubElement(op, "Severidad").text = alert["severidad"]
            ET.SubElement(op, "Descripcion").text = alert["descripcion"]
            ET.SubElement(op, "Monto").text = str(alert["monto"])
            ET.SubElement(op, "FechaDeteccion").text = alert["fecha_deteccion"][:10]

        # Narrativa
        ET.SubElement(root, "Narrativa").text = narrative

        # Indicadores de sospecha
        indicadores = ET.SubElement(root, "IndicadoresSospecha")
        alert_types = set(a["tipo"] for a in alerts)
        for atype in alert_types:
            ET.SubElement(indicadores, "Indicador").text = atype

        return ET.tostring(root, encoding="unicode", method="xml")

    def _generate_reference_number(self, report_type: ReportType) -> str:
        """Genera numero de referencia unico."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_suffix = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:6].upper()
        return f"{self.INSTITUTION_CODE}-{report_type.value.upper()}-{timestamp}-{random_suffix}"

    # ============ Report Management ============

    def get_reports(
        self,
        report_type: Optional[ReportType] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[RegulatoryReport]:
        """Obtiene reportes con filtros."""
        query = self.db.query(RegulatoryReport)

        if report_type:
            query = query.filter(RegulatoryReport.report_type == report_type)
        if status:
            query = query.filter(RegulatoryReport.status == status)

        return query.order_by(RegulatoryReport.created_at.desc()).limit(limit).all()

    def approve_report(
        self,
        report_id: uuid.UUID,
        approver_id: uuid.UUID
    ) -> RegulatoryReport:
        """Aprueba reporte para envio."""
        report = self.db.query(RegulatoryReport).filter(
            RegulatoryReport.id == report_id
        ).first()

        if not report:
            raise ValueError("Reporte no encontrado")

        report.approved_by = approver_id
        report.approved_at = datetime.utcnow()
        report.status = "approved"

        self.db.commit()
        self.db.refresh(report)

        return report

    def submit_report(
        self,
        report_id: uuid.UUID
    ) -> RegulatoryReport:
        """
        Envia reporte a UIF.
        En produccion: integrar con API de UIF.
        """
        report = self.db.query(RegulatoryReport).filter(
            RegulatoryReport.id == report_id,
            RegulatoryReport.status == "approved"
        ).first()

        if not report:
            raise ValueError("Reporte no encontrado o no aprobado")

        # Simulacion de envio - en produccion integrar con UIF
        # Aqui iria la llamada al webservice de UIF

        report.submitted_at = datetime.utcnow()
        report.status = "submitted"
        # report.uif_confirmation = response_from_uif

        self.db.commit()
        self.db.refresh(report)

        return report

    # ============ Statistics ============

    def get_reporting_statistics(self, year: int = None) -> Dict[str, Any]:
        """Obtiene estadisticas de reportes."""
        if not year:
            year = datetime.utcnow().year

        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)

        # Reportes por tipo
        by_type = {}
        for rtype in ReportType:
            count = self.db.query(RegulatoryReport).filter(
                RegulatoryReport.created_at >= start_date,
                RegulatoryReport.created_at <= end_date,
                RegulatoryReport.report_type == rtype,
            ).count()
            by_type[rtype.value] = count

        # Reportes por estado
        by_status = {}
        for status in ["draft", "ready", "approved", "submitted", "accepted", "rejected"]:
            count = self.db.query(RegulatoryReport).filter(
                RegulatoryReport.created_at >= start_date,
                RegulatoryReport.created_at <= end_date,
                RegulatoryReport.status == status,
            ).count()
            by_status[status] = count

        # Monto total reportado
        total_amount = self.db.query(
            func.sum(RegulatoryReport.total_amount)
        ).filter(
            RegulatoryReport.created_at >= start_date,
            RegulatoryReport.created_at <= end_date,
            RegulatoryReport.status.in_(["submitted", "accepted"]),
        ).scalar() or Decimal("0")

        return {
            "year": year,
            "total_reports": sum(by_type.values()),
            "by_type": by_type,
            "by_status": by_status,
            "total_amount_reported_mxn": float(total_amount),
        }
