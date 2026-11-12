"""File-level quality analysis."""

import ast
import math
from collections.abc import Iterable
from pathlib import Path

import lizard

from app.models.file_metrics import FileMetrics
from app.models.finding import Finding, FindingSeverity

SOURCE_EXTENSIONS = {
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".go",
    ".kt",
    ".kts",
    ".swift",
    ".sql",
    ".psql",
    ".cs",
    ".fs",
    ".vb",
    ".java",
    ".php",
    ".phtml",
    ".rb",
    ".rs",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".cxx",
    ".hpp",
    ".hh",
    ".xml",
    ".tf",
    ".tfvars",
    ".hcl",
    ".yaml",
    ".yml",
    ".json",
    ".gradle",
    ".sh",
    ".bash",
}


def _relative_path(base_path: Path, file_path: Path) -> str:
    return str(file_path.relative_to(base_path))


def analyze_files(base_path: Path, scan_id: int) -> tuple[list[FileMetrics], list[Finding]]:
    """Analyze files and produce file metrics and quality findings."""

    metrics: list[FileMetrics] = []
    findings: list[Finding] = []

    for file_path in _iter_source_files(base_path):
        language = _detect_language(file_path)
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        loc = _logical_loc(text)
        complexity = _cyclomatic_complexity(file_path, text, language)
        maintainability = _maintainability_index(loc, complexity)
        debt_minutes = max(0, int((complexity - 8) * 15))
        relative = _relative_path(base_path, file_path)

        metric = FileMetrics(
            scan_id=scan_id,
            file_path=relative,
            language=language,
            lines_of_code=loc,
            cyclomatic_complexity=complexity,
            maintainability_index=round(maintainability, 2),
            technical_debt_minutes=debt_minutes,
        )
        metrics.append(metric)

        if complexity >= 14:
            findings.append(
                Finding(
                    scan_id=scan_id,
                    tool="quality-analyzer",
                    severity=FindingSeverity.MEDIUM if complexity < 20 else FindingSeverity.HIGH,
                    title="High cyclomatic complexity",
                    message=f"{relative} has cyclomatic complexity {complexity}",
                    description="Break down nested logic into smaller, testable units.",
                    category="complexity",
                    file_path=relative,
                    fingerprint=f"quality:{relative}:complexity",
                    line=1,
                )
            )
        if maintainability < 55:
            findings.append(
                Finding(
                    scan_id=scan_id,
                    tool="quality-analyzer",
                    severity=FindingSeverity.MEDIUM,
                    title="Low maintainability index",
                    message=f"{relative} has maintainability index {maintainability:.1f}",
                    description=(
                        "Refactor long functions and reduce branching to improve maintainability."
                    ),
                    category="maintainability",
                    file_path=relative,
                    fingerprint=f"quality:{relative}:maintainability",
                    line=1,
                )
            )

    return metrics, findings


def _iter_source_files(base_path: Path) -> Iterable[Path]:
    for file_path in base_path.rglob("*"):
        if not file_path.is_file():
            continue
        if ".git" in file_path.parts or "node_modules" in file_path.parts:
            continue
        file_name = file_path.name.lower()
        if file_name == "dockerfile" or file_name == ".dockerignore":
            yield file_path
            continue
        if file_name.endswith(".gradle.kts"):
            yield file_path
            continue
        if file_path.suffix.lower() in SOURCE_EXTENSIONS:
            yield file_path


def _detect_language(file_path: Path) -> str:
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()
    if name == "dockerfile" or name == ".dockerignore":
        return "dockerfile"
    if name.endswith(".gradle.kts"):
        return "kotlin"
    if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
        return "javascript"
    if suffix in {".ts", ".tsx", ".mts", ".cts"}:
        return "typescript"
    if suffix in {".kt", ".kts"}:
        return "kotlin"
    if suffix in {".sql", ".psql"}:
        return "sql"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix in {".tf", ".tfvars", ".hcl"}:
        return "terraform"
    mapping = {
        ".py": "python",
        ".pyi": "python",
        ".go": "go",
        ".swift": "swift",
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
        ".json": "json",
        ".gradle": "groovy",
        ".sh": "shell",
        ".bash": "shell",
    }
    return mapping.get(suffix, "text")


def _logical_loc(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _cyclomatic_complexity(file_path: Path, text: str, language: str) -> int:
    if language == "python":
        ast_complexity = _python_ast_complexity(text)
        if ast_complexity is not None:
            return max(1, ast_complexity)
    lizard_complexity = _lizard_complexity(file_path)
    if lizard_complexity is not None:
        return max(1, lizard_complexity)
    return 1


def _lizard_complexity(file_path: Path) -> int | None:
    try:
        analysis = lizard.analyze_file(str(file_path))
    except Exception:  # noqa: BLE001
        return None
    if not analysis.function_list:
        return 1
    return max(int(function.cyclomatic_complexity) for function in analysis.function_list)


class _PythonComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        self.complexity += max(1, len(node.handlers))
        if node.orelse:
            self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:  # noqa: N802
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:  # noqa: N802
        self.complexity += 1 + len(node.ifs)
        self.generic_visit(node)


def _python_ast_complexity(text: str) -> int | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    visitor = _PythonComplexityVisitor()
    visitor.visit(tree)
    return visitor.complexity


def _maintainability_index(loc: int, complexity: int) -> float:
    safe_loc = max(loc, 1)
    safe_complexity = max(complexity, 1)
    volume_proxy = max(1.0, float(safe_loc * safe_complexity))
    raw_index = (
        (
            171.0
            - (5.2 * math.log(volume_proxy))
            - (0.23 * safe_complexity)
            - (16.2 * math.log(safe_loc))
        )
        * 100.0
        / 171.0
    )
    return max(0.0, min(100.0, raw_index))
