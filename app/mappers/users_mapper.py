from app.models.user_entity import UserEntity
from app.schemas.user import UserSchema


class UsersMapper:
    @staticmethod
    def entity_to_schema(user: UserEntity) -> UserSchema:
        """
        Convertir UserEntity en UserSchema (transformation de données)

        Args:
            user: Entité utilisateur avec profil chargé

        Returns:
            UserSchema pour la réponse API
        """
        return UserSchema(
            id=user.id,
            email=user.email,
            phone=user.phone,
            user_type=user.user_type,
            roles=user.role_names,
            status=user.status,
            email_verified=user.email_verified,
            phone_verified=user.phone_verified,
            created_at=user.created_at.strftime("%d/%m/%Y") if user.created_at else None,
            last_login=user.last_login.strftime("%d/%m/%Y") if user.last_login else None,
            company_name=user.company_profile.company_name if user.company_profile else None,
            contact_person=user.company_profile.contact_person if user.company_profile else None,
            city=user.company_profile.city if user.company_profile else None
        )