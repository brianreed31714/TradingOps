"""Resolve local observation targets without importing project code or settings."""
import json
from pathlib import Path, PurePosixPath


def safe_local_path(root, value, *, suffix=None):
    if not isinstance(value, str) or not value or "\\" in value or any(c in value for c in ":*?<>|\x00"):
        raise ValueError("Unsafe relative path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Unsafe relative path")
    rel = PurePosixPath(value)
    if rel.is_absolute() or (suffix and rel.suffix != suffix):
        raise ValueError("Unexpected path")
    root = Path(root).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Path escapes checkout")
    return path


def resolve_entrypoint(root, registry, name):
    components = registry["components"]
    if not isinstance(components, list) or any(not isinstance(x, dict) for x in components):
        raise ValueError("Invalid components")
    entries = [x for x in components if x.get("id") == name]
    if len(entries) != 1:
        raise ValueError("Missing or duplicate component")
    entry = entries[0]
    if registry["project"] != "StockTracker" or name != "trader":
        return str(safe_local_path(root, entry.get("entrypoint"), suffix=".py")), "REGISTRY", True
    try:
        manifest_path = safe_local_path(root, registry.get(
            "runtime_manifest", "deploy/state/active_release.json"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        script = manifest["files"]["trader"]
        target = safe_local_path(root, script, suffix=".py")
        if not target.is_file():
            raise ValueError("Manifest script missing")
        return str(target), "LOCAL_MANIFEST_OBSERVED_ONLY", True
    except FileNotFoundError:
        reason = "MANIFEST_MISSING"
    except (OSError, ValueError, TypeError, KeyError):
        reason = "MANIFEST_INVALID"
    # A registry default is only a diagnostic candidate, never the active release.
    fallback = safe_local_path(root, entry.get("entrypoint"), suffix=".py")
    if not fallback.is_file():
        raise ValueError("Fallback script missing")
    return str(fallback), reason + "_REGISTRY_FALLBACK", False
