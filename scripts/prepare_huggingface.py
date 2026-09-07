"""Stage the tested wheels as the purecipher/xsecuremcp Docker Space."""

from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path

from markdown_it import MarkdownIt


def render_readme(readme: str, template: str) -> str:
    body = re.sub(r"\A---\n.*?\n---\n", "", readme, count=1, flags=re.S)
    markdown = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = markdown.parse(body)
    toc = []
    slugs: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            title = tokens[index + 1].content
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"
            count = slugs.get(slug, 0)
            slugs[slug] = count + 1
            anchor = f"{slug}-{count}" if count else slug
            token.attrSet("id", anchor)
            if token.tag == "h2":
                toc.append(f'<a href="#{anchor}">{escape(title)}</a>')
        for child in token.children or []:
            if child.type == "link_open" and (child.attrGet("href") or "").startswith(
                ("https://", "http://")
            ):
                child.attrSet("target", "_blank")
                child.attrSet("rel", "noopener noreferrer")
    rendered = markdown.renderer.render(tokens, markdown.options, {})
    rendered = rendered.replace("<table>", '<div class="table-wrap"><table>').replace(
        "</table>", "</table></div>"
    )
    return template.replace("{{TOC_HTML}}", "\n".join(toc)).replace(
        "{{README_HTML}}", rendered
    )


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
        "COPY space_app.py index.html /app/\n"
        "RUN useradd --create-home --uid 1000 app\n"
        "USER 1000\nWORKDIR /home/app\n"
        "ENV UV_CACHE_DIR=/home/app/.cache/uv "
        "NPM_CONFIG_CACHE=/home/app/.npm\nEXPOSE 8000",
    )
    runtime = runtime.replace(
        '["purecipher-registry", "--host", "0.0.0.0", "--port", "8000"]',
        '["python", "/app/space_app.py"]',
    )
    (output / "Dockerfile").write_text(
        launchers + "\n\nFROM python:3.12-slim-bookworm AS runtime\n" + runtime
    )
    (output / ".dockerignore").write_text(
        "*\n!Dockerfile\n!wheels/\n!wheels/**\n!space_app.py\n!index.html\n"
    )
    shutil.copyfile(root / "scripts/huggingface_app.py", output / "space_app.py")
    readme = (root / ".github/huggingface/README.md").read_text()
    for placeholder, value in {
        "{{BUILD_COMMIT}}": commit,
        "{{BUILD_COMMIT_SHORT}}": commit[:12],
        "{{PACKAGE_VERSION}}": build["version"],
    }.items():
        readme = readme.replace(placeholder, value)
    (output / "README.md").write_text(readme)
    (output / "index.html").write_text(
        render_readme(readme, (root / ".github/huggingface/page.html").read_text())
    )


if __name__ == "__main__":
    import os

    prepare(Path.cwd(), Path("dist"), Path("hf-space"), os.environ["GITHUB_SHA"])
