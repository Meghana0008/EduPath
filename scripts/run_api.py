"""Start API with .env loaded (ensures SMTP credentials are available)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
os.environ.setdefault("PYTHONPATH", str(ROOT / "backend"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        app_dir=str(ROOT / "backend"),
    )
