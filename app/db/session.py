from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings

engine = create_engine(settings.DATABASE_URL, echo= settings.is_development, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
