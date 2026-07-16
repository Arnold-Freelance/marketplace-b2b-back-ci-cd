import os

import uvicorn

from app.config.settings import settings

if __name__ == "__main__":
    # Render (et la plupart des PaaS) imposent le port via la variable $PORT.
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "app.main_new:app",
        host="0.0.0.0",
        port=port,
        reload=settings.is_development,
        log_level="info",
    )
