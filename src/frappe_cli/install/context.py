from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..utils.validators import safe_bench_path


@dataclass
class InstallContext:
    bench_name: str
    site_name: str
    frappe_branch: str
    app_url: str
    app_branch: str
    sudo_password: str = field(repr=False)
    mariadb_root_password: str = field(repr=False)
    admin_password: str = field(repr=False)
    ssl_email: str
    ubuntu_version: str
    dry_run: bool
    debug: bool = False
    skip_ssl: bool = False
    enable_passwordless_restart: bool = False
    log_fn: Optional[Callable[[str], None]] = field(default=None, repr=False)

    @property
    def app_name(self) -> str:
        if not self.app_url:
            return ""
        return self.app_url.rstrip("/").split("/")[-1].removesuffix(".git")

    @property
    def bench_path(self) -> Path:
        """Return a validated bench path that is guaranteed to live under ``$HOME``.

        Raises :class:`ValidationError` if ``bench_name`` is unsafe (absolute
        path, traversal, or contains characters that could break shell/path
        operations). Every step that touches the filesystem uses this property,
        so validation cannot be bypassed.
        """
        return safe_bench_path(self.bench_name)
