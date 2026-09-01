"""Alembic-backed migrations for PureCipher registry persistence.

The migration scripts use SQLAlchemy's dialect-agnostic operations
(``op.create_table``, ``sa.Text``, …) so the same chain upgrades either a
PostgreSQL database (production) or a single-file SQLite database (legacy
local development). The target is chosen from the persistence string's scheme.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from purecipher.pgdb import is_postgres_dsn, sqlalchemy_url


def migrate_registry_database(target: str | None) -> None:
    """Upgrade the PureCipher registry database to the latest schema.

    Args:
        target: A PostgreSQL DSN (``postgresql://…``) or a SQLite file path.
            ``None`` or ``:memory:`` is a no-op / ephemeral and skips
            migration (schema is created in-process instead).
    """

    if not target:
        return

    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).with_name("migrations")),
    )

    if is_postgres_dsn(target):
        database_url = sqlalchemy_url(target)
        config.attributes["purecipher_db_path"] = target
    else:
        db_file = Path(target).expanduser()
        if str(db_file) == ":memory:":
            return
        db_file.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{db_file.resolve()}"
        config.attributes["purecipher_db_path"] = str(db_file)

    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


__all__ = ["migrate_registry_database"]
