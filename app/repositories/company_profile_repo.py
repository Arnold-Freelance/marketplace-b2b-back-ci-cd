from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository
from app.models.company_profile_entity import CompanyProfileEntity


class CompanyProfileRepository(BaseRepository):
    """Repository pour les profils entreprises"""

    def __init__(self, db: Session):
        super().__init__(db, CompanyProfileEntity)

    def get_by_user_id(self, user_id: int):
        """Récupérer le profil par user_id"""
        return self.db.query(CompanyProfileEntity).filter(
            CompanyProfileEntity.user_id == user_id
        ).first()