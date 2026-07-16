# app/services/email_template_service.py
"""
Service d'envoi d'emails avec templates HTML (Jinja2)
Similaire à Thymeleaf en Java Spring Boot
"""
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config.settings import settings
from app.core.logger import logger


class EmailTemplateService:
    """
    Service d'envoi d'emails avec templates HTML

    Utilise Jinja2 pour le rendu des templates (comme Thymeleaf en Java)
    """

    def __init__(self):
        # Configurer Jinja2
        template_dir = Path(__file__).parent.parent / "templates" / "emails"
        template_dir.mkdir(parents=True, exist_ok=True)

        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Rendre un template avec des variables (binding)

        Args:
            template_name: Nom du fichier template (ex: "verification.html")
            context: Dictionnaire de variables à injecter

        Returns:
            HTML rendu avec les variables
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Erreur rendu template {template_name}: {str(e)}")
            raise

    def send_email_with_template(
            self,
            to_email: str,
            subject: str,
            template_name: str,
            context: Dict[str, Any]
    ) -> bool:
        """
        Envoyer un email avec un template HTML

        Args:
            to_email: Email destinataire
            subject: Sujet de l'email
            template_name: Nom du template (ex: "verification.html")
            context: Variables pour le template

        Returns:
            True si envoyé avec succès
        """
        try:
            # Vérifier SMTP configuré
            if not settings.SMTP_HOST or not settings.SMTP_USER:
                logger.warning("SMTP non configuré")
                return False

            # Rendre le template HTML
            html_body = self.render_template(template_name, context)

            # Créer le message
            message = MIMEMultipart("alternative")
            message["From"] = settings.EMAIL_FROM
            message["To"] = to_email
            message["Subject"] = subject

            # Ajouter le HTML
            message.attach(MIMEText(html_body, "html"))

            # Envoyer via SMTP
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)

            logger.info(f"✉️ Email template envoyé à {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur envoi email template: {str(e)}")
            return False

    # ==================== EMAILS SPÉCIFIQUES ====================

    def send_verification_email(
            self,
            email: str,
            user_name: str,
            token: str
    ) -> bool:
        """Envoyer email de vérification avec template"""

        mobile_link = f"{settings.MOBILE_DEEP_LINK_SCHEME}://verify-email?token={token}"
        web_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"

        context = {
            "user_name": user_name,
            "mobile_link": mobile_link,
            "web_link": web_link,
            "token_preview": token[:20],
            "app_name": settings.APP_NAME,
            "support_email": "support@marketplace.com",
            "year": 2025
        }

        return self.send_email_with_template(
            to_email=email,
            subject="Vérifiez votre email - MarketPlace B2B",
            template_name="verification_email.html",
            context=context
        )

    def send_welcome_email(
            self,
            email: str,
            user_name: str,
            user_type: str
    ) -> bool:
        """Envoyer email de bienvenue avec template"""

        context = {
            "user_name": user_name,
            "user_type": user_type,
            "app_name": settings.APP_NAME,
            "login_url": f"{settings.FRONTEND_URL}/login",
            "support_email": "support@marketplace.com",
            "year": 2025
        }

        return self.send_email_with_template(
            to_email=email,
            subject="Bienvenue sur MarketPlace B2B !",
            template_name="welcome_email.html",
            context=context
        )

    def send_password_reset_email(
            self,
            email: str,
            user_name: str,
            reset_token: str
    ) -> bool:
        """Envoyer email de réinitialisation mot de passe"""

        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        context = {
            "user_name": user_name,
            "reset_link": reset_link,
            "app_name": settings.APP_NAME,
            "support_email": "support@marketplace.com",
            "year": 2025
        }

        return self.send_email_with_template(
            to_email=email,
            subject="Réinitialisation de mot de passe",
            template_name="password_reset.html",
            context=context
        )

    def send_password_reset_code_email(
            self,
            email: str,
            user_name: str,
            code: str,
            ttl_minutes: int = 15,
    ) -> bool:
        """Envoyer le code à 6 chiffres de réinitialisation.

        Remplace le lien pour le parcours mobile : l'app n'a ni domaine web ni
        deep link, et l'utilisateur recopie le code sans quitter l'application.
        Le lien (`send_password_reset_email`) reste disponible pour la future web.
        """
        context = {
            "user_name": user_name,
            "code": code,
            "ttl_minutes": ttl_minutes,
            "app_name": settings.APP_NAME,
            "support_email": "support@marketplace.com",
            "year": datetime.now().year,
        }

        return self.send_email_with_template(
            to_email=email,
            subject=f"Votre code de réinitialisation : {code}",
            template_name="password_reset_code.html",
            context=context,
        )


# ==================== TEMPLATES HTML ====================

"""
Structure du projet:

app/
├── templates/
│   └── emails/
│       ├── base.html              # Template de base (layout)
│       ├── verification.html      # Email de vérification
│       ├── welcome.html           # Email de bienvenue
│       └── password_reset.html    # Reset password
├── services/
│   └── email_template_service.py
"""