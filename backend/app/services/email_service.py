"""
Servicio de envío de emails usando SendGrid.
"""
import logging
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Servicio para envío de emails transaccionales."""

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self.from_name = settings.SENDGRID_FROM_NAME
        self.frontend_url = settings.FRONTEND_URL
        self._client: Optional[SendGridAPIClient] = None

    @property
    def client(self) -> SendGridAPIClient:
        """Lazy initialization del cliente SendGrid."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("SENDGRID_API_KEY no configurado")
            self._client = SendGridAPIClient(self.api_key)
        return self._client

    def is_configured(self) -> bool:
        """Verifica si el servicio está configurado."""
        return bool(self.api_key)

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> bool:
        """
        Envía un email.

        Returns:
            True si se envió exitosamente, False en caso contrario.
        """
        if not self.is_configured():
            logger.warning("SendGrid no configurado. Email no enviado.")
            return False

        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=HtmlContent(html_content)
            )

            if plain_content:
                message.add_content(Content("text/plain", plain_content))

            response = self.client.send(message)

            if response.status_code in (200, 201, 202):
                logger.info(f"Email enviado exitosamente a {to_email}")
                return True
            else:
                logger.error(f"Error enviando email: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error enviando email a {to_email}: {str(e)}")
            return False

    def send_password_reset_email(self, to_email: str, reset_token: str) -> bool:
        """
        Envía email de recuperación de contraseña.

        Args:
            to_email: Email del destinatario
            reset_token: Token JWT para reset

        Returns:
            True si se envió exitosamente
        """
        reset_url = f"{self.frontend_url}/reset-password?token={reset_token}"

        subject = "Recupera tu contraseña - FinCore"

        html_content = self._get_password_reset_template(reset_url)

        plain_content = f"""
Recuperación de contraseña - FinCore

Recibimos una solicitud para restablecer tu contraseña.

Haz clic en el siguiente enlace para crear una nueva contraseña:
{reset_url}

Este enlace expirará en 1 hora.

Si no solicitaste este cambio, puedes ignorar este mensaje.

- El equipo de FinCore
        """

        return self._send_email(to_email, subject, html_content, plain_content.strip())

    def _get_password_reset_template(self, reset_url: str) -> str:
        """Genera el template HTML para reset de contraseña."""
        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Recupera tu contraseña</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f4f4f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">FinCore</h1>
                            <p style="margin: 8px 0 0; color: #bfdbfe; font-size: 14px;">Sistema Financiero</p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <h2 style="margin: 0 0 16px; color: #1f2937; font-size: 22px; font-weight: 600;">
                                Recupera tu contraseña
                            </h2>

                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                Recibimos una solicitud para restablecer la contraseña de tu cuenta.
                                Haz clic en el botón de abajo para crear una nueva contraseña.
                            </p>

                            <!-- Button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{reset_url}"
                                           style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 8px; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);">
                                            Restablecer contraseña
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 24px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                Este enlace expirará en <strong>1 hora</strong>.
                            </p>

                            <p style="margin: 16px 0 0; color: #6b7280; font-size: 14px; line-height: 1.6;">
                                Si no solicitaste este cambio, puedes ignorar este mensaje de forma segura.
                            </p>

                            <!-- Link alternativo -->
                            <div style="margin-top: 32px; padding: 16px; background-color: #f9fafb; border-radius: 8px;">
                                <p style="margin: 0 0 8px; color: #6b7280; font-size: 12px;">
                                    Si el botón no funciona, copia y pega este enlace en tu navegador:
                                </p>
                                <p style="margin: 0; word-break: break-all;">
                                    <a href="{reset_url}" style="color: #3b82f6; font-size: 12px; text-decoration: none;">
                                        {reset_url}
                                    </a>
                                </p>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; background-color: #f9fafb; border-radius: 0 0 12px 12px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; color: #9ca3af; font-size: 12px; text-align: center;">
                                Este es un mensaje automático de FinCore. Por favor no respondas a este correo.
                            </p>
                            <p style="margin: 8px 0 0; color: #9ca3af; font-size: 12px; text-align: center;">
                                &copy; 2024 FinCore. Todos los derechos reservados.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """


    def send_new_device_notification(
        self,
        email: str,
        device_name: str,
        location: str,
        ip_address: str,
        login_time: str
    ) -> bool:
        """
        Envía notificación de nuevo dispositivo detectado.

        Args:
            email: Email del usuario
            device_name: Nombre del dispositivo (ej: "Chrome en Windows")
            location: Ubicación (ej: "Ciudad de México, MX")
            ip_address: Dirección IP
            login_time: Fecha/hora del login

        Returns:
            True si se envió exitosamente
        """
        subject = "Nuevo inicio de sesión detectado - FinCore"

        html_content = self._get_new_device_template(
            device_name, location, ip_address, login_time
        )

        plain_content = f"""
Alerta de seguridad - FinCore

Detectamos un nuevo inicio de sesión en tu cuenta.

Dispositivo: {device_name}
Ubicación: {location}
Dirección IP: {ip_address}
Fecha y hora: {login_time}

Si fuiste tú, puedes ignorar este mensaje.

Si NO reconoces esta actividad, te recomendamos:
1. Cambiar tu contraseña inmediatamente
2. Activar autenticación de dos factores (2FA)
3. Revisar tus sesiones activas y cerrar las que no reconozcas

- El equipo de seguridad de FinCore
        """

        return self._send_email(email, subject, html_content, plain_content.strip())

    def _get_new_device_template(
        self,
        device_name: str,
        location: str,
        ip_address: str,
        login_time: str
    ) -> str:
        """Genera el template HTML para notificación de nuevo dispositivo."""
        security_url = f"{self.frontend_url}/security"

        return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuevo inicio de sesión</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f5;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f4f4f5;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center; background: linear-gradient(135deg, #dc2626 0%, #f97316 100%); border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">FinCore</h1>
                            <p style="margin: 8px 0 0; color: #fecaca; font-size: 14px;">Alerta de Seguridad</p>
                        </td>
                    </tr>

                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <div style="padding: 16px; background-color: #fef2f2; border-radius: 8px; margin-bottom: 24px; border-left: 4px solid #dc2626;">
                                <p style="margin: 0; color: #991b1b; font-size: 16px; font-weight: 600;">
                                    Nuevo inicio de sesión detectado
                                </p>
                            </div>

                            <p style="margin: 0 0 24px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                Detectamos un inicio de sesión desde un nuevo dispositivo en tu cuenta.
                            </p>

                            <!-- Device Info -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f9fafb; border-radius: 8px; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                            <tr>
                                                <td style="padding: 8px 0;">
                                                    <span style="color: #6b7280; font-size: 14px;">Dispositivo:</span>
                                                    <span style="color: #1f2937; font-size: 14px; font-weight: 600; float: right;">{device_name}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; border-top: 1px solid #e5e7eb;">
                                                    <span style="color: #6b7280; font-size: 14px;">Ubicación:</span>
                                                    <span style="color: #1f2937; font-size: 14px; font-weight: 600; float: right;">{location}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; border-top: 1px solid #e5e7eb;">
                                                    <span style="color: #6b7280; font-size: 14px;">Dirección IP:</span>
                                                    <span style="color: #1f2937; font-size: 14px; font-weight: 600; float: right;">{ip_address}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; border-top: 1px solid #e5e7eb;">
                                                    <span style="color: #6b7280; font-size: 14px;">Fecha y hora:</span>
                                                    <span style="color: #1f2937; font-size: 14px; font-weight: 600; float: right;">{login_time}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0 0 16px; color: #4b5563; font-size: 16px; line-height: 1.6;">
                                <strong>Si fuiste tú</strong>, puedes ignorar este mensaje.
                            </p>

                            <p style="margin: 0 0 24px; color: #dc2626; font-size: 16px; line-height: 1.6; font-weight: 600;">
                                Si NO reconoces esta actividad, actúa inmediatamente:
                            </p>

                            <!-- Button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{security_url}"
                                           style="display: inline-block; padding: 16px 32px; background: linear-gradient(135deg, #dc2626 0%, #f97316 100%); color: #ffffff; text-decoration: none; font-size: 16px; font-weight: 600; border-radius: 8px; box-shadow: 0 4px 12px rgba(220, 38, 38, 0.4);">
                                            Revisar seguridad de mi cuenta
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <!-- Tips -->
                            <div style="margin-top: 24px; padding: 16px; background-color: #eff6ff; border-radius: 8px;">
                                <p style="margin: 0 0 12px; color: #1e40af; font-size: 14px; font-weight: 600;">
                                    Recomendaciones de seguridad:
                                </p>
                                <ul style="margin: 0; padding-left: 20px; color: #1e40af; font-size: 14px; line-height: 1.8;">
                                    <li>Cambia tu contraseña si no reconoces este acceso</li>
                                    <li>Activa autenticación de dos factores (2FA)</li>
                                    <li>Revisa y cierra sesiones que no reconozcas</li>
                                </ul>
                            </div>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px 40px; background-color: #f9fafb; border-radius: 0 0 12px 12px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; color: #9ca3af; font-size: 12px; text-align: center;">
                                Este es un mensaje automático de seguridad de FinCore.
                            </p>
                            <p style="margin: 8px 0 0; color: #9ca3af; font-size: 12px; text-align: center;">
                                &copy; 2024 FinCore. Todos los derechos reservados.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        """


# Instancia singleton
email_service = EmailService()
