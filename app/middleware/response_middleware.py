"""
Response wrapping middleware — garantit que TOUTE réponse JSON sortante est
un `ResponseBase` (success, message, item / items), même si l'endpoint a
retourné un dict ou un objet "nu".

Inspiré par la cohérence de format imposée par le `Response<T>` Spring Boot,
mais sans exiger que chaque service écrive le wrapper à la main.

Comportement :
- Skip si content-type != application/json
- Skip si status_code hors 2xx (les erreurs ont leur propre format via
  exception_middleware)
- Skip si déjà au format ResponseBase (présence de la clé `success`)
- Skip pour la doc (`/api/docs`, `/api/openapi.json`, `/api/redoc`)
- Sinon, wrap en `{"success": True, "message": "...", "item" | "items": ...}`

Note perf : ré-encode chaque body JSON. Acceptable au stade actuel ; à
réévaluer si traffic important. StreamingResponse n'est pas concerné car
elle utilise un media_type différent (text/event-stream typiquement).
"""
import json
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_DOC_PATHS = ("/api/docs", "/api/redoc", "/api/openapi.json", "/docs", "/redoc", "/openapi.json")
_DEFAULT_OK_MESSAGE = "Opération réussie"


def _is_already_wrapped(data) -> bool:
    """Heuristique : un ResponseBase a forcément `success` et `message`."""
    return isinstance(data, dict) and "success" in data and "message" in data


def _wrap(data) -> dict:
    """Wrap une valeur arbitraire en ResponseBase-shaped dict."""
    if isinstance(data, list):
        return {
            "success": True,
            "message": _DEFAULT_OK_MESSAGE,
            "items": data,
            "total": len(data),
        }
    return {
        "success": True,
        "message": _DEFAULT_OK_MESSAGE,
        "item": data,
    }


class ResponseWrappingMiddleware(BaseHTTPMiddleware):
    """
    Enrobe automatiquement les réponses JSON 2xx en ResponseBase si l'endpoint
    n'a pas déjà retourné un dict ResponseBase-shaped.
    """

    def __init__(self, app, skip_paths: Iterable[str] | None = None):
        super().__init__(app)
        self.skip_paths = tuple(skip_paths) if skip_paths is not None else _DOC_PATHS

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip pour la doc OpenAPI
        if any(request.url.path.startswith(p) for p in self.skip_paths):
            return await call_next(request)

        response = await call_next(request)

        # Skip non-JSON
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Skip erreurs (gérées par exception_middleware)
        if not (200 <= response.status_code < 300):
            return response

        # Lire le body (consomme l'itérateur original)
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            data = json.loads(body) if body else None
        except json.JSONDecodeError:
            # Body non parsable — on le repasse tel quel
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Si déjà wrappé, on rejoue le body original sans le réencoder
        if _is_already_wrapped(data):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Wrap & ré-encode
        wrapped = _wrap(data)
        new_body = json.dumps(wrapped, default=str).encode("utf-8")

        # Important : recalculer Content-Length
        headers = dict(response.headers)
        headers["content-length"] = str(len(new_body))

        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )
