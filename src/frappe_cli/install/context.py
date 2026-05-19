from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


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
    log_fn: Optional[Callable[[str], None]] = field(default=None, repr=False)

    @property
    def app_name(self) -> str:
        if not self.app_url:
            return ""
        return self.app_url.rstrip("/").split("/")[-1].removesuffix(".git")

    @property
    def bench_path(self) -> Path:
        return Path.home() / self.bench_name
