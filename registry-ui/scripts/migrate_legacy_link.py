#!/usr/bin/env python3
"""Migrate <Link legacyBehavior passHref><X component="a" ...>…</X></Link>
into <X component={Link} href=… ...>…</X>.

Next.js 16 + Turbopack rejects ``<Link legacyBehavior>`` whose direct
child resolves to a Server Component. The fix is to drop the legacy
wrapper and let the child render as the link itself by passing
``component={Link}`` (MUI's ``component`` prop). This script does that
conversion mechanically for every file under registry-ui/src so we
don't have to chase one error at a time.

Run from the registry-ui root:
    python3 scripts/migrate_legacy_link.py

Idempotent: a second run finds no remaining usages and is a no-op.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


# Match a ``<Link href=... legacyBehavior passHref> <Child component="a" ...>
# inner </Child> </Link>`` block where Child is one of the safe set
# (Button, Box, CardActionArea). The href can be either a string
# literal or an expression in braces. We use a manual brace-aware scan
# below so we tolerate JSX with nested ``sx={{ ... }}`` props.

CHILD_TAGS = ("Button", "Box", "CardActionArea")
LINK_OPEN_RE = re.compile(
    r"<Link\b(?P<link_attrs>[^>]*?)\blegacyBehavior\b[^>]*?>",
    re.DOTALL,
)


def _extract_link_href(link_attrs: str) -> str | None:
    """Return ``href={...}`` or ``href="..."`` from the Link attrs."""
    m = re.search(
        r'\bhref=(?:"(?P<lit>[^"]*)"|\{(?P<expr>[^}]*(?:\{[^}]*\}[^}]*)*)\})',
        link_attrs,
    )
    if not m:
        return None
    if m.group("lit") is not None:
        return f'href="{m.group("lit")}"'
    return "href={" + m.group("expr") + "}"


def _strip_component_a(child_attrs: str) -> str:
    """Drop ``component="a"`` from a child's attribute string."""
    return re.sub(r'\s*component="a"\s*', " ", child_attrs).strip()


def _find_matching_close(text: str, start: int, tag: str) -> int | None:
    """Return the index just past the matching </tag>. Tracks balanced
    nested same-tag opens so we don't trip on inner ``<Box>``s."""
    open_re = re.compile(rf"<{tag}\b[^>]*>", re.DOTALL)
    close_re = re.compile(rf"</{tag}\s*>")
    depth = 1
    pos = start
    while pos < len(text):
        next_open = open_re.search(text, pos)
        next_close = close_re.search(text, pos)
        if next_close is None:
            return None
        if next_open is not None and next_open.start() < next_close.start():
            depth += 1
            pos = next_open.end()
            continue
        depth -= 1
        if depth == 0:
            return next_close.end()
        pos = next_close.end()
    return None


def _migrate_text(text: str) -> tuple[str, int]:
    """Walk the text linearly converting each Link/legacyBehavior block.

    Returns ``(new_text, count)``.
    """
    out: list[str] = []
    cursor = 0
    count = 0

    while True:
        m = LINK_OPEN_RE.search(text, cursor)
        if not m:
            out.append(text[cursor:])
            break

        # Everything up to the Link opener is unchanged.
        out.append(text[cursor : m.start()])

        link_attrs = m.group("link_attrs")
        href = _extract_link_href(link_attrs)
        if href is None:
            # Couldn't parse href — leave the original block alone.
            out.append(text[m.start() : m.end()])
            cursor = m.end()
            continue

        # Skip whitespace after the Link opener to find the first child.
        idx = m.end()
        while idx < len(text) and text[idx] in " \t\r\n":
            idx += 1

        # Child must be one of CHILD_TAGS with component="a".
        child_match = None
        for tag in CHILD_TAGS:
            ws = re.compile(rf"<{tag}\b(?P<child_attrs>[^>]*?)>", re.DOTALL)
            cm = ws.match(text, idx)
            if cm and 'component="a"' in cm.group("child_attrs"):
                child_match = (tag, cm)
                break
        if child_match is None:
            out.append(text[m.start() : m.end()])
            cursor = m.end()
            continue

        tag, cm = child_match
        child_attrs = cm.group("child_attrs")
        child_open_end = cm.end()

        # Find matching </tag>
        close_pos = _find_matching_close(text, child_open_end, tag)
        if close_pos is None:
            out.append(text[m.start() : m.end()])
            cursor = m.end()
            continue

        # And then expect </Link> immediately after (allowing whitespace).
        after_child = close_pos
        while after_child < len(text) and text[after_child] in " \t\r\n":
            after_child += 1
        link_close_re = re.compile(r"</Link\s*>")
        link_close_m = link_close_re.match(text, after_child)
        if link_close_m is None:
            out.append(text[m.start() : m.end()])
            cursor = m.end()
            continue

        # Build the new opener and emit it.
        new_attrs = _strip_component_a(child_attrs)
        new_open = f"<{tag} component={{Link}} {href}"
        if new_attrs:
            new_open += f" {new_attrs}"
        new_open += ">"
        inner = text[child_open_end:close_pos - len(f"</{tag}>")]
        out.append(new_open)
        out.append(inner)
        out.append(f"</{tag}>")
        cursor = link_close_m.end()
        count += 1

    return "".join(out), count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default="src",
        help="Directory to scan (default: src)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't write files."
    )
    args = parser.parse_args()

    root = Path(args.root)
    files = list(root.rglob("*.tsx")) + list(root.rglob("*.ts"))
    total_files = 0
    total_subs = 0
    for path in files:
        text = path.read_text()
        if "legacyBehavior" not in text:
            continue
        new_text, n = _migrate_text(text)
        if n > 0 and not args.dry_run:
            path.write_text(new_text)
        if n > 0:
            total_files += 1
            total_subs += n
            print(f"{path}: {n} block(s)")

    print(
        f"\nMigrated {total_subs} block(s) across {total_files} file(s)"
        + (" (dry run)" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
