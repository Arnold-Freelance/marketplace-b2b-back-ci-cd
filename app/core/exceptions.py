# app/core/exceptions.py
"""Exceptions personnalisées pour l'application"""

class BaseAppException(Exception):
    """Exception de base pour l'application"""
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ValidationError(BaseAppException):
    """Erreur de validation des données"""
    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR")


class NotFoundError(BaseAppException):
    """Ressource non trouvée"""
    def __init__(self, resource_name: str, resource_id: any):
        message = f"{resource_name} avec l'ID {resource_id} n'a pas été trouvé"
        super().__init__(message, code="NOT_FOUND")


class DuplicateError(BaseAppException):
    """Duplication de ressource"""
    def __init__(self, message: str):
        super().__init__(message, code="DUPLICATE_ERROR")


class BusinessRuleError(BaseAppException):
    """Violation d'une règle métier"""
    def __init__(self, message: str):
        super().__init__(message, code="BUSINESS_RULE_VIOLATION")


class DatabaseError(BaseAppException):
    """Erreur de base de données"""
    def __init__(self, message: str = "Erreur lors de l'accès à la base de données"):
        super().__init__(message, code="DATABASE_ERROR")


class UnauthorizedError(BaseAppException):
    """Accès non autorisé"""
    def __init__(self, message: str = "Accès non autorisé"):
        super().__init__(message, code="UNAUTHORIZED")


class ForbiddenError(BaseAppException):
    """Action interdite"""
    def __init__(self, message: str = "Action interdite"):
        super().__init__(message, code="FORBIDDEN")