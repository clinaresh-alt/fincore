"""
Endpoints para Sistema de Soporte.
Tickets, Status Page, Centro de Impuestos y Verificación SAT 69-B.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.support import (
    SupportTicket, TicketMessage, StatusComponent, StatusIncident, StatusUpdate,
    TicketCategory, TicketPriority, TicketStatus, SystemStatus
)
from app.models.audit import AuditLog
from app.schemas.support import (
    TicketCreate, TicketResponse, TicketDetailResponse, TicketListResponse,
    TicketMessageCreate, TicketMessageResponse, TicketRateRequest,
    StatusComponentResponse, StatusIncidentResponse, StatusPageResponse,
    StatusUpdateResponse, TaxYearSummary, TaxTransactionItem, TaxReportResponse,
    SAT69BCheckRequest, SAT69BCheckResponse
)

router = APIRouter(prefix="/support", tags=["Support"])


# ==================== TICKETS ====================

@router.post("/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    data: TicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crear un nuevo ticket de soporte."""
    # Generar número de ticket
    ticket_number = SupportTicket.generate_ticket_number(db)

    ticket = SupportTicket(
        ticket_number=ticket_number,
        user_id=current_user.id,
        subject=data.subject,
        description=data.description,
        category=TicketCategory(data.category.value),
        priority=TicketPriority(data.priority.value),
        status=TicketStatus.OPEN,
        user_email=current_user.email,
        user_name=f"{current_user.nombre} {current_user.apellido}",
        related_entity_type=data.related_entity_type,
        related_entity_id=data.related_entity_id,
        attachments=data.attachments or [],
        tags=[],
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return TicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        user_id=ticket.user_id,
        subject=ticket.subject,
        description=ticket.description,
        category=ticket.category.value,
        priority=ticket.priority.value,
        status=ticket.status.value,
        assigned_to=ticket.assigned_to,
        user_email=ticket.user_email,
        user_name=ticket.user_name,
        tags=ticket.tags or [],
        attachments=ticket.attachments or [],
        related_entity_type=ticket.related_entity_type,
        related_entity_id=ticket.related_entity_id,
        satisfaction_rating=ticket.satisfaction_rating,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        first_response_at=ticket.first_response_at,
        resolved_at=ticket.resolved_at,
        closed_at=ticket.closed_at,
    )


@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Listar tickets del usuario."""
    query = db.query(SupportTicket).filter(
        SupportTicket.user_id == current_user.id
    )

    if status_filter:
        query = query.filter(SupportTicket.status == TicketStatus(status_filter))
    if category:
        query = query.filter(SupportTicket.category == TicketCategory(category))

    total = query.count()

    tickets = query.order_by(desc(SupportTicket.created_at)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return TicketListResponse(
        tickets=[
            TicketResponse(
                id=t.id,
                ticket_number=t.ticket_number,
                user_id=t.user_id,
                subject=t.subject,
                description=t.description,
                category=t.category.value,
                priority=t.priority.value,
                status=t.status.value,
                assigned_to=t.assigned_to,
                user_email=t.user_email,
                user_name=t.user_name,
                tags=t.tags or [],
                attachments=t.attachments or [],
                related_entity_type=t.related_entity_type,
                related_entity_id=t.related_entity_id,
                satisfaction_rating=t.satisfaction_rating,
                created_at=t.created_at,
                updated_at=t.updated_at,
                first_response_at=t.first_response_at,
                resolved_at=t.resolved_at,
                closed_at=t.closed_at,
            )
            for t in tickets
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tickets/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener detalle de un ticket con sus mensajes."""
    ticket = db.query(SupportTicket).filter(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id
    ).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket no encontrado"
        )

    # Obtener mensajes (excluyendo notas internas)
    messages = db.query(TicketMessage).filter(
        TicketMessage.ticket_id == ticket_id,
        TicketMessage.is_internal == False
    ).order_by(TicketMessage.created_at).all()

    # Marcar mensajes como leídos
    for msg in messages:
        if not msg.is_from_user and not msg.read_at:
            msg.read_at = datetime.utcnow()
    db.commit()

    return TicketDetailResponse(
        ticket=TicketResponse(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            user_id=ticket.user_id,
            subject=ticket.subject,
            description=ticket.description,
            category=ticket.category.value,
            priority=ticket.priority.value,
            status=ticket.status.value,
            assigned_to=ticket.assigned_to,
            user_email=ticket.user_email,
            user_name=ticket.user_name,
            tags=ticket.tags or [],
            attachments=ticket.attachments or [],
            related_entity_type=ticket.related_entity_type,
            related_entity_id=ticket.related_entity_id,
            satisfaction_rating=ticket.satisfaction_rating,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            first_response_at=ticket.first_response_at,
            resolved_at=ticket.resolved_at,
            closed_at=ticket.closed_at,
        ),
        messages=[
            TicketMessageResponse(
                id=m.id,
                ticket_id=m.ticket_id,
                user_id=m.user_id,
                message=m.message,
                is_internal=m.is_internal,
                is_from_user=m.is_from_user,
                attachments=m.attachments or [],
                created_at=m.created_at,
                read_at=m.read_at,
            )
            for m in messages
        ]
    )


@router.post("/tickets/{ticket_id}/messages", response_model=TicketMessageResponse)
async def add_ticket_message(
    ticket_id: UUID,
    data: TicketMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Agregar mensaje a un ticket."""
    ticket = db.query(SupportTicket).filter(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id
    ).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket no encontrado"
        )

    if ticket.status in [TicketStatus.CLOSED, TicketStatus.RESOLVED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden agregar mensajes a tickets cerrados"
        )

    message = TicketMessage(
        ticket_id=ticket_id,
        user_id=current_user.id,
        message=data.message,
        is_internal=False,
        is_from_user=True,
        attachments=data.attachments or [],
    )

    # Si estaba esperando respuesta del usuario, cambiar estado
    if ticket.status == TicketStatus.WAITING_USER:
        ticket.status = TicketStatus.IN_PROGRESS

    db.add(message)
    db.commit()
    db.refresh(message)

    return TicketMessageResponse(
        id=message.id,
        ticket_id=message.ticket_id,
        user_id=message.user_id,
        message=message.message,
        is_internal=message.is_internal,
        is_from_user=message.is_from_user,
        attachments=message.attachments or [],
        created_at=message.created_at,
        read_at=message.read_at,
    )


@router.post("/tickets/{ticket_id}/rate")
async def rate_ticket(
    ticket_id: UUID,
    data: TicketRateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Calificar la resolución de un ticket."""
    ticket = db.query(SupportTicket).filter(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id
    ).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket no encontrado"
        )

    if ticket.status not in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden calificar tickets resueltos o cerrados"
        )

    if ticket.satisfaction_rating:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ticket ya fue calificado"
        )

    ticket.satisfaction_rating = data.rating
    ticket.satisfaction_feedback = data.feedback
    db.commit()

    return {"message": "Gracias por tu calificación", "rating": data.rating}


@router.post("/tickets/{ticket_id}/close")
async def close_ticket(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cerrar un ticket (por el usuario)."""
    ticket = db.query(SupportTicket).filter(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id
    ).first()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket no encontrado"
        )

    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ticket ya está cerrado"
        )

    ticket.status = TicketStatus.CLOSED
    ticket.closed_at = datetime.utcnow()
    db.commit()

    return {"message": "Ticket cerrado exitosamente", "ticket_number": ticket.ticket_number}


# ==================== STATUS PAGE (PÚBLICO) ====================

@router.get("/status", response_model=StatusPageResponse)
async def get_status_page(db: Session = Depends(get_db)):
    """
    Obtener estado actual del sistema.
    Este endpoint es PÚBLICO (no requiere autenticación).
    """
    # Obtener componentes visibles
    components = db.query(StatusComponent).filter(
        StatusComponent.is_visible == True
    ).order_by(StatusComponent.display_order).all()

    # Calcular estado general
    if not components:
        overall_status = SystemStatus.OPERATIONAL.value
    else:
        statuses = [c.status for c in components]
        if SystemStatus.MAJOR_OUTAGE in statuses:
            overall_status = SystemStatus.MAJOR_OUTAGE.value
        elif SystemStatus.PARTIAL_OUTAGE in statuses:
            overall_status = SystemStatus.PARTIAL_OUTAGE.value
        elif SystemStatus.DEGRADED in statuses:
            overall_status = SystemStatus.DEGRADED.value
        elif SystemStatus.MAINTENANCE in statuses:
            overall_status = SystemStatus.MAINTENANCE.value
        else:
            overall_status = SystemStatus.OPERATIONAL.value

    # Incidentes activos (no resueltos, no programados)
    active_incidents = db.query(StatusIncident).filter(
        StatusIncident.is_resolved == False,
        StatusIncident.is_scheduled == False
    ).order_by(desc(StatusIncident.created_at)).all()

    # Mantenimientos programados (futuros)
    scheduled_maintenances = db.query(StatusIncident).filter(
        StatusIncident.is_scheduled == True,
        StatusIncident.is_resolved == False,
        or_(
            StatusIncident.scheduled_for >= datetime.utcnow(),
            and_(
                StatusIncident.scheduled_for <= datetime.utcnow(),
                StatusIncident.scheduled_until >= datetime.utcnow()
            )
        )
    ).order_by(StatusIncident.scheduled_for).all()

    # Incidentes recientes (últimos 7 días, resueltos)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_incidents = db.query(StatusIncident).filter(
        StatusIncident.is_resolved == True,
        StatusIncident.resolved_at >= week_ago
    ).order_by(desc(StatusIncident.resolved_at)).limit(10).all()

    def format_incident(incident: StatusIncident) -> StatusIncidentResponse:
        updates = db.query(StatusUpdate).filter(
            StatusUpdate.incident_id == incident.id
        ).order_by(desc(StatusUpdate.created_at)).all()

        component_name = None
        if incident.component:
            component_name = incident.component.name

        return StatusIncidentResponse(
            id=incident.id,
            component_id=incident.component_id,
            component_name=component_name,
            title=incident.title,
            description=incident.description,
            status=incident.status.value,
            is_scheduled=incident.is_scheduled,
            scheduled_for=incident.scheduled_for,
            scheduled_until=incident.scheduled_until,
            is_resolved=incident.is_resolved,
            created_at=incident.created_at,
            resolved_at=incident.resolved_at,
            updates=[
                StatusUpdateResponse(
                    id=u.id,
                    message=u.message,
                    status=u.status.value,
                    created_at=u.created_at,
                )
                for u in updates
            ]
        )

    return StatusPageResponse(
        overall_status=overall_status,
        components=[
            StatusComponentResponse(
                id=c.id,
                name=c.name,
                description=c.description,
                group=c.group,
                status=c.status.value,
                display_order=c.display_order,
                last_incident_at=c.last_incident_at,
            )
            for c in components
        ],
        active_incidents=[format_incident(i) for i in active_incidents],
        scheduled_maintenances=[format_incident(i) for i in scheduled_maintenances],
        recent_incidents=[format_incident(i) for i in recent_incidents],
        last_updated=datetime.utcnow(),
    )


# ==================== CENTRO DE IMPUESTOS ====================

@router.get("/tax-center/{year}", response_model=TaxReportResponse)
async def get_tax_report(
    year: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generar reporte fiscal anual para el SAT.
    Incluye inversiones, dividendos, ganancias/pérdidas realizadas.
    """
    from app.models.investment import Investment, InvestmentTransaction
    from app.models.remittance import Remittance, RemittanceStatus
    from app.models.marketplace import TokenTrade

    year_start = datetime(year, 1, 1)
    year_end = datetime(year, 12, 31, 23, 59, 59)

    transactions_list: List[TaxTransactionItem] = []

    # 1. Inversiones realizadas en el año
    investments = db.query(Investment).filter(
        Investment.user_id == current_user.id,
        Investment.fecha_inversion >= year_start,
        Investment.fecha_inversion <= year_end
    ).all()

    total_investments = 0.0
    for inv in investments:
        amount = float(inv.monto)
        total_investments += amount
        transactions_list.append(TaxTransactionItem(
            date=inv.fecha_inversion,
            type="investment",
            description=f"Inversión en {inv.project.nombre if inv.project else 'Proyecto'}",
            amount=amount,
            currency="MXN",
            reference_id=str(inv.id),
        ))

    # 2. Dividendos recibidos
    dividends = db.query(InvestmentTransaction).filter(
        InvestmentTransaction.user_id == current_user.id,
        InvestmentTransaction.transaction_type == "dividend",
        InvestmentTransaction.created_at >= year_start,
        InvestmentTransaction.created_at <= year_end
    ).all()

    total_dividends = 0.0
    for div in dividends:
        amount = float(div.amount)
        total_dividends += amount
        transactions_list.append(TaxTransactionItem(
            date=div.created_at,
            type="dividend",
            description=f"Dividendo - {div.description or 'Pago de dividendos'}",
            amount=amount,
            currency="MXN",
            reference_id=str(div.id),
        ))

    # 3. Trades del marketplace (ganancias/pérdidas)
    trades = db.query(TokenTrade).filter(
        or_(
            TokenTrade.buyer_id == current_user.id,
            TokenTrade.seller_id == current_user.id
        ),
        TokenTrade.created_at >= year_start,
        TokenTrade.created_at <= year_end
    ).all()

    total_trades = len(trades)
    realized_gains = 0.0
    realized_losses = 0.0
    total_fees = 0.0

    for trade in trades:
        if trade.seller_id == current_user.id:
            # Venta - calcular ganancia/pérdida
            # Nota: En una implementación real, se calcularía el costo base
            net_amount = float(trade.total_amount - trade.seller_fee)
            cost_basis = float(trade.total_amount * 0.9)  # Simplificado
            gain_loss = net_amount - cost_basis

            if gain_loss > 0:
                realized_gains += gain_loss
            else:
                realized_losses += abs(gain_loss)

            total_fees += float(trade.seller_fee)

            transactions_list.append(TaxTransactionItem(
                date=trade.created_at,
                type="trade",
                description=f"Venta de tokens",
                amount=net_amount,
                currency="MXN",
                cost_basis=cost_basis,
                gain_loss=gain_loss,
                reference_id=str(trade.id),
            ))
        else:
            # Compra
            total_fees += float(trade.buyer_fee)
            transactions_list.append(TaxTransactionItem(
                date=trade.created_at,
                type="trade",
                description=f"Compra de tokens",
                amount=-float(trade.total_amount + trade.buyer_fee),
                currency="MXN",
                reference_id=str(trade.id),
            ))

    # 4. Remesas
    remittances_sent = db.query(Remittance).filter(
        Remittance.sender_id == current_user.id,
        Remittance.status == RemittanceStatus.COMPLETED,
        Remittance.created_at >= year_start,
        Remittance.created_at <= year_end
    ).all()

    remittances_received = db.query(Remittance).filter(
        Remittance.receiver_id == current_user.id,
        Remittance.status == RemittanceStatus.COMPLETED,
        Remittance.created_at >= year_start,
        Remittance.created_at <= year_end
    ).all()

    total_remittances_sent = sum(float(r.source_amount) for r in remittances_sent)
    total_remittances_received = sum(float(r.destination_amount) for r in remittances_received)

    for rem in remittances_sent:
        transactions_list.append(TaxTransactionItem(
            date=rem.created_at,
            type="remittance",
            description=f"Remesa enviada - {rem.tracking_number}",
            amount=-float(rem.source_amount),
            currency=rem.source_currency.value if rem.source_currency else "USD",
            reference_id=str(rem.id),
        ))

    for rem in remittances_received:
        transactions_list.append(TaxTransactionItem(
            date=rem.created_at,
            type="remittance",
            description=f"Remesa recibida - {rem.tracking_number}",
            amount=float(rem.destination_amount),
            currency=rem.destination_currency.value if rem.destination_currency else "MXN",
            reference_id=str(rem.id),
        ))

    # Ordenar transacciones por fecha
    transactions_list.sort(key=lambda x: x.date)

    # Construir resumen
    summary = TaxYearSummary(
        year=year,
        total_investments=total_investments,
        total_returns=0.0,  # Se calcularía con retornos de inversión
        total_dividends=total_dividends,
        total_trades=total_trades,
        realized_gains=realized_gains,
        realized_losses=realized_losses,
        net_realized_pnl=realized_gains - realized_losses,
        total_fees_paid=total_fees,
        total_remittances_sent=total_remittances_sent,
        total_remittances_received=total_remittances_received,
    )

    # RFC del usuario (si está en KYC)
    user_rfc = None
    if hasattr(current_user, 'kyc_profile') and current_user.kyc_profile:
        user_rfc = getattr(current_user.kyc_profile, 'rfc', None)

    return TaxReportResponse(
        user_id=current_user.id,
        user_name=f"{current_user.nombre} {current_user.apellido}",
        user_rfc=user_rfc,
        year=year,
        generated_at=datetime.utcnow(),
        summary=summary,
        transactions=transactions_list,
        download_url=None,  # Se generaría PDF bajo demanda
    )


@router.get("/tax-center/{year}/download")
async def download_tax_report(
    year: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Descargar reporte fiscal en PDF."""
    # En una implementación real, generaría un PDF
    # Por ahora, retornamos un mensaje
    return {
        "message": "Reporte en proceso de generación",
        "year": year,
        "format": "pdf",
        "estimated_time_seconds": 30,
    }


# ==================== VERIFICACIÓN SAT 69-B ====================

@router.post("/sat-69b/check", response_model=SAT69BCheckResponse)
async def check_sat_69b(
    data: SAT69BCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verificar si un RFC está en la lista 69-B del SAT.

    La lista 69-B contiene contribuyentes con operaciones simuladas:
    - 69-B: Operaciones inexistentes
    - 69-B Bis: Transmisión indebida de pérdidas fiscales
    """
    import re

    # Validar formato RFC
    rfc = data.rfc.upper().strip()

    # RFC persona física: 4 letras + 6 dígitos + 3 caracteres
    # RFC persona moral: 3 letras + 6 dígitos + 3 caracteres
    rfc_pattern = r'^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$'
    if not re.match(rfc_pattern, rfc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de RFC inválido"
        )

    # En una implementación real, consultaríamos la API del SAT o una base de datos actualizada
    # Por ahora, simulamos la verificación

    # Lista de ejemplo de RFCs en lista 69-B (para pruebas)
    blacklisted_rfcs = {
        "XAXX010101000": {
            "status": "listed_definitive",
            "list_type": "69-B",
            "reason": "Operaciones simuladas - Definitivo",
            "publication_date": datetime(2023, 6, 15),
        },
        "XEXX010101000": {
            "status": "listed_presumed",
            "list_type": "69-B",
            "reason": "Operaciones simuladas - Presunto",
            "publication_date": datetime(2024, 1, 10),
        },
    }

    if rfc in blacklisted_rfcs:
        entry = blacklisted_rfcs[rfc]
        return SAT69BCheckResponse(
            rfc=rfc,
            is_listed=True,
            status=entry["status"],
            list_type=entry["list_type"],
            publication_date=entry["publication_date"],
            reason=entry["reason"],
            checked_at=datetime.utcnow(),
            source="SAT",
        )

    return SAT69BCheckResponse(
        rfc=rfc,
        is_listed=False,
        status="clean",
        list_type=None,
        publication_date=None,
        reason=None,
        checked_at=datetime.utcnow(),
        source="SAT",
    )


@router.get("/sat-69b/recent-checks")
async def get_recent_sat_checks(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener verificaciones recientes de RFC (para el usuario actual)."""
    # En una implementación real, guardaríamos el historial de verificaciones
    return {
        "message": "Historial de verificaciones",
        "checks": [],
        "total": 0,
    }


# ==================== CHAT EN VIVO (INTEGRACIÓN) ====================

@router.get("/chat/config")
async def get_chat_config(
    current_user: User = Depends(get_current_user),
):
    """
    Obtener configuración para el widget de chat en vivo.
    Soporta Crisp, Intercom, y otros proveedores.
    """
    # En producción, estos valores vendrían de variables de entorno
    import os

    provider = os.getenv("LIVE_CHAT_PROVIDER", "crisp")

    if provider == "crisp":
        return {
            "provider": "crisp",
            "website_id": os.getenv("CRISP_WEBSITE_ID", ""),
            "user_data": {
                "email": current_user.email,
                "nickname": f"{current_user.nombre} {current_user.apellido}",
                "user_id": str(current_user.id),
            },
            "settings": {
                "locale": "es",
                "color_theme": "blue",
            }
        }
    elif provider == "intercom":
        return {
            "provider": "intercom",
            "app_id": os.getenv("INTERCOM_APP_ID", ""),
            "user_data": {
                "email": current_user.email,
                "name": f"{current_user.nombre} {current_user.apellido}",
                "user_id": str(current_user.id),
                "created_at": int(current_user.created_at.timestamp()) if current_user.created_at else None,
            },
            "settings": {
                "alignment": "right",
                "horizontal_padding": 20,
                "vertical_padding": 20,
            }
        }
    else:
        return {
            "provider": "none",
            "message": "Chat en vivo no configurado",
        }
