"""Alembic-backed SQLite migrations for PureCipher registry persistence."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def migrate_registry_database(db_path: str | None) -> None:
    """Upgrade the PureCipher registry database to the latest schema."""

    if not db_path:
        return

    db_file = Path(db_path).expanduser()
    if str(db_file) != ":memory:":
        db_file.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{db_file.resolve()}"
    else:
        database_url = "sqlite:///:memory:"

    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).with_name("migrations")),
    )
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["purecipher_db_path"] = str(db_file)
    command.upgrade(config, "head")


__all__ = ["migrate_registry_database"]
