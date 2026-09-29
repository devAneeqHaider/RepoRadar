"""Download public GitHub repositories as tarballs.

Only public repository metadata and tarballs are fetched; no authentication
is used and no private data is ever requested.
"""
import json
import logging
import os
import re
import tarfile
import tempfile
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class GithubDownloadError(Exception):
    """Raised when a repository tarball cannot be downloaded or extracted."""


#: Directories that are never extracted (build artifacts, caches, VCS data).
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

#: Extensions treated as binary — skipped during extraction.
BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".exe",
    ".dll",
    ".so",
    ".o",
    ".a",
    ".woff",
    ".woff2",
    ".ttf",
    ".mp4",
    ".mp3",
}

MAX_TARBALL_BYTES = 50 * 1024 * 1024  # ~50 MB download cap
MAX_EXTRACTED_BYTES = 300 * 1024 * 1024  # guard against decompression bombs
MAX_FILES = 2000  # analysis file cap
_CHUNK_SIZE = 1024 * 64

REPO_URL_RE = re.compile(r"^https://github\.com/([^/\s]+)/([^/\s]+)/?$")
_USER_AGENT = "RepoRadar/1.0 (+https://github.com)"


class GithubClient:
    """Fetches public GitHub repository tarballs and metadata."""

    def parse_url(self, url: str) -> tuple[str, str]:
        """Split a GitHub repo URL into (owner, name); strips a .git suffix."""
        match = REPO_URL_RE.match((url or "").strip())
        if not match:
            raise GithubDownloadError(
                f"Invalid GitHub repository URL: {url!r}. "
                "Expected https://github.com/<owner>/<repo>"
            )
        owner, name = match.group(1), match.group(2)
        if name.endswith(".git"):
            name = name[: -len(".git")]
        return owner, name

    def _candidate_urls_for(self, owner: str, repo: str, branch: str) -> list[str]:
        return [
            f"https://api.github.com/repos/{owner}/{repo}/tarball/{branch}",
            f"https://codeload.github.com/{owner}/{repo}/legacy.tar.gz/{branch}",
        ]

    def download(
        self, owner: str, repo: str, branches: tuple[str, ...] = ("main", "master")
    ) -> tuple[str, dict]:
        """Download and safely extract a repo tarball.

        Returns ``(temp_dir_path, {"default_branch": branch_used})``.
        Raises :class:`GithubDownloadError` on any failure.
        """
        last_error: Exception | None = None
        for branch in branches:
            for url in self._candidate_urls_for(owner, repo, branch):
                try:
                    tarball_path = self._fetch_tarball(url)
                except GithubDownloadError as exc:
                    last_error = exc
                    logger.info("Tarball fetch failed for %s: %s", url, exc)
                    continue
                try:
                    temp_dir = self._safe_extract(tarball_path)
                finally:
                    try:
                        os.unlink(tarball_path)
                    except OSError:
                        pass
                return temp_dir, {"default_branch": branch}
        raise GithubDownloadError(
            f"Could not download {owner}/{repo}: tried branches "
            f"{list(branches)} via api.github.com and codeload.github.com. "
            f"Last error: {last_error}"
        )

    def _fetch_tarball(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/octet-stream"},
        )
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except (urllib.error.URLError, OSError) as exc:
            raise GithubDownloadError(f"Request to {url} failed: {exc}") from exc

        with response:
            if getattr(response, "status", 200) not in (200,):
                raise GithubDownloadError(
                    f"Unexpected HTTP status {getattr(response, 'status', '?')} for {url}"
                )
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_TARBALL_BYTES:
                raise GithubDownloadError(
                    f"Tarball exceeds {MAX_TARBALL_BYTES // (1024 * 1024)} MB cap "
                    f"(Content-Length: {content_length} bytes)"
                )
            fd, tmp_path = tempfile.mkstemp(suffix=".tar.gz")
            downloaded = 0
            try:
                with os.fdopen(fd, "wb") as fh:
                    while True:
                        chunk = response.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        if downloaded > MAX_TARBALL_BYTES:
                            raise GithubDownloadError(
                                "Tarball exceeded "
                                f"{MAX_TARBALL_BYTES // (1024 * 1024)} MB while streaming"
                            )
                        fh.write(chunk)
            except GithubDownloadError:
                os.unlink(tmp_path)
                raise
            except OSError as exc:
                os.unlink(tmp_path)
                raise GithubDownloadError(f"Failed writing tarball: {exc}") from exc
        return tmp_path

    def _safe_extract(self, tarball_path: str) -> str:
        """Extract a tarball with path-traversal protection into a fresh temp dir."""
        temp_dir = tempfile.mkdtemp(prefix="reporadar-")
        extracted_bytes = 0
        file_count = 0
        try:
            with tarfile.open(tarball_path, "r:*") as tar:
                for member in tar.getmembers():
                    if not member.isreg():
                        continue  # skip dirs, symlinks, hardlinks, devices
                    rel = self._sanitize_member(member.name)
                    if rel is None:
                        continue
                    if file_count >= MAX_FILES:
                        logger.info("File cap (%d) reached, stopping extraction", MAX_FILES)
                        break
                    target = os.path.join(temp_dir, rel)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with tar.extractfile(member) as src, open(target, "wb") as dst:
                        while True:
                            chunk = src.read(_CHUNK_SIZE)
                            if not chunk:
                                break
                            extracted_bytes += len(chunk)
                            if extracted_bytes > MAX_EXTRACTED_BYTES:
                                raise GithubDownloadError(
                                    "Extracted content exceeded safety cap"
                                )
                            dst.write(chunk)
                    file_count += 1
        except tarfile.TarError as exc:
            raise GithubDownloadError(f"Invalid tar archive: {exc}") from exc
        if file_count == 0:
            raise GithubDownloadError("Tarball contained no extractable files")
        return temp_dir

    @staticmethod
    def _sanitize_member(name: str) -> str | None:
        """Strip the tarball's top-level dir; reject traversal, skips, binaries."""
        if os.path.isabs(name):
            return None
        parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
        if not parts or any(p == ".." for p in parts):
            return None
        # GitHub tarballs nest everything under "<owner>-<repo>-<sha>/".
        parts = parts[1:]
        if not parts:
            return None
        if any(p in SKIP_DIRS for p in parts):
            return None
        if os.path.splitext(parts[-1])[1].lower() in BINARY_EXTS:
            return None
        return os.path.join(*parts)

    def fetch_repo_meta(self, owner: str, repo: str) -> dict:
        """Best-effort public metadata (stars, description, language). Never raises."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/vnd.github+json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - metadata is optional
            logger.info("Repo metadata fetch failed for %s/%s: %s", owner, repo, exc)
            return {}
        return {
            "stars": int(payload.get("stargazers_count") or 0),
            "description": payload.get("description") or "",
            "language": payload.get("language") or "",
            "default_branch": payload.get("default_branch") or "main",
        }
