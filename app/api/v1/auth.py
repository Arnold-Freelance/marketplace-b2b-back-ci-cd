# app/routes/auth_routes.py
"""
Routes d'authentification simplifiées
Les exceptions sont gérées automatiquement par le middleware
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.company_profile_repo import CompanyProfileRepository
from app.schemas.base import ResponseBase
from app.services.auth_service import AuthService
from app.repositories.user_repo import UserRepository
from app.repositories.password_reset_code_repo import PasswordResetCodeRepository
from app.schemas.user import UserCreateSchema, UserLoginSchema, UserSchema, TokenResponse, ResetPasswordSchema, \
    ForgotPasswordSchema, VerifyResetCodeSchema
from app.core.logger import logger

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Factory pour créer le service d'authentification"""
    user_repo = UserRepository(db)
    profile_repo = CompanyProfileRepository(db)
    # Sans ce repo, forgot-password ne peut pas émettre de code.
    return AuthService(user_repo, profile_repo, PasswordResetCodeRepository(db))


@router.post(
    "/register",
    response_model=ResponseBase[UserSchema],
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d'un nouvel utilisateur",
    description="Créer un compte utilisateur (supplier, buyer ou admin)"
)
async def register(
        user_data: UserCreateSchema,
        auth_service: AuthService = Depends(get_auth_service)
) -> ResponseBase[UserSchema]:
    """
    Inscription d'un nouvel utilisateur

    - **email**: Email unique
    - **phone**: Numéro de téléphone unique
    - **password**: Mot de passe (min 8 caractères, 1 majuscule, 1 chiffre)
    - **user_type**: Type d'utilisateur (supplier, buyer, admin)
    - **company_name**: Nom de l'entreprise (obligatoire pour supplier/buyer)

    Les exceptions (DuplicateError, ValidationError) sont gérées par le middleware
    """
    logger.info(f"Requête d'inscription: {user_data.email}")
    return auth_service.register_user(user_data)


@router.post(
    "/login",
    response_model=ResponseBase[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Connexion utilisateur",
    description="Authentifier un utilisateur et obtenir un token JWT"
)
async def login(
        credentials: UserLoginSchema,
        auth_service: AuthService = Depends(get_auth_service)
) -> ResponseBase[TokenResponse]:
    """
    Connexion utilisateur

    - **identifier**: Email ou numéro de téléphone
    - **password**: Mot de passe

    Retourne un token JWT et les informations utilisateur
    Les exceptions (UnauthorizedError) sont gérées par le middleware
    """
    logger.info(f"Requête de connexion: {credentials.identifier}")
    return auth_service.authenticate_user(credentials)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Déconnexion utilisateur",
    description="Invalider le token (à implémenter avec blacklist)"
)
async def logout():
    """
    Déconnexion utilisateur

    Note: Avec JWT, la déconnexion côté serveur nécessite une blacklist de tokens.
    Pour l'instant, la déconnexion se fait côté client en supprimant le token.
    """
    return {"message": "Déconnexion réussie"}


# ==================== ROUTES SUPPLÉMENTAIRES (OPTIONNELLES) ====================

@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    response_model=ResponseBase[UserSchema],
    summary="Vérifier l'email",
    description="Vérifier l'email avec un code/token"
)
async def verify_email(
        verification_token: str,
        auth_service: AuthService = Depends(get_auth_service)
) -> ResponseBase[UserSchema]:
    """Vérification de l'email (à implémenter)"""
    return auth_service.verify_email(verification_token)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Renvoyer l'email de vérification",
    description="Renvoyer le lien de vérification si email non vérifié"
)
async def resend_verification(
        email: str,
        auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """
    Renvoyer l'email de vérification

    - **email**: Email de l'utilisateur
    """
    logger.info(f"Requête de renvoi d'email: {email}")
    return auth_service.resend_verification_email(email)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Mot de passe oublié",
    description="Demander un lien de réinitialisation de mot de passe par email"
)
async def forgot_password(
        request: ForgotPasswordSchema,
        auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """
    Demande de réinitialisation de mot de passe

    - **email**: Email du compte

    Un **code à 6 chiffres** est envoyé par email (valable 15 minutes, usage unique) :
    l'utilisateur le saisit dans l'app, il n'y a pas de lien à ouvrir.
    Pour des raisons de sécurité, la réponse est toujours la même,
    que l'email existe ou non.
    """
    logger.info(f"Requête forgot-password: {request.email}")
    return auth_service.forgot_password(request.email)


@router.post(
    "/verify-reset-code",
    status_code=status.HTTP_200_OK,
    summary="Vérifier le code de réinitialisation",
    description="Échanger le code reçu par email contre un token de réinitialisation",
)
async def verify_reset_code(
        request: VerifyResetCodeSchema,
        auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """
    Vérifier le code à 6 chiffres.

    - **email**: Email du compte
    - **code**: Code reçu par email

    Renvoie un `reset_token` à passer à `/reset-password`. Le code est consommé :
    il ne peut plus resservir. Après 5 tentatives, il est invalidé.
    """
    logger.info("Requête verify-reset-code")
    return auth_service.verify_reset_code(request.email, request.code)


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Réinitialiser le mot de passe",
    description="Réinitialiser le mot de passe avec un token"
)
async def reset_password(
        request: ResetPasswordSchema,
        auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """
    Réinitialiser le mot de passe

    - **token**: Token reçu par email
    - **new_password**: Nouveau mot de passe (min 8 caractères, 1 majuscule, 1 chiffre)

    Le token expire après 1 heure.
    """
    logger.info("Requête reset-password")
    return auth_service.reset_password(request.token, request.new_password)