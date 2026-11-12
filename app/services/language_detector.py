"""Repository language detection."""

from collections import Counter
from pathlib import Path

EXTENSION_MAP = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".sql": "sql",
    ".psql": "sql",
    ".pls": "plsql",
    ".pks": "plsql",
    ".pkb": "plsql",
    ".prc": "plsql",
    ".fnc": "plsql",
    ".trg": "plsql",
    ".tpb": "plsql",
    ".tps": "plsql",
    ".sqlj": "plsql",
    ".cs": "csharp",
    ".fs": "fsharp",
    ".vb": "vbnet",
    ".java": "java",
    ".php": "php",
    ".phtml": "php",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".xml": "xml",
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".hcl": "terraform",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".gradle": "groovy",
    ".sh": "shell",
    ".bash": "shell",
}
SPECIAL_FILENAMES = {
    "dockerfile": "dockerfile",
    ".dockerignore": "dockerfile",
    # Package manifests — ensure SCA engines run when these exist
    "package.json": "javascript",
    "package-lock.json": "javascript",
    "yarn.lock": "javascript",
    "pnpm-lock.yaml": "javascript",
    "requirements.txt": "python",
    "pipfile.lock": "python",
    "poetry.lock": "python",
    "pyproject.toml": "python",
    "go.mod": "go",
    "go.sum": "go",
    "cargo.toml": "rust",
    "cargo.lock": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "gemfile": "ruby",
    "gemfile.lock": "ruby",
    "composer.json": "php",
    "composer.lock": "php",
    "packages.config": "csharp",
}


def detect_languages(repo_path: Path) -> dict[str, int]:
    """Count primary languages by file extension."""

    counts: Counter[str] = Counter()
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        file_name = file_path.name.lower()
        if file_name.endswith(".gradle.kts"):
            counts["kotlin"] += 1
            continue
        if file_name.endswith(".tf.json"):
            counts["terraform"] += 1
            continue
        special_language = SPECIAL_FILENAMES.get(file_name)
        if special_language:
            counts[special_language] += 1
            continue
        suffix = file_path.suffix.lower()
        language = EXTENSION_MAP.get(suffix)
        if language:
            counts[language] += 1
            if language in {"yaml", "json"} and _is_cloudformation_template(file_path):
                counts["cloudformation"] += 1
            continue
        if _is_cloudformation_template(file_path):
            counts["cloudformation"] += 1
    return dict(counts)


def _is_cloudformation_template(file_path: Path) -> bool:
    lower_name = file_path.name.lower()
    suffix = file_path.suffix.lower()

    if lower_name.endswith(".template"):
        return True
    if "cloudformation" in str(file_path).lower():
        return True
    if suffix not in {".yaml", ".yml", ".json"}:
        return False

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")[:65536].lower()
    except OSError:
        return False

    if "awstemplateformatversion" in content or '"awstemplateformatversion"' in content:
        return True
    if "aws::" in content:
        return True
    if ("transform:" in content or '"transform"' in content) and "aws::" in content:
        return True
    return False
