"""O pacote enviado à Vercel precisa conter todo módulo que a API importa."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Importa a API num processo limpo e lista os pacotes do próprio repositório que ela carregou.
PROBE = """
import json, sys
from pathlib import Path
root = Path.cwd().resolve()
import app.main
names = set()
for name, module in list(sys.modules.items()):
    origin = getattr(module, "__file__", None)
    if origin:
        path = Path(origin).resolve()
        if path.is_relative_to(root) and ".venv" not in path.parts:
            names.add(name.split(".")[0])
print(json.dumps(sorted(names)))
"""


def ignored_entries() -> set[str]:
    lines = (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
    return {line.strip().rstrip("/") for line in lines if line.strip() and not line.startswith(("#", "!"))}


def test_api_imports_are_not_left_out_of_the_deploy():
    result = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, capture_output=True, text=True, check=True)
    used = set(json.loads(result.stdout.strip().splitlines()[-1]))
    assert {"app", "agents", "core", "quant"} <= used
    assert not used & ignored_entries(), f"usados pela API e ignorados no deploy: {used & ignored_entries()}"
