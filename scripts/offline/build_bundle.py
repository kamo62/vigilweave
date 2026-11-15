"""Prepare the no-Docker Linux ZIP on the connected preparation machine.

Requires the project's existing .venv, frontend/node_modules, Bun, uv and a Python
with pip. Downloads wheels/binaries, never installs into the existing project env.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
ARCHES = {"x86_64": "x64", "aarch64": "arm64"}
GITLEAKS_VERSION = "8.30.0"
OMITTED_PACKAGES = {"psycopg", "playwright", "checkov", "cfn-lint", "semgrep", "sqlfluff"}
SOURCE_DIRS = {"app", "alembic", "docs", "frontend", "scripts", "tests"}
SOURCE_FILES = {
    ".gitignore",
    ".python-version",
    ".env.example",
    "LICENSE",
    "README.md",
    "CONTRIBUTING.md",
    "alembic.ini",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "tools_config.yaml",
}


def included_source(relative: Path) -> bool:
    """Allowlist source and reject local/runtime/planning/build material at any depth."""
    if relative.parts[0] not in SOURCE_DIRS and relative.as_posix() not in SOURCE_FILES:
        return False
    for part in relative.parts:
        name = part.lower()
        if name in {
            "node_modules",
            "dist",
            "build",
            "__pycache__",
            "do-not-run",
            ".git",
            ".vscode",
            "stitch",
            ".dockerignore",
            "nginx.conf",
            "kubernetes-deployment.md",
        }:
            return False
        if name.startswith(("docker", ".env.")) and relative.as_posix() != ".env.example":
            return False
        if Path(name).suffix in {".md", ".txt", ".rst", ".adoc"} and re.match(
            r"^(agents?|tasks?|handoff|prd)([._-]|$)", name
        ):
            return False
        if name == ".env" or name.endswith((".db", ".db-wal", ".db-shm", ".pyc", ".tsbuildinfo")):
            return False
    return relative.as_posix() not in {"scripts/build_multiarch_images.sh"}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def download(url: str, destination: Path, expected: str | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Download {destination.name}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)
    if expected and sha256(destination) != expected:
        raise RuntimeError(f"Upstream checksum mismatch: {destination.name}")


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read().decode()


def run(command: list[str], **kwargs) -> None:
    subprocess.run(command, check=True, **kwargs)


def source_copy(destination: Path) -> None:
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    # Include only this task's new support files, not arbitrary untracked local work.
    paths += [
        str(p.relative_to(ROOT)) for p in (ROOT / "scripts/offline").rglob("*") if p.is_file()
    ]
    paths += ["tests/test_offline_bundle.py", "docs/offline-local.md"]
    for name in sorted(set(paths)):
        relative = Path(name)
        source = ROOT / relative
        if not name or not included_source(relative) or source.is_symlink() or not source.is_file():
            continue
        if any(p.is_symlink() for p in source.parents if p != ROOT and ROOT in p.parents):
            raise RuntimeError(f"Symlink in source path: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def frontend_build(bundle: Path) -> dict:
    modules = ROOT / "frontend/node_modules"
    if not modules.is_dir():
        raise RuntimeError("frontend/node_modules is required; use the existing locked install")
    index = bundle / "frontend/index.html"
    # Offline UI uses the existing CSS system-font fallbacks, not remote font services.
    index.write_text(
        "".join(
            line
            for line in index.read_text().splitlines(keepends=True)
            if "fonts.googleapis.com" not in line and "fonts.gstatic.com" not in line
        )
    )
    # Build sanitised source: no local .env or public design/PRD mockups can leak into dist.
    staged_modules = bundle / "frontend/node_modules"
    staged_modules.symlink_to(modules, target_is_directory=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("VITE_")}
    env.update({"VITE_API_BASE_URL": "", "VITE_APP_URL": "", "VITE_MARKETING_URL": ""})
    try:
        run(["bun", "run", "build"], cwd=bundle / "frontend", env=env)
    finally:
        staged_modules.unlink()

    # Preserve third-party notices, including transitive packages, outside the served directory.
    inventory = []
    for package in sorted(modules.rglob("package.json")):
        if not package.is_file():
            continue
        metadata = json.loads(package.read_text(encoding="utf-8"))
        relative = package.parent.relative_to(modules)
        inventory.append(
            {
                "path": str(relative),
                "name": metadata.get("name"),
                "version": metadata.get("version"),
                "license": metadata.get("license"),
            }
        )
        for notice in package.parent.iterdir():
            if notice.is_file() and notice.name.lower().startswith(
                ("license", "licence", "notice", "copying")
            ):
                # These directories contain notices only, never dependency code.
                notice_path = Path(
                    *(
                        "nested-dependencies" if part == "node_modules" else part
                        for part in relative.parts
                    )
                )
                target = bundle / "THIRD_PARTY/frontend" / notice_path / notice.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(notice, target)
    (bundle / "THIRD_PARTY/frontend-packages.json").write_text(
        json.dumps(inventory, indent=2) + "\n"
    )
    return {
        "bun": subprocess.check_output(["bun", "--version"], text=True).strip(),
        "lock_sha256": sha256(ROOT / "frontend/bun.lock"),
    }


def python_assets(bundle: Path, temporary: Path) -> dict:
    baseline = json.loads(
        subprocess.check_output(
            [
                str(ROOT / ".venv/bin/python"),
                "-c",
                "import json,sys;from importlib.metadata import distributions;"
                "print(json.dumps({'python':sys.version.split()[0],"
                "'packages':{d.metadata['Name']:d.version for d in distributions()}}))",
            ],
            text=True,
        )
    )
    version = baseline["python"]
    if not version.startswith("3.14."):
        raise RuntimeError("This bundle currently targets the project's Python 3.14 baseline")
    constraints = temporary / "baseline.txt"
    constraints.write_text("".join(f"{n}=={v}\n" for n, v in sorted(baseline["packages"].items())))
    requirements = []
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        name = re.split(r"[\[<>=]", line)[0].lower()
        if line and name not in OMITTED_PACKAGES:
            requirements.append(line)
    # Include the existing backend test tools, without the heavyweight optional scanners.
    requirements += [
        line
        for line in (ROOT / "requirements-dev.txt").read_text().splitlines()
        if line.startswith(("pytest==", "pytest-cov=="))
    ]
    selected = temporary / "runtime.in"
    selected.write_text("\n".join(requirements) + "\n")
    runtimes = json.loads(
        subprocess.check_output(
            ["uv", "python", "list", "--all-platforms", "--all-arches", "--output-format", "json"],
            text=True,
        )
    )
    runtime_sources = {}
    for arch in ARCHES:
        runtime = next(
            item
            for item in runtimes
            if item["version"] == version
            and item["os"] == "linux"
            and item["arch"] == arch
            and item["libc"] == "gnu"
            and item["variant"] == "default"
        )
        # uv's mirror may not expose checksum sidecars. Resolve the exact upstream
        # release asset and verify the digest supplied by GitHub's release API.
        tag, filename = runtime["url"].split("/download/", 1)[1].split("/", 1)
        release = json.loads(
            get_text(
                f"https://api.github.com/repos/astral-sh/python-build-standalone/releases/tags/{tag}"
            )
        )
        asset = next(item for item in release["assets"] if item["name"] == unquote(filename))
        url = asset["browser_download_url"]
        digest = asset.get("digest", "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise RuntimeError("Missing upstream Python SHA256 digest")
        expected = digest.removeprefix("sha256:")
        archive = bundle / "vendor/python" / f"{arch}.tar.gz"
        download(url, archive, expected)
        runtime_sources[arch] = {"url": url, "sha256": expected}
        # The portable interpreter distribution retains its own licences inside the tarball.
        with tarfile.open(archive) as tar:
            if not any("license" in member.name.lower() for member in tar.getmembers()):
                raise RuntimeError("Portable Python archive contains no licence material")
        resolved = temporary / f"resolved-{arch}.txt"
        run(
            [
                "uv",
                "--no-config",
                "pip",
                "compile",
                str(selected),
                "-c",
                str(constraints),
                "--python-version",
                version,
                "--python-platform",
                f"{arch}-unknown-linux-gnu",
                "--default-index",
                "https://pypi.org/simple",
                "--no-header",
                "--no-annotate",
                "-o",
                str(resolved),
            ],
            cwd=ROOT,
        )
        wheels = bundle / "vendor/wheels" / arch
        wheels.mkdir(parents=True)
        platforms = [f"manylinux_2_{minor}_{arch}" for minor in range(34, 16, -1)]
        platforms += [f"manylinux2014_{arch}"]
        command = [
            sys.executable,
            "-m",
            "pip",
            "--isolated",
            "download",
            "--index-url",
            "https://pypi.org/simple",
            "--only-binary=:all:",
            "--no-deps",
            "--python-version",
            "3.14",
            "--implementation",
            "cp",
            "--abi",
            "cp314",
            "--dest",
            str(wheels),
            "-r",
            str(resolved),
        ]
        for value in platforms:
            command.extend(["--platform", value])
        run(command)
        # The offline installer consumes only exact versions plus hashes of the delivered wheels.
        pins = []
        for wheel in sorted(wheels.glob("*.whl")):
            name, wheel_version = wheel.name.split("-")[:2]
            pins.append(f"{name}=={wheel_version} --hash=sha256:{sha256(wheel)}")
        (bundle / f"vendor/requirements-{arch}.txt").write_text("\n".join(pins) + "\n")
    (bundle / "vendor/preparation-baseline.json").write_text(json.dumps(baseline, indent=2) + "\n")
    return {"version": version, "sources": runtime_sources}


def gitleaks_assets(bundle: Path, temporary: Path) -> dict:
    base = f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}/"
    checksums = get_text(base + f"gitleaks_{GITLEAKS_VERSION}_checksums.txt")
    (bundle / "vendor/gitleaks-upstream-checksums.txt").write_text(checksums)
    hashes = {line.split()[1].lstrip("*"): line.split()[0] for line in checksums.splitlines()}
    sources = {}
    for arch, release_arch in ARCHES.items():
        filename = f"gitleaks_{GITLEAKS_VERSION}_linux_{release_arch}.tar.gz"
        archive = temporary / filename
        download(base + filename, archive, hashes[filename])
        with tarfile.open(archive) as tar:
            # Copy named regular files, never extract arbitrary archive paths or links.
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                name = Path(member.name).name
                if name != "gitleaks" and not name.lower().startswith(("license", "notice")):
                    continue
                target = bundle / "vendor/bin" / arch / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if name == "gitleaks" else 0o644)
        if not (bundle / "vendor/bin" / arch / "gitleaks").is_file():
            raise RuntimeError("Gitleaks binary missing from upstream archive")
        sources[arch] = {"url": base + filename, "sha256": hashes[filename]}
    return {"version": GITLEAKS_VERSION, "sources": sources}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/vigilweave-offline-linux.zip")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite {output}; choose a new output name")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="offline-build-", dir=output.parent) as directory:
        temporary = Path(directory)
        bundle = temporary / "vigilweave-offline"
        source_copy(bundle)
        frontend = frontend_build(bundle)
        python = python_assets(bundle, temporary)
        gitleaks = gitleaks_assets(bundle, temporary)
        (bundle / "OFFLINE.md").write_text((ROOT / "docs/offline-local.md").read_text())
        manifest = {
            "prepared_at": datetime.now(UTC).isoformat(),
            "source_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_note": "Working-tree source, including uncommitted offline packaging support",
            "platforms": ["linux-x86_64-glibc2.34+", "linux-aarch64-glibc2.34+"],
            "frontend": frontend,
            "python": python,
            "gitleaks": gitleaks,
            "linux_runtime_verified": False,
        }
        (bundle / "BUNDLE.json").write_text(json.dumps(manifest, indent=2) + "\n")
        files = sorted(p for p in bundle.rglob("*") if p.is_file())
        if any(p.is_symlink() for p in bundle.rglob("*")):
            raise RuntimeError("Unexpected symlink in bundle")
        (bundle / "SHA256SUMS").write_text(
            "".join(f"{sha256(p)}  {p.relative_to(bundle).as_posix()}\n" for p in files)
        )
        with zipfile.ZipFile(
            output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for path in sorted(bundle.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(temporary))
    output.with_suffix(output.suffix + ".sha256").write_text(f"{sha256(output)}  {output.name}\n")
    print(f"Created {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
