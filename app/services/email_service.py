# app/services/email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List

from app.config.settings import settings
from app.core.logger import logger


class EmailService:
    """Service d'envoi d'emails via SMTP"""

    @staticmethod
    def send_email(
            to_email: str,
            subject: str,
            body: str,
            html_body: str = None
    ) -> bool:
        """
        Envoyer un email

        Args:
            to_email: Email du destinataire
            subject: Sujet de l'email
            body: Corps de l'email (texte brut)
            html_body: Corps HTML (optionnel)

        Returns:
            True si envoyé avec succès
        """
        try:
            # Créer le message
            message = MIMEMultipart("alternative")
            message["From"] = settings.EMAIL_FROM
            message["To"] = to_email
            message["Subject"] = subject

            # Ajouter le corps texte
            message.attach(MIMEText(body, "plain"))

            # Ajouter le corps HTML si fourni
            if html_body:
                message.attach(MIMEText(html_body, "html"))

            # Se connecter au serveur SMTP
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()  # Sécuriser la connexion
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)

            logger.info(f"Email envoyé à {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Erreur envoi email à {to_email}: {str(e)}")
            return False

    @staticmethod
    def send_verification_email(email: str, verification_code: str) -> bool:
        """Envoyer un email de vérification"""
        subject = "Vérifiez votre email - MarketPlace B2B"

        body = f"""
        Bonjour,

        Merci de vous être inscrit sur MarketPlace B2B !

        Votre code de vérification est : {verification_code}

        Ce code expire dans 24 heures.

        Cordialement,
        L'équipe MarketPlace B2B
        """

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Vérifiez votre email</h2>
                <p>Bonjour,</p>
                <p>Merci de vous être inscrit sur <strong>MarketPlace B2B</strong> !</p>
                <p>Votre code de vérification est :</p>
                <h1 style="color: #4CAF50; letter-spacing: 5px;">{verification_code}</h1>
                <p>Ce code expire dans <strong>24 heures</strong>.</p>
                <br>
                <p>Cordialement,<br>L'équipe MarketPlace B2B</p>
            </body>
        </html>
        """

        return EmailService.send_email(email, subject, body, html_body)

    @staticmethod
    def send_password_reset_email(email: str, reset_token: str) -> bool:
        """Envoyer un email de réinitialisation de mot de passe"""
        subject = "Réinitialisation de mot de passe - MarketPlace B2B"

        reset_link = f"https://votre-site.com/reset-password?token={reset_token}"

        body = f"""
        Bonjour,

        Vous avez demandé la réinitialisation de votre mot de passe.

        Cliquez sur le lien suivant pour réinitialiser votre mot de passe :
        {reset_link}

        Ce lien expire dans 1 heure.

        Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.

        Cordialement,
        L'équipe MarketPlace B2B
        """

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Réinitialisation de mot de passe</h2>
                <p>Bonjour,</p>
                <p>Vous avez demandé la réinitialisation de votre mot de passe.</p>
                <p>
                    <a href="{reset_link}" 
                       style="background-color: #4CAF50; 
                              color: white; 
                              padding: 15px 32px; 
                              text-decoration: none; 
                              display: inline-block; 
                              border-radius: 4px;">
                        Réinitialiser mon mot de passe
                    </a>
                </p>
                <p>Ce lien expire dans <strong>1 heure</strong>.</p>
                <p>Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.</p>
                <br>
                <p>Cordialement,<br>L'équipe MarketPlace B2B</p>
            </body>
        </html>
        """

        return EmailService.send_email(email, subject, body, html_body)

    @staticmethod
    def send_welcome_email(email: str, user_name: str) -> bool:
        """Envoyer un email de bienvenue"""
        subject = "Bienvenue sur MarketPlace B2B !"

        body = f"""
        Bonjour {user_name},

        Bienvenue sur MarketPlace B2B !

        Votre compte a été créé avec succès.

        Vous pouvez maintenant vous connecter et commencer à utiliser notre plateforme.

        Cordialement,
        L'équipe MarketPlace B2B
        """

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Bienvenue sur MarketPlace B2B !</h2>
                <p>Bonjour <strong>{user_name}</strong>,</p>
                <p>Votre compte a été créé avec succès. 🎉</p>
                <p>Vous pouvez maintenant vous connecter et commencer à utiliser notre plateforme.</p>
                <br>
                <p>Cordialement,<br>L'équipe MarketPlace B2B</p>
            </body>
        </html>
        """

        return EmailService.send_email(email, subject, body, html_body)