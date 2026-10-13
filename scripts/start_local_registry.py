"""Start the local hosted registry; retains local signing keys across restarts.

Requires local PostgreSQL at 127.0.0.1:5432 (or DATABASE_URL).
The first administrator is created through the registry setup page.
"""

import json
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
config = root / ".data/local-registry-keys.json"
config.parent.mkdir(parents=True, exist_ok=True)
if not config.exists():
    with open(
        config, "x", opener=lambda path, flags: os.open(path, flags, 0o600)
    ) as handle:
        json.dump(
            {
                key: secrets.token_urlsafe(48)
                for key in ["PURECIPHER_SIGNING_SECRET", "PURECIPHER_JWT_SECRET"]
            },
            handle,
        )
for key, value in json.loads(config.read_text()).items():
    os.environ.setdefault(key, value)
os.environ.setdefault(
    "DATABASE_URL", "postgresql://purecipher:purecipher@127.0.0.1:5432/purecipher"
)
os.environ.setdefault("PURECIPHER_ENABLE_AUTH", "true")
os.environ.setdefault("PURECIPHER_REQUIRE_MODERATION", "true")
os.environ.setdefault("PURECIPHER_CONSUMER_RUNTIME_ENABLED", "true")
os.environ.setdefault(
    "PURECIPHER_DIRECTORY_FILE", str(root / ".data/mcp-directory.json")
)
from purecipher.cli import main  # noqa: E402 - configuration precedes CLI imports

main(["--host", "127.0.0.1", "--port", "8001", "--host-toolsets"])
