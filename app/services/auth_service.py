# app/services/auth_service.py
"""
Service d'authentification - TOUTE la logique métier ici
Repository = requêtes uniquement, Service = logique métier
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

import jwt
import bcrypt

from app.mappers.users_mapper import UsersMapper
from app.repositories.user_repo import UserRepository
from app.repositories.company_profile_repo import CompanyProfileRepository
from app.repositories.password_reset_code_repo import PasswordResetCodeRepository
from app.models.user_entity import UserEntity
from app.schemas.base import ResponseBase
from app.schemas.user import UserCreateSchema, UserLoginSchema, UserSchema, TokenResponse
from app.core.exceptions import UnauthorizedError, ValidationError, DuplicateError
from app.core.logger import logger
from app.config.settings import settings


class AuthService:
    """
    Service d'authentification

    Gère l'inscription, la connexion et la génération de tokens JWT.
    Toute la logique métier est ici, les repositories font uniquement les requêtes SQL.
    """

    def __init__(
            self,
            user_repo: UserRepository,
            profile_repo: CompanyProfileRepository,
            reset_code_repo: Optional["PasswordResetCodeRepository"] = None,
    ):
        self.user_repo = user_repo
        self.profile_repo = profile_repo
        # Codes de réinitialisation à 6 chiffres. Optionnel : les appelants qui ne
        # font pas de reset (scripts, tests) n'ont pas à le fournir.
        self.reset_code_repo = reset_code_repo

    # ==================== GESTION DES MOTS DE PASSE ====================

    @staticmethod
    def _sanitize_password(password: str) -> bytes:
        """
        Normaliser le mot de passe pour bcrypt.

        bcrypt ne traite que les 72 premiers octets et, depuis la v4, refuse les
        octets NUL (les anciennes versions tronquaient silencieusement au 1er NUL,
        comportement d'une chaîne C). On reproduit ce comportement pour :
          - éviter une erreur 500 (NullPasswordError) sur des entrées contenant \\x00 ;
          - rester compatible avec les hashs déjà créés sous l'ancienne version.
        """
        raw = password.encode("utf-8") if isinstance(password, str) else bytes(password)
        nul_index = raw.find(b"\x00")
        if nul_index != -1:
            raw = raw[:nul_index]
        return raw[:72]

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hasher un mot de passe avec bcrypt

        Args:
            password: Mot de passe en clair

        Returns:
            Hash bcrypt du mot de passe
        """
        hashed = bcrypt.hashpw(AuthService._sanitize_password(password), bcrypt.gensalt())
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Vérifier un mot de passe contre son hash

        Args:
            plain_password: Mot de passe en clair
            hashed_password: Hash stocké en BD

        Returns:
            True si le mot de passe correspond
        """
        try:
            return bcrypt.checkpw(
                AuthService._sanitize_password(plain_password),
                hashed_password.encode("utf-8"),
            )
        except ValueError:
            # Hash mal formé / non-bcrypt en base
            return False

    # ==================== GESTION DES TOKENS JWT ====================

    @staticmethod
    def default_roles_for(user_type: str) -> list[str]:
        """Rôles attribués par défaut selon le type d'inscription (T5).

        - supplier → {supplier, buyer} (un vendeur est aussi acheteur)
        - buyer    → {buyer}
        - admin    → {admin}
        """
        if user_type == "supplier":
            return ["buyer", "supplier"]
        return [user_type]

    def create_access_token(
        self,
        user_id: int,
        user_type: str,
        roles: list[str] | None = None,
    ) -> str:
        """
        Créer un token JWT d'accès

        Args:
            user_id: ID de l'utilisateur
            user_type: Type d'utilisateur (compat legacy : supplier/buyer/admin)
            roles: Liste des rôles de l'utilisateur (T5). Si absente, dérivée du
                   user_type.

        Returns:
            Token JWT encodé
        """
        expiration = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

        if roles is None:
            roles = self.default_roles_for(user_type)

        payload = {
            "user_id": str(user_id),
            "type": user_type,      # conservé pour compat (mobile pas encore migré)
            "roles": roles,         # T5 : liste de rôles, source des guards
            "exp": expiration,
            "iat": datetime.utcnow()
        }

        return jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )

    def decode_token(self, token: str) -> dict:
        """
        Décoder et valider un token JWT

        Args:
            token: Token JWT à décoder

        Returns:
            Payload du token

        Raises:
            UnauthorizedError: Si le token est invalide ou expiré
        """
        try:
            return jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Token expiré")
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Token invalide")

    def create_verification_token(self, user_id: int, email: str) -> str:
        """
        Créer un token de vérification d'email

        Args:
            user_id: ID de l'utilisateur
            email: Email à vérifier

        Returns:
            Token JWT pour vérification email (expire dans 24h)
        """
        expiration = datetime.utcnow() + timedelta(hours=24)

        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "email_verification",
            "exp": expiration,
            "iat": datetime.utcnow()
        }

        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def create_password_reset_token(self, user_id: int, email: str) -> str:
        """
        Créer un token de réinitialisation de mot de passe

        Args:
            user_id: ID de l'utilisateur
            email: Email de l'utilisateur

        Returns:
            Token JWT pour réinitialisation (expire dans 1 heure)
        """
        expiration = datetime.utcnow() + timedelta(hours=1)

        payload = {
            "sub": str(user_id),
            "email": email,
            "type": "password_reset",
            "exp": expiration,
            "iat": datetime.utcnow()
        }

        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # ==================== VALIDATIONS MÉTIER ====================

    def _validate_registration_data(self, data: UserCreateSchema) -> None:
        """
        Valider les données d'inscription (logique métier)

        Args:
            data: Données d'inscription à valider

        Raises:
            ValidationError: Si validation échoue
            DuplicateError: Si email/phone existe déjà
        """
        # Règle métier: company_name obligatoire pour supplier/buyer
        if data.user_type.value != "admin" and not data.company_name:
            raise ValidationError(
                "Le nom de l'entreprise est obligatoire pour les fournisseurs et acheteurs"
            )

        # Vérifier l'unicité de l'email
        if self.user_repo.get_by_email(data.email):
            raise DuplicateError(f"Un utilisateur avec l'email '{data.email}' existe déjà")

        # Vérifier l'unicité du téléphone
        if self.user_repo.get_by_phone(data.phone):
            raise DuplicateError(f"Un utilisateur avec le téléphone '{data.phone}' existe déjà")

    def _validate_user_status(self, user: UserEntity) -> None:
        """
        Valider que l'utilisateur peut se connecter (logique métier)

        Args:
            user: Utilisateur à valider

        Raises:
            UnauthorizedError: Si le compte est suspendu ou inactif
        """
        if user.status.value == "suspended":
            raise UnauthorizedError("Votre compte est suspendu. Contactez le support.")

        if user.status.value == "inactive":
            raise UnauthorizedError("Votre compte est inactif. Veuillez le réactiver.")

    # ==================== INSCRIPTION ====================

    def register_user(self, data: UserCreateSchema) -> ResponseBase[UserSchema]:
        """
        Inscrire un nouvel utilisateur (TOUTE la logique métier ici)

        Args:
            data: Données d'inscription validées par Pydantic

        Returns:
            UserSchema de l'utilisateur créé

        Raises:
            ValidationError: Si les règles métier ne sont pas respectées
            DuplicateError: Si l'email ou le téléphone existe déjà
        """
        logger.info(f"Tentative d'inscription: {data.email}")

        # 1. Validation métier (règles business)
        self._validate_registration_data(data)

        # 2. Hasher le mot de passe (logique métier)
        hashed_password = self.hash_password(data.password)

        # 3. Créer l'utilisateur (délégation au repository pour requête SQL)
        user = self.user_repo.create(
            email=data.email,
            phone=data.phone,
            password_hash=hashed_password,
            user_type=data.user_type.value,
            status="pending"
        )

        logger.info(f"User créé avec ID: {user.id}")

        # 3bis. Attribuer les rôles (T5). Un supplier obtient aussi buyer.
        self.user_repo.add_roles(user.id, self.default_roles_for(data.user_type.value))
        logger.info(f"Rôles attribués à user {user.id}: {self.default_roles_for(data.user_type.value)}")

        # 4. Créer le profil entreprise si nécessaire (logique conditionnelle métier)
        if data.company_name or data.contact_person or data.city:
            self.profile_repo.create(
                user_id=user.id,
                company_name=data.company_name or "",
                contact_person=data.contact_person,
                city=data.city
            )
            logger.info(f"Profil entreprise créé pour user {user.id}")

        logger.info(f"Utilisateur {user.id} inscrit avec succès")

        # 5. Récupérer avec profil et convertir en schéma de réponse
        user_with_profile = self.user_repo.get_with_profile(user.id)

        # 6. Générer token de vérification
        verification_token = self.create_verification_token(user.id, user.email)

        # 7. Envoyer email de vérification avec template
        try:
            from app.services.email_services_v2 import EmailTemplateService
            email_service = EmailTemplateService()
            user_name = data.company_name or data.contact_person or "Utilisateur"
            email_service.send_verification_email(user.email, user_name, verification_token)
            logger.info(f"Email de vérification envoyé à {user.email}")
        except Exception as e:
            logger.error(f"Erreur envoi email vérification: {str(e)}")

        return ResponseBase[UserSchema](
            success=True,
            message="Inscription réussie avec succès",
            item=UsersMapper.entity_to_schema(user_with_profile)
        )

    # ==================== AUTHENTIFICATION ====================

    def authenticate_user(self, credentials: UserLoginSchema) -> ResponseBase[TokenResponse]:
        """
        Authentifier un utilisateur (TOUTE la logique métier ici)

        Args:
            credentials: Identifiant (email/phone) et mot de passe

        Returns:
            TokenResponse avec token JWT et infos utilisateur

        Raises:
            UnauthorizedError: Si les identifiants sont invalides ou compte suspendu
        """
        logger.info(f"Tentative de connexion: {credentials.identifier}")

        # 1. Récupérer l'utilisateur (requête SQL via repository)
        user = self.user_repo.get_by_identifier(credentials.identifier)

        if not user:
            logger.warning(f"Utilisateur non trouvé: {credentials.identifier}")
            raise UnauthorizedError("Identifiant ou mot de passe incorrect")

        # 2. Vérifier le mot de passe (logique métier)
        if not self.verify_password(credentials.password, user.password_hash):
            logger.warning(f"Mot de passe incorrect pour: {credentials.identifier}")
            raise UnauthorizedError("Identifiant ou mot de passe incorrect")

        # 3. Valider le statut du compte (règle métier)
        self._validate_user_status(user)

        # 4. Générer le token JWT (logique métier) — inclut la liste de rôles (T5).
        #    Fallback role_names si la table user_roles n'est pas encore peuplée.
        roles = self.user_repo.get_roles(user.id) or user.role_names
        token = self.create_access_token(user.id, user.user_type.value, roles)

        # 5. Mettre à jour la dernière connexion (requête SQL via repository)
        self.user_repo.update_last_login(user.id)

        logger.info(f"Utilisateur {user.id} connecté avec succès")

        # 6. Retourner le token et les infos utilisateur

        return ResponseBase[TokenResponse](
            success=True,
            message="Connexion réussie avec succès",
            item=TokenResponse(
                access_token=token,
                token_type="bearer",
                user=UsersMapper.entity_to_schema(user)
            )
        )

    # ==================== VÉRIFICATION EMAIL ====================

    def verify_email(self, token: str) -> ResponseBase[UserSchema]:
        """
        Vérifier l'email d'un utilisateur avec un token

        Args:
            token: Token JWT de vérification

        Returns:
            UserSchema de l'utilisateur vérifié

        Raises:
            UnauthorizedError: Si le token est invalide ou expiré
            ValidationError: Si l'email est déjà vérifié
        """
        logger.info("Tentative de vérification d'email")

        # 1. Décoder le token
        try:
            payload = self.decode_token(token)
        except UnauthorizedError as e:
            logger.warning(f"Token de vérification invalide: {str(e)}")
            raise

        # 2. Vérifier que c'est bien un token de vérification
        if payload.get("type") != "email_verification":
            raise UnauthorizedError("Type de token invalide")

        user_id = int(payload.get("sub"))
        email = payload.get("email")

        # 3. Récupérer l'utilisateur
        user = self.user_repo.get_by_id(user_id)

        # 4. Vérifier que l'email correspond
        if user.email != email:
            raise ValidationError("Email ne correspond pas au token")

        # 5. Vérifier si déjà vérifié
        if user.email_verified:
            logger.info(f"Email déjà vérifié pour user {user_id}")
            raise ValidationError("Email déjà vérifié")

        # 6. Marquer l'email comme vérifié et activer le compte
        self.user_repo.update(
            user_id,
            email_verified=True,
            status="active"  # Activer le compte
        )

        logger.info(f"Email vérifié pour user {user_id}")

        # 7. Envoyer email de bienvenue
        try:
            from app.services.email_service import EmailService
            user_name = user.company_profile.company_name if user.company_profile else "Utilisateur"
            EmailService.send_welcome_email(user.email, user_name)
            logger.info(f"Email de bienvenue envoyé à {user.email}")
        except Exception as e:
            logger.error(f"Erreur envoi email bienvenue: {str(e)}")

        # 8. Retourner l'utilisateur mis à jour
        user_updated = self.user_repo.get_with_profile(user_id)

        return ResponseBase[UserSchema](
            success=True,
            message="Vérification d'email réussie avec succès",
            item=UsersMapper.entity_to_schema(user_updated)
        )

    def resend_verification_email(self, email: str) -> dict:
        """
        Renvoyer l'email de vérification

        Args:
            email: Email de l'utilisateur

        Returns:
            Message de confirmation

        Raises:
            ValidationError: Si l'utilisateur n'existe pas ou email déjà vérifié
        """
        logger.info(f"Demande de renvoi d'email de vérification: {email}")

        # 1. Récupérer l'utilisateur
        user = self.user_repo.get_by_email(email)

        if not user:
            raise ValidationError("Aucun compte associé à cet email")

        # 2. Vérifier si déjà vérifié
        if user.email_verified:
            raise ValidationError("Email déjà vérifié")

        # 3. Générer nouveau token
        verification_token = self.create_verification_token(user.id, user.email)

        # 4. Envoyer email
        try:
            from app.services.email_services_v2 import EmailTemplateService
            user_name = user.company_profile.company_name if user.company_profile else "Utilisateur"
            EmailTemplateService.send_verification_email(user.email, user_name, verification_token)
            logger.info(f"Email de vérification renvoyé à {user.email}")
        except Exception as e:
            logger.error(f"Erreur envoi email: {str(e)}")
            raise ValidationError("Erreur lors de l'envoi de l'email")

        return {"success":True, "message": "Email de vérification envoyé"}

    # ==================== RÉINITIALISATION MOT DE PASSE ====================

    def forgot_password(self, email: str) -> dict:
        """
        Demande de réinitialisation de mot de passe

        Args:
            email: Email de l'utilisateur

        Returns:
            Message de confirmation

        Note:
            Pour des raisons de sécurité, on retourne toujours un succès
            même si l'email n'existe pas (évite l'énumération d'emails)
        """
        logger.info(f"Demande de réinitialisation mot de passe: {email}")

        # Réponse générique systématique pour ne pas révéler l'existence d'un compte
        generic_response = {
            "success": True,
            "message": "Si cet email existe, un lien de réinitialisation a été envoyé"
        }

        # 1. Récupérer l'utilisateur
        user = self.user_repo.get_by_email(email)

        # 2. Si l'utilisateur n'existe pas ou compte non actif → on retourne
        #    silencieusement la réponse générique (anti-énumération d'emails)
        if not user:
            logger.info(f"Email non trouvé: {email} - réponse générique envoyée")
            return generic_response

        if user.status.value == "suspended":
            logger.warning(f"Tentative reset sur compte suspendu: {email} - réponse générique envoyée")
            return generic_response

        # 3. Émettre un code à 6 chiffres.
        #
        # Et non plus un lien : l'app mobile n'a ni domaine web ni deep link
        # configuré, et un JWT ne se recopie pas à la main. L'utilisateur saisit
        # le code dans l'app, sans jamais la quitter.
        code = self._generate_reset_code()
        self._store_reset_code(user.id, code)

        # 4. Envoyer l'email
        try:
            from app.services.email_services_v2 import EmailTemplateService
            email_service = EmailTemplateService()
            user_name = user.company_profile.company_name if user.company_profile else "Utilisateur"
            email_service.send_password_reset_code_email(user.email, user_name, code)
            logger.info(f"Code de réinitialisation envoyé à {user.email}")
        except Exception as e:
            logger.error(f"Erreur envoi email reset: {str(e)}")
            # On ne révèle pas l'erreur à l'utilisateur

        return generic_response

    # ---------- Codes de réinitialisation (6 chiffres) ----------

    #: Assez court pour être recopié depuis un email, assez long pour résister au
    #: hasard une fois les tentatives plafonnées (cf. MAX_RESET_ATTEMPTS).
    RESET_CODE_TTL_MINUTES = 15
    MAX_RESET_ATTEMPTS = 5

    @staticmethod
    def _generate_reset_code() -> str:
        """Code à 6 chiffres, tiré d'une source cryptographique.

        `secrets` et non `random` : ce dernier est un Mersenne Twister, dont l'état
        se reconstitue à partir de quelques tirages — un attaquant pourrait alors
        prédire les codes des autres utilisateurs.
        """
        return f"{secrets.randbelow(1_000_000):06d}"

    def _store_reset_code(self, user_id: int, code: str) -> None:
        """Stocker le code, haché, et invalider les précédents."""
        if not self.reset_code_repo:
            raise Exception("Repository des codes de réinitialisation non injecté")

        self.reset_code_repo.invalidate_all_for_user(user_id)
        self.reset_code_repo.create(
            user_id=user_id,
            code_hash=self.hash_password(code),   # bcrypt : le code est un secret
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=self.RESET_CODE_TTL_MINUTES),
            attempts=0,
            is_active=True,
        )

    def verify_reset_code(self, email: str, code: str) -> dict:
        """Échanger un code valide contre un token de réinitialisation.

        Le code ne circule pas jusqu'à l'écran du nouveau mot de passe : on le
        convertit en JWT court (1 h), et `reset_password` reste inchangé. Le code
        est consommé ici — il ne peut plus resservir, même si l'utilisateur
        abandonne à l'étape suivante.
        """
        if not self.reset_code_repo:
            raise Exception("Repository des codes de réinitialisation non injecté")

        invalid = UnauthorizedError("Code invalide ou expiré. Demandez un nouveau code.")

        user = self.user_repo.get_by_email(email)
        if not user:
            # Même message que pour un mauvais code : sinon la route dirait quels
            # emails existent, ce que `forgot_password` prend soin de taire.
            raise invalid

        entry = self.reset_code_repo.get_active_for_user(user.id)
        if not entry:
            raise invalid

        # Plafond d'essais AVANT vérification : sans lui, un code à 6 chiffres
        # tombe par force brute en quelques minutes.
        if entry.attempts >= self.MAX_RESET_ATTEMPTS:
            self.reset_code_repo.update(entry.id, is_active=False)
            logger.warning(f"Trop de tentatives de code pour l'utilisateur {user.id}")
            raise invalid

        if not self.verify_password(code, entry.code_hash):
            self.reset_code_repo.update(entry.id, attempts=entry.attempts + 1)
            raise invalid

        # Code consommé : usage unique.
        self.reset_code_repo.update(
            entry.id,
            used_at=datetime.now(timezone.utc),
            is_active=False,
        )

        token = self.create_password_reset_token(user.id, user.email)
        logger.info(f"Code de réinitialisation validé pour l'utilisateur {user.id}")

        return {
            "success": True,
            "message": "Code validé",
            "item": {"reset_token": token},
        }

    def reset_password(self, token: str, new_password: str) -> dict:
        """
        Réinitialiser le mot de passe avec un token

        Args:
            token: Token JWT de réinitialisation
            new_password: Nouveau mot de passe

        Returns:
            Message de confirmation

        Raises:
            UnauthorizedError: Si le token est invalide ou expiré
            ValidationError: Si le nouveau mot de passe est invalide
        """
        logger.info("Tentative de réinitialisation de mot de passe")

        # 1. Décoder le token
        try:
            payload = self.decode_token(token)
        except UnauthorizedError as e:
            logger.warning(f"Token de réinitialisation invalide: {str(e)}")
            raise UnauthorizedError(
                "Le lien de réinitialisation est invalide ou a expiré. "
                "Veuillez faire une nouvelle demande."
            )

        # 2. Vérifier que c'est bien un token de réinitialisation
        if payload.get("type") != "password_reset":
            raise UnauthorizedError("Type de token invalide")

        user_id = int(payload.get("sub"))
        email = payload.get("email")

        # 3. Récupérer l'utilisateur
        user = self.user_repo.get_by_id(user_id)

        # 4. Vérifier que l'email correspond (sécurité supplémentaire)
        if user.email != email:
            raise ValidationError("Token invalide pour cet utilisateur")

        # 5. Vérifier que l'ancien mot de passe est différent
        if self.verify_password(new_password, user.password_hash):
            raise ValidationError(
                "Le nouveau mot de passe doit être différent de l'ancien"
            )

        # 6. Hasher le nouveau mot de passe
        new_password_hash = self.hash_password(new_password)

        # 7. Mettre à jour le mot de passe
        self.user_repo.update(
            user_id,
            password_hash=new_password_hash
        )

        logger.info(f"Mot de passe réinitialisé pour user {user_id}")

        # 8. Envoyer email de confirmation (optionnel)
        try:
            from app.services.email_services_v2 import EmailTemplateService
            email_service = EmailTemplateService()
            user_name = user.company_profile.company_name if user.company_profile else "Utilisateur"

            # Email de confirmation de changement de mot de passe
            context = {
                "user_name": user_name,
                "app_name": settings.APP_NAME,
                "support_email": "support@marketplace.com",
                "year": 2025
            }

            email_service.send_email_with_template(
                to_email=user.email,
                subject="Mot de passe modifié",
                template_name="password_changed.html",
                context=context
            )
            logger.info(f"Email de confirmation envoyé à {user.email}")
        except Exception as e:
            logger.error(f"Erreur envoi email confirmation: {str(e)}")

        return {
            "success": True,
            "message": "Votre mot de passe a été réinitialisé avec succès. Vous pouvez maintenant vous connecter."
        }
