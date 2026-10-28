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
    bench_parent: str = ""
    selected_steps: list[str] = field(default_factory=list)
    workflow: str = "production"
    log_fn: Optional[Callable[[str], None]] = field(default=None, repr=False)

    @property
    def app_name(self) -> str:
        if not self.app_url:
            return ""
        return self.app_url.rstrip("/").split("/")[-1].removesuffix(".git")

    @property
    def bench_path(self) -> Path:
        """Resolve a validated name inside the explicitly selected parent."""
        parent = Path(self.bench_parent).expanduser() if self.bench_parent else None
        return safe_bench_path(self.bench_name, home=parent)
