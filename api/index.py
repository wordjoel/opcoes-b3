"""Entrada da função Python na Vercel. O código fica fora de api/ porque a Vercel
transformaria cada arquivo desta pasta em uma função separada."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402,F401
