"""Walk an extracted repository tree and detect each file's language."""
import os

#: File extension -> language name. Keep in sync with the frontend legend.
EXTENSION_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".php": "PHP",
    ".rs": "Rust",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C",
    ".hpp": "C++",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".sql": "SQL",
    ".sh": "Shell",
    ".vue": "Vue",
    ".swift": "Swift",
    ".kt": "Kotlin",
}

_DOCKER_BASENAMES = {"dockerfile"}


def detect_language(filename: str) -> str:
    """Return the language for a file name, or 'Other' when unknown."""
    base = os.path.basename(filename).lower()
    if base in _DOCKER_BASENAMES or base.startswith("dockerfile."):
        return "Docker"
    ext = os.path.splitext(base)[1]
    return EXTENSION_MAP.get(ext, "Other")


def walk_tree(root: str) -> tuple[list[dict], dict]:
    """Walk ``root`` and return ``(files, top_languages)``.

    Each file is ``{"path": repo-relative posix path, "language": str,
    "size": int}``. ``top_languages`` maps language -> file count, ordered
    by count descending.
    """
    files: list[dict] = []
    counts: dict[str, int] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, root).replace(os.sep, "/")
            try:
                size = os.path.getsize(abs_path)
            except OSError:
                continue
            language = detect_language(filename)
            files.append({"path": rel_path, "language": language, "size": size})
            counts[language] = counts.get(language, 0) + 1
    files.sort(key=lambda f: f["path"])
    top_languages = dict(
        sorted(counts.items(), key=lambda item: item[1], reverse=True)
    )
    return files, top_languages
