import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app  # noqa: E402

# Em execução local (uvicorn api.index:app), serve o frontend estático no mesmo host.
# Na Vercel, a CDN serve os arquivos estáticos diretamente e encaminha /api/* para esta função.
if not os.getenv("VERCEL") and ROOT_DIR.exists():
    app.mount("/", StaticFiles(directory=str(ROOT_DIR), html=True), name="static")
