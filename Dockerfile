# Backend FastAPI — Marketplace B2B
# Build depuis le dossier Backend/ :
#   docker build -t marketplace-b2b-api .
#   docker run --rm -p 8000:8000 --env-file .env marketplace-b2b-api
#
# 3.12 et pas 3.13 : c'est la version figée par `runtime.txt` (python-3.12.7)
# et par `PYTHON_VERSION` du `render.yaml`. Garder les deux alignés.
FROM python:3.12-slim

# - PYTHONDONTWRITEBYTECODE : pas de .pyc dans un conteneur jetable.
# - PYTHONUNBUFFERED : sans ça, les logs restent bloqués dans le buffer stdout
#   et n'apparaissent pas dans `docker logs`.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Aucun paquet système à installer : psycopg2-binary, pillow et bcrypt sont
# distribués en wheels manylinux (libpq et libjpeg embarqués). D'où le choix de
# `psycopg2-binary` plutôt que `psycopg2` — cf. le commentaire du requirements.

# Les dépendances d'abord, seules : cette couche n'est réinvalidée que si
# requirements.txt change, pas à chaque modification de code.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# `main_new.py:105` monte `StaticFiles(directory="uploads")`, qui lève une
# RuntimeError AU DÉMARRAGE si le dossier n'existe pas — or .gitignore exclut son
# contenu, donc il peut très bien ne pas arriver dans le contexte de build.
# On le crée donc inconditionnellement, et il appartient à l'utilisateur applicatif
# (STORAGE_BACKEND=local y écrit ; en prod c'est Supabase qui prend le relais).
RUN mkdir -p uploads

# Utilisateur non-root : par défaut un conteneur tourne en root, ce qui n'a aucune
# raison d'être ici.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# `sh -c` (et non la forme exec) car $PORT doit être interpolé : Render et la
# plupart des PaaS imposent le port par cette variable. Repli sur 8000 en local,
# comme le fait déjà run.py.
CMD ["sh", "-c", "uvicorn app.main_new:app --host 0.0.0.0 --port ${PORT:-8000}"]
