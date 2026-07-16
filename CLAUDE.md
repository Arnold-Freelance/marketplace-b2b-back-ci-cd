# Backend — Marketplace B2B

API REST FastAPI pour la plateforme B2B.

## Stack

- **FastAPI** ≥0.110 (entry point : `app/main_new.py`, lancé via `run.py` sur port 8000)
- **SQLAlchemy 2.0** (ORM, mode sync via `psycopg2-binary`)
- **PostgreSQL** (DB principale, schema dans `postgres_bd.sql`)
- **Pydantic v2** (≥2.6 — migration faite Phase 4 code-facto)
- **PyJWT** + `passlib[bcrypt]` (auth)
- **pydantic-settings** (chargement `.env`)
- **pytest** + **httpx** (tests — Phase 5)
- **Alembic** gère le schéma de base (migrations). `create_all()` a été retiré du démarrage (il ne modifiait pas l'existant → dérives). Voir section *Migrations*.

## Architecture en couches

```
app/
├── api/
│   ├── deps.py          Dépendances FastAPI (get_db, get_current_user)
│   ├── v1/              Routes HTTP legacy (RequestBase + user dans body)
│   └── v2/              Routes HTTP REST idiomatiques (recommandé pour le nouveau)
├── middleware/
│   ├── exception_middleware.py   Exception handlers + RequestLogging
│   ├── auth_middleware.py        Décode le JWT pour TOUTES les routes (whitelist)
│   └── response_middleware.py    Wrap auto en ResponseBase
├── services/            Logique métier
│   ├── base_service.py           Classe abstraite legacy
│   └── service_protocol.py       Protocol BasicService (recommandé pour le nouveau)
├── repositories/        Accès DB (CRUD)
│   └── base.py          BaseRepository avec paramètre autocommit (cf. Phase 2)
├── models/              Entités SQLAlchemy
├── schemas/             DTOs Pydantic v2
├── mappers/             Conversion model ↔ schema
├── security/            JWT, hashing
├── core/
│   ├── logger.py, exceptions.py, enums.py
│   └── transactional.py Décorateur @transactional (Unit of Work)
├── db/                  Session, base, engine
├── config/              Settings (pydantic-settings)
├── container/           DI / factories
├── websocket/           Connection manager
├── templates/emails/    Templates Jinja2
└── utils/
```

## Middlewares (Phase 1 code-facto)

**Ordre d'exécution** (du plus externe au plus interne) :
1. **`RequestLoggingMiddleware`** — log toutes les requêtes + temps
2. **`CORSMiddleware`** — gère les preflights
3. **`GZipMiddleware`** — compression
4. **`ResponseWrappingMiddleware`** — enrobe auto en `ResponseBase` les responses JSON 2xx non déjà-wrappées
5. **`AuthMiddleware`** — décode le JWT, expose `request.state.user_id`
6. → Route

**`AuthMiddleware`** :
- Whitelist : login, register, forgot/reset password, docs, health
- Pour les autres : décode le JWT, met `request.state.user_id` (+ `user_payload`)
- 401 ResponseBase formaté si invalide
- **Plus besoin de re-décoder le JWT** sur chaque route

**`ResponseWrappingMiddleware`** :
- Si la réponse est un dict/objet nu → enrobe en `{success: true, message, item}`
- Si la réponse est une liste → enrobe en `{success: true, message, items, total}`
- Si déjà au format ResponseBase → passe-through
- Erreurs 4xx/5xx préservées (gérées par exception_middleware)

## Auth — comment ça marche

Du côté route :
```python
from app.api.deps import get_current_user

@router.get("/me")
async def me(current_user_id: int = Depends(get_current_user)):
    return {"id": current_user_id}
```

`get_current_user` est désormais une simple lecture de `request.state.user_id` (posé par le middleware). Pas de re-décodage.

## Routes — pattern recommandé (v2)

**Faire** (`app/api/v2/products.py`) :
```python
@router.get("")
async def list_products(
    current_user_id: Annotated[int, Depends(get_current_user)],
    search: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    ...

@router.post("", status_code=201)
async def create_product(
    data: ProductSchema,
    current_user_id: Annotated[int, Depends(get_current_user)],
):
    ...

@router.put("/{product_id}")
async def update_product(
    product_id: int,
    data: ProductSchema,
    current_user_id: Annotated[int, Depends(get_current_user)],
):
    ...
```

**Ne plus faire** (legacy `v1/`) :
- `POST /products/create` → préférer `POST /products`
- `POST /products/update` avec id dans body → préférer `PUT /products/{id}`
- `RequestBase` enveloppant avec `user` dans body → identité via token
- Filtres dans le body POST → query params GET

## Services — Protocol BasicService

Recommandé pour les nouveaux services :
```python
from app.services.service_protocol import BasicService
from app.schemas.base import ResponseBase

class ProductService:  # Pas besoin d'hériter
    def create(self, data, user_id: int) -> ResponseBase[ProductSchema]: ...
    def update(self, entity_id: int, data, user_id: int) -> ResponseBase[ProductSchema]: ...
    def delete(self, entity_id: int, user_id: int) -> ResponseBase[ProductSchema]: ...
    def get_by_id(self, entity_id: int) -> ResponseBase[ProductSchema]: ...
    def get_by_criteria(self, criteria=None, limit=20, offset=0) -> ResponseBase[ProductSchema]: ...
```

Le Protocol est duck-typé — l'IDE/mypy vérifie la conformité, pas le runtime.

## Repositories — `autocommit` (Phase 2)

`BaseRepository` accepte `autocommit=True` (défaut, legacy) ou `False`.

**Nouveau pattern recommandé** : `autocommit=False` + `@transactional` au niveau service :
```python
from app.core.transactional import transactional

class ProductService:
    def __init__(self, product_repo, audit_repo):
        self.product_repo = product_repo
        self.audit_repo = audit_repo
        self.db = product_repo.db  # nécessaire pour @transactional

    @transactional
    def create(self, data, user_id):
        product = self.product_repo.create(...)  # flush sans commit
        self.audit_repo.create(...)              # idem
        return ResponseBase(success=True, item=product_schema)
        # commit auto en sortie / rollback auto sur exception
```

## Conventions importantes

- **Identité** : toujours via `Depends(get_current_user)` qui lit `request.state.user_id`. **Jamais** dans le body de la requête.
- **Réponses uniformes** : `ResponseBase[T]` partout. Le middleware wrap automatiquement les réponses brutes, mais préférer retourner explicitement un `ResponseBase` quand possible (plus clair).
- **Pas de try/except dans les routes** — les exceptions custom sont attrapées par `exception_middleware`.
- **Logging** : `from app.core.logger import logger`, pas `print`.
- **Uploads** : `uploads/products/images/`, etc. — créés par `services/file_upload_service.py`.

## Configuration `.env`

Voir `.env.example`. Obligatoires : `DATABASE_URL`, `SECRET_KEY` (Settings plante au démarrage sans, avec `Field(...)`).

Générer un SECRET_KEY :
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Lancement

```bash
# Depuis Backend/
pip install -r requirements.txt
python run.py
```

- Swagger : http://localhost:8000/api/docs
- Healthcheck : http://localhost:8000/health

## Migrations (Alembic)

Le schéma est versionné dans `alembic/versions/`. `env.py` lit la metadata
des modèles (`Base.metadata`) et l'URL depuis `settings.DATABASE_URL`
(surchargeable via `ALEMBIC_DATABASE_URL`).

```bash
cd Backend
alembic upgrade head                          # (re)construit / met à jour la base
alembic revision --autogenerate -m "message"  # après un changement de modèle
alembic current        # révision courante
alembic history        # historique
```

Workflow : on modifie une entité → `alembic revision --autogenerate` → on
relit la migration générée → `alembic upgrade head`. **Ne plus utiliser
`create_all()`** (source de dérive de schéma).

## Tests

```bash
cd Backend
pip install -r requirements.txt
pytest                       # tous les tests
pytest tests/test_auth_middleware.py -v
```

Setup actuel : tests sur les middlewares (auth + response wrapping). À étendre vers les routes et services.

## API servie (toutes en /api/v1, REST idiomatique)

`main_new.py` inclut tous les routers ci-dessous. Il n'y a plus de routes
legacy : l'ancienne v1 (RequestBase + tout en POST) a été supprimée et les
routes REST renommées de /api/v2 vers /api/v1.

| Domaine | Préfixe | Notes |
|---|---|---|
| Auth | `/api/v1/auth` | login, register, forgot/reset, verify |
| Products | `/api/v1/products` | CRUD + `/{id}/stock` |
| Product images | `/api/v1/products/{id}/images` | nested, upload/batch/order/primary |
| Categories | `/api/v1/categories` | CRUD + `/by-slug` + `/hierarchy` |
| Cart | `/api/v1/cart` | `/items` |
| Orders | `/api/v1/orders` | `?role=buyer\|supplier`, `/status`, `/cancel` |
| Reviews | `/api/v1/reviews` | `/response`, `/vote`, `/products/{id}`, `/statistics` |
| Wishlist | `/api/v1/favorites` | `/statistics`, `/by-product/{id}` |
| Messaging | `/api/v1/conversations`, `/api/v1/messages` | REST + temps réel via WS |
| Notifications | `/api/v1/notifications` | `/read-all` |
| Payments | `/api/v1/payments` | `/initiate`, `/callback` (public), `/refund` |
| WebSocket | `/ws/chat/{user_id}`, `/ws/notifications/{user_id}` | token JWT en query param |

### Paiement
Module scaffold avec provider abstrait (`services/payment/provider.py`).
Par défaut `MockMobileMoneyProvider` (aucun réseau, simule Mobile Money).
Brancher un vrai PSP (CinetPay/Wave/Orange Money) = implémenter
`PaymentProvider` et l'injecter dans `PaymentService`.

### WebSocket & auth
Le WS ne passe PAS par AuthMiddleware (scope HTTP uniquement). La validation
du token JWT se fait dans la route (`_validate_ws_token`), via le query
param `?token=`, et vérifie que le user_id du token == user_id de l'URL.

### Routes publiques (whitelist AuthMiddleware)
login, register, logout, forgot/reset/verify, docs/health,
`/api/v1/payments/callback` (webhook PSP), `/api/v1/categories/hierarchy`.

## CORS

Actuellement `allow_origins=["*"]` — à restreindre avant déploiement prod.

## Migration en cours

| Aspect | v1 (legacy) | v2 (recommandé) |
|---|---|---|
| Verbes HTTP | Tout en POST | GET / POST / PUT / DELETE |
| Body | `RequestBase{user, data}` | Schema direct |
| Identité | `request.user` du body | `Depends(get_current_user)` |
| Filtres | Dans le body | Query params |
| Validation | Pydantic v1 (`@validator`, `class Config`) | Pydantic v2 (`@field_validator`, `ConfigDict`) |
| Commits | Auto dans repo | `@transactional` dans service |

Les anciennes routes v1 restent actives pour la compat mobile. Une fois le mobile migré, on supprime v1.
