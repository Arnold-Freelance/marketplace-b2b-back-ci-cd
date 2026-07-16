from sqlalchemy.orm import Session
from app.repositories.user_repo import UserRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.order_repo import OrderRepository
from app.services.auth_service import AuthService
from app.services.product_service import ProductService
from app.services.order_service import OrderService

class ServiceFactory:
    def __init__(self, db: Session):
        self.db = db
        self._user_repo = self._product_repo = self._order_repo = None

    @property
    def user_repo(self): self._user_repo = self._user_repo or UserRepository(self.db); return self._user_repo
    @property
    def product_repo(self): self._product_repo = self._product_repo or ProductRepository(self.db); return self._product_repo
    @property
    def order_repo(self): self._order_repo = self._order_repo or OrderRepository(self.db); return self._order_repo

    def auth_service(self): return AuthService(self.user_repo)
    def product_service(self): return ProductService(self.product_repo, self.user_repo)
    def order_service(self): return OrderService(self.order_repo, self.user_repo)
