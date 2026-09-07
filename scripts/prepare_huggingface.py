"""Stage the tested wheels as the purecipher/xsecuremcp Docker Space."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


def prepare(root: Path, dist: Path, output: Path, commit: str) -> None:
    build = json.loads((dist / "build.json").read_text())
    if (
        not re.fullmatch(r"[a-f0-9]{40}", commit)
        or build["commit"] != commit
        or build["repository"] != "PureCipher/xsecuremcp2.0"
    ):
        raise ValueError("Space artifacts must match the tested fork commit")
    wheels = sorted(dist.glob("*.whl"))
    if len(wheels) != 4:
        raise ValueError("The Space requires all four tested workspace wheels")
    output.mkdir(parents=True, exist_ok=False)
    (output / "wheels").mkdir()
    for artifact in [*wheels, dist / "constraints.txt"]:
        shutil.copyfile(artifact, output / "wheels" / artifact.name)
    shutil.copyfile(dist / "build.json", output / "build.json")
    shutil.copyfile(root / "LICENSE", output / "LICENSE")

    # Share the existing runtime and launcher definitions, but install the
    # tested wheels instead of rebuilding packages on the Space.
    source = (root / "Dockerfile.purecipher-registry").read_text()
    stages, runtime = source.split("FROM python:3.12-slim-bookworm AS runtime\n")
    launchers = stages.split("\n\n", 1)[0]
    runtime = runtime.replace(
        "COPY --from=build /wheels /tmp/wheels", "COPY wheels /tmp/wheels"
    )
    runtime = runtime.replace(
        "EXPOSE 8000",
        "RUN useradd --create-home --uid 1000 app\n"
        "USER 1000\nWORKDIR /home/app\n"
        "ENV UV_CACHE_DIR=/home/app/.cache/uv "
        "NPM_CONFIG_CACHE=/home/app/.npm\nEXPOSE 8000",
    )
    (output / "Dockerfile").write_text(
        launchers + "\n\nFROM python:3.12-slim-bookworm AS runtime\n" + runtime
    )
    (output / ".dockerignore").write_text("*\n!Dockerfile\n!wheels/\n!wheels/**\n")
    readme = (root / ".github/huggingface/README.md").read_text()
    for placeholder, value in {
        "{{BUILD_COMMIT}}": commit,
        "{{BUILD_COMMIT_SHORT}}": commit[:12],
        "{{PACKAGE_VERSION}}": build["version"],
    }.items():
        readme = readme.replace(placeholder, value)
    (output / "README.md").write_text(readme)


if __name__ == "__main__":
    import os

    prepare(Path.cwd(), Path("dist"), Path("hf-space"), os.environ["GITHUB_SHA"])
