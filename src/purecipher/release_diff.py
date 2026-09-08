"""Deterministic release comparison; never treats missing inventory as empty."""

import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def inventory(snapshot):
    metadata = snapshot.get("metadata") or {}
    inspection = metadata.get("introspection") or {}
    if not isinstance(inspection, dict):
        inspection = {}
    raw = inspection.get("tools")
    names = inspection.get("tool_names")
    if not isinstance(raw, list):
        raw = metadata.get("tools")
    if not isinstance(raw, list) and not isinstance(names, list):
        return None
    tools = {}
    for item in raw or []:
        if isinstance(item, str):
            tools[item] = {"name": item}
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            tools[item["name"]] = item
    if isinstance(names, list):
        tools = {
            name: tools.get(name, {"name": name})
            for name in names
            if isinstance(name, str)
        }
    return tools


def compare(before, after):
    if before is None:
        return {
            "available": False,
            "reason": "The original baseline was not saved and the published release has changed. Inspect the submitted snapshot; do not infer a historical comparison.",
        }
    fields = []
    for key in (
        "version",
        "display_name",
        "description",
        "categories",
        "tags",
        "source_url",
        "homepage_url",
        "license",
    ):
        if before.get(key) != after.get(key):
            fields.append(
                {"field": key, "before": before.get(key), "after": after.get(key)}
            )
    old_manifest, new_manifest = (
        before.get("manifest") or {},
        after.get("manifest") or {},
    )
    manifest_changes = [
        key
        for key in sorted(set(old_manifest) | set(new_manifest))
        if canonical(old_manifest.get(key)) != canonical(new_manifest.get(key))
    ]
    old_meta, new_meta = before.get("metadata") or {}, after.get("metadata") or {}
    metadata_changes = [
        key
        for key in sorted(set(old_meta) | set(new_meta))
        if canonical(old_meta.get(key)) != canonical(new_meta.get(key))
    ]
    security = [
        key
        for key in manifest_changes
        if key
        not in {
            "version",
            "description",
            "tags",
            "tool_name",
            "author",
            "created_at",
            "manifest_id",
        }
    ]
    fields.extend(
        {
            "field": "manifest." + key,
            "before": old_manifest.get(key),
            "after": new_manifest.get(key),
        }
        for key in security
    )
    old_tools, new_tools = inventory(before), inventory(after)
    tools = {
        "known": old_tools is not None and new_tools is not None,
        "added": [],
        "removed": [],
        "changed": [],
    }
    if tools["known"]:
        tools.update(
            added=sorted(new_tools.keys() - old_tools.keys()),
            removed=sorted(old_tools.keys() - new_tools.keys()),
            changed=sorted(
                k
                for k in old_tools.keys() & new_tools.keys()
                if canonical(old_tools[k]) != canonical(new_tools[k])
            ),
        )
    return {
        "available": True,
        "fields": fields,
        "manifest_changes": manifest_changes,
        "metadata_changes": metadata_changes,
        "security_changes": security,
        "tools": tools,
        "review_access": bool(
            security
            or metadata_changes
            or tools["removed"]
            or tools["changed"]
            or tools["added"]
        ),
    }
