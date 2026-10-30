#!/usr/bin/env python3
"""Build a small, deterministic, plugin-specific QwenPaw release ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

MAX_BYTES = 10 * 1024 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
RUNTIME_FILES = {"plugin.json", "plugin.py", "README.md", "CHANGELOG.md", "LICENSE"}


def runtime_files(plugin_dir: Path, root: Path) -> list[tuple[Path, str]]:
    """Return only runtime files, with safe, portable archive paths."""
    entries: list[tuple[Path, str]] = []
    for path in sorted(plugin_dir.rglob("*")):
        relative = path.relative_to(plugin_dir)
        if path.is_symlink():
            raise ValueError(f"Symlinks are not release inputs: {relative}")
        if not path.is_file():
            continue
        parts = relative.parts
        if not parts or any(part in {".git", "__pycache__", "node_modules"} for part in parts):
            continue
        if parts[0] in {"tests", "verification", "dist"}:
            continue
        if parts[0] == "web" and len(parts) == 2 and parts[1].endswith(".js"):
            pass
        elif len(parts) != 1 or parts[0] not in RUNTIME_FILES:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        archive_path = PurePosixPath(*parts)
        if archive_path.is_absolute() or ".." in archive_path.parts:
            raise ValueError(f"Unsafe release path: {relative}")
        entries.append((path, archive_path.as_posix()))
    names = [name for _, name in entries]
    if "plugin.json" not in names or "plugin.py" not in names:
        raise ValueError("plugin.json and plugin.py are required")
    return entries


def build(plugin_directory: Path, root: Path) -> tuple[Path, str, int]:
    plugin_dir = plugin_directory.resolve()
    if not plugin_dir.is_dir():
        raise ValueError(f"Plugin directory does not exist: {plugin_directory}")
    manifest = json.loads((plugin_dir / "plugin.json").read_text(encoding="utf-8"))
    plugin_id = manifest["id"]
    version = manifest["version"]
    if not plugin_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in plugin_id):
        raise ValueError("Plugin ID contains unsafe filename characters")
    if not version or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-+_" for char in version):
        raise ValueError("Plugin version contains unsafe filename characters")
    entries = runtime_files(plugin_dir, root)
    output_dir = root / "dist"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / f"{plugin_id}-v{version}.zip"

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, archive_name in entries:
            content = path.read_bytes()
            if archive_name == "LICENSE" and len(content) < 1000:
                content = (root / "LICENSE").read_bytes()
            info = zipfile.ZipInfo(archive_name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
        names = archive.namelist()
        if "plugin.json" not in names or any(name.startswith("/") or ".." in PurePosixPath(name).parts for name in names):
            raise ValueError("Unsafe or invalid ZIP layout")
        packaged_manifest = json.loads(archive.read("plugin.json"))
        if packaged_manifest["id"] != plugin_id or packaged_manifest["version"] != version:
            raise ValueError("Packaged manifest differs from the source manifest")
        for entry_name in (packaged_manifest.get("entry") or {}).values():
            if entry_name not in names:
                raise ValueError(f"Manifest entry is absent from release: {entry_name}")
        if len(archive.read("LICENSE")) < 1000:
            raise ValueError("Release must include the complete licence")

    size = output.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(f"Release exceeds 10 MB: {size} bytes")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return output, digest, size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_directory", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        output, digest, size = build(args.plugin_directory, root)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Packaging failed: {exc}", file=sys.stderr)
        return 1
    print(f"Archive: {output.relative_to(root)}")
    print(f"Size: {size:,} bytes (limit: {MAX_BYTES:,})")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
