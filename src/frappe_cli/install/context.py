from dataclasses import dataclass
from pathlib import Path


@dataclass
class InstallContext:
    bench_name: str
    site_name: str
    frappe_branch: str
    app_url: str
    app_branch: str
    sudo_password: str
    mariadb_root_password: str
    admin_password: str
    ssl_email: str
    ubuntu_version: str
    dry_run: bool
    debug: bool = False
    skip_ssl: bool = False

    @property
    def app_name(self) -> str:
        return self.app_url.rstrip("/").split("/")[-1].removesuffix(".git")

    @property
    def bench_path(self) -> Path:
        return Path.home() / self.bench_name
