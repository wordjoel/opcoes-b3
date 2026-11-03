"""Aplica as migrations: python -m db.migrate"""

from core.config import load_local_env
from db.client import Database, migrate


def main() -> None:
    load_local_env()
    applied = migrate(Database.from_env())
    print("Aplicadas: " + ", ".join(applied) if applied else "Nada pendente.")


if __name__ == "__main__":
    main()
