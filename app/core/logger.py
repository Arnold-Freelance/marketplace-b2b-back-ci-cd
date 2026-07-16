# app/core/logger.py
# ⚠️ IMPORTANT: Ne pas nommer ce fichier "logging.py"
# car cela entre en conflit avec le module standard Python
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Formatter avec couleurs pour la console"""

    # Codes de couleur ANSI
    COLORS = {
        'DEBUG': '\033[36m',  # Cyan
        'INFO': '\033[32m',  # Vert
        'WARNING': '\033[33m',  # Jaune
        'ERROR': '\033[31m',  # Rouge
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'  # Reset
    }

    def format(self, record):
        """Formate le log avec des couleurs"""
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging(
        log_level: str = "INFO",
        log_dir: str = "logs",
        max_bytes: int = 10485760,  # 10MB
        backup_count: int = 5
) -> logging.Logger:
    """
    Configure le système de logging avec rotation des fichiers

    Args:
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Répertoire pour les fichiers de log
        max_bytes: Taille maximale d'un fichier de log
        backup_count: Nombre de fichiers de backup à conserver

    Returns:
        Logger configuré
    """
    # Créer le répertoire de logs s'il n'existe pas
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Créer le logger
    logger = logging.getLogger("app")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Éviter la duplication des handlers si déjà configurés
    if logger.handlers:
        return logger

    # Format des logs pour fichiers (plus détaillé)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(funcName)s() | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Format des logs pour console (plus lisible)
    console_formatter = ColoredFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # Handler pour la console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Handler pour le fichier principal avec rotation
    today = datetime.now().strftime('%Y%m%d')
    file_handler = RotatingFileHandler(
        filename=log_path / f"app_{today}.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Handler pour les erreurs (fichier séparé)
    error_handler = RotatingFileHandler(
        filename=log_path / f"errors_{today}.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)

    # Handler pour le debug (fichier séparé, seulement en mode DEBUG)
    if log_level.upper() == "DEBUG":
        debug_handler = RotatingFileHandler(
            filename=log_path / f"debug_{today}.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(file_formatter)
        logger.addHandler(debug_handler)

    # Ajouter les handlers au logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    # Log initial
    logger.info(f"Logging configuré - Niveau: {log_level.upper()}, Répertoire: {log_dir}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Récupère un logger enfant pour un module spécifique

    Args:
        name: Nom du module/logger

    Returns:
        Logger pour le module

    Example:
        logger = get_logger(__name__)
        logger.info("Message du module")
    """
    if name:
        return logging.getLogger(f"app.{name}")
    return logging.getLogger("app")


# Instance globale du logger
logger = setup_logging()


# Décorateur pour logger les appels de méthodes
def log_execution(func):
    """
    Décorateur pour logger l'exécution d'une fonction

    Example:
        @log_execution
        def my_function():
            pass
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_logger = get_logger(func.__module__)
        func_logger.debug(f"▶ Début exécution: {func.__name__}()")

        try:
            result = func(*args, **kwargs)
            func_logger.debug(f"✓ Fin exécution: {func.__name__}()")
            return result
        except Exception as e:
            func_logger.error(
                f"✗ Erreur dans {func.__name__}(): {str(e)}",
                exc_info=True
            )
            raise

    return wrapper


def log_method_call(func):
    """
    Décorateur pour logger les appels de méthodes avec leurs arguments

    Example:
        @log_method_call
        def create(self, data):
            pass
    """
    import functools

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        class_name = self.__class__.__name__
        method_logger = get_logger(func.__module__)

        # Logger les arguments (en évitant les données sensibles)
        args_str = ", ".join(repr(arg)[:100] for arg in args)
        kwargs_str = ", ".join(f"{k}={repr(v)[:100]}" for k, v in kwargs.items())
        params = ", ".join(filter(None, [args_str, kwargs_str]))

        method_logger.debug(f"▶ {class_name}.{func.__name__}({params})")

        try:
            result = func(self, *args, **kwargs)
            method_logger.debug(f"✓ {class_name}.{func.__name__}() terminé")
            return result
        except Exception as e:
            method_logger.error(
                f"✗ Erreur dans {class_name}.{func.__name__}(): {str(e)}",
                exc_info=True
            )
            raise

    return wrapper


# Context manager pour logger les performances
class LogPerformance:
    """
    Context manager pour mesurer et logger le temps d'exécution

    Example:
        with LogPerformance("Opération complexe"):
            # Code à mesurer
            pass
    """

    def __init__(self, operation_name: str, logger_instance: Optional[logging.Logger] = None):
        self.operation_name = operation_name
        self.logger = logger_instance or logger
        self.start_time = None

    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.debug(f"⏱ Début: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        elapsed = time.time() - self.start_time

        if exc_type is None:
            self.logger.info(f"✓ {self.operation_name} terminé en {elapsed:.3f}s")
        else:
            self.logger.error(
                f"✗ {self.operation_name} échoué après {elapsed:.3f}s: {exc_val}"
            )

        return False  # Ne pas supprimer l'exception


# Fonction utilitaire pour logger les requêtes HTTP
def log_http_request(method: str, url: str, status_code: int, duration: float):
    """
    Logger une requête HTTP

    Args:
        method: Méthode HTTP (GET, POST, etc.)
        url: URL de la requête
        status_code: Code de statut HTTP
        duration: Durée de la requête en secondes
    """
    level = logging.INFO if 200 <= status_code < 400 else logging.ERROR
    logger.log(
        level,
        f"{method} {url} - {status_code} - {duration:.3f}s"
    )


# Fonction pour configurer le logging depuis les settings
def configure_logging_from_settings(settings):
    """
    Configure le logging depuis l'objet settings

    Args:
        settings: Instance de Settings avec configuration
    """
    global logger
    logger = setup_logging(
        log_level=settings.LOG_LEVEL,
        log_dir=settings.LOG_DIR,
        max_bytes=settings.LOG_MAX_BYTES,
        backup_count=settings.LOG_BACKUP_COUNT
    )
    return logger


# Exemple d'utilisation avancée
if __name__ == "__main__":
    # Test du système de logging
    test_logger = setup_logging(log_level="DEBUG")

    test_logger.debug("Message de debug")
    test_logger.info("Message d'information")
    test_logger.warning("Message d'avertissement")
    test_logger.error("Message d'erreur")
    test_logger.critical("Message critique")


    # Test du décorateur
    @log_execution
    def test_function():
        test_logger.info("Fonction de test")
        return "Résultat"


    test_function()

    # Test du context manager
    with LogPerformance("Opération test"):
        import time

        time.sleep(0.1)

    print("\n✅ Logs écrits dans le répertoire 'logs/'")
    print("   - app_YYYYMMDD.log (tous les logs)")
    print("   - errors_YYYYMMDD.log (erreurs uniquement)")
    print("   - debug_YYYYMMDD.log (debug uniquement si activé)")