"""Create a source-only ZIP of the core application, without bundled dependencies."""

import argparse
import hashlib
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".gitignore",
    ".python-version",
    "LICENSE",
    "alembic.ini",
    "pyproject.toml",
    "requirements.txt",
    "tools_config.yaml",
}
FRONTEND_FILES = {
    ".gitignore",
    "bun.lock",
    "eslint.config.js",
    "index.html",
    "package.json",
    "tsconfig.app.json",
    "tsconfig.json",
    "tsconfig.node.json",
    "vite.config.ts",
}


def include(path: Path) -> bool:
    """Keep application source and build inputs, not local data or support projects."""
    name = path.as_posix()
    if name in ROOT_FILES or name == "docs/openapi.json":
        return True
    if not path.parts or path.parts[0] not in {"app", "alembic", "frontend"}:
        return False
    if any(
        part in {"node_modules", "dist", "build", "__pycache__", "tests", "stitch"}
        for part in path.parts
    ):
        return False
    if path.suffix in {".pyc", ".tsbuildinfo"} or path.name == "setupTests.ts":
        return False
    if re.search(r"\.(test|spec)\.[^.]+$", path.name):
        return False
    if re.match(r"(?i)^(agents?|tasks?|handoff|prd)[._-].*\.(md|txt|rst)$", path.name):
        return False
    if path.parts[0] in {"app", "alembic"}:
        return path.suffix in {".py", ".mako"}
    relative = path.relative_to("frontend")
    return (
        relative.as_posix() in FRONTEND_FILES
        or relative.parts[0] == "src"
        or relative.as_posix() in {"public/favicon.svg", "public/icons.svg"}
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/vigilweave-core.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite {output}; choose another output name")
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    selected = []
    for name in sorted(filter(None, paths)):
        path = Path(name)
        source = ROOT / path
        if not include(path) or not source.is_file() or source.is_symlink():
            continue
        if any(parent.is_symlink() for parent in source.parents if ROOT in parent.parents):
            raise RuntimeError(f"Symlink in source path: {path}")
        selected.append(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in selected:
            archive.write(ROOT / path, Path("vigilweave-core") / path)
        archive.writestr(
            "vigilweave-core/README.md", (ROOT / "docs/core-application.md").read_text()
        )
    with output.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    print(f"Created {output}: {len(selected) + 1} files, {output.stat().st_size / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
