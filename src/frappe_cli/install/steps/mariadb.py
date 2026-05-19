import os
import subprocess
import tempfile
from pathlib import Path

from .base import InstallStep

FRAPPE_MARIADB_CNF = """\
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""

# systemd unit names seen on Ubuntu/Debian for MariaDB/MySQL.
_MARIADB_UNITS = ("mariadb", "mysql", "mysqld")
_MARIADB_PACKAGES = ("mariadb-server", "mysql-server", "mariadb-server-10.11")


def _mariadb_unit_active() -> bool:
    """True when a MariaDB/MySQL systemd unit is active.

    Do not use `mysqladmin status` here — on secured servers it fails with
    'Access denied' for the invoking user even when the database is healthy.
    """
    for unit in _MARIADB_UNITS:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout.strip() == "active":
            return True
    return False


def _mariadb_packages_installed() -> bool:
    """True when a MariaDB/MySQL server package is already on the system."""
    for pkg in _MARIADB_PACKAGES:
        try:
            result = subprocess.run(
                ["dpkg", "-l", pkg],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "ii" and parts[1] == pkg:
                return True
    return False


def _active_mariadb_unit() -> str:
    """Return the active MariaDB/MySQL systemd unit name, or 'mariadb' as default."""
    for unit in _MARIADB_UNITS:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0 and result.stdout.strip() == "active":
            return unit
    return "mariadb"


def _frappe_cnf_exists(cnf_path: str) -> bool:
    try:
        return Path(cnf_path).exists()
    except (PermissionError, OSError):
        return False


class MariaDBInstallStep(InstallStep):
    name = "mariadb_install"
    description = "Install & configure MariaDB"
    CNF_PATH = "/etc/mysql/mariadb.conf.d/99-frappe.cnf"

    def check(self, ctx) -> bool:
        """Skip when MariaDB is running and the Frappe utf8mb4 drop-in exists."""
        running = _mariadb_unit_active()
        configured = _frappe_cnf_exists(self.CNF_PATH)
        if running and configured:
            if ctx.log_fn:
                ctx.log_fn(
                    "MariaDB is already installed, running, and has Frappe config"
                )
            return True
        return False

    def run(self, ctx) -> None:
        packages_present = _mariadb_packages_installed()
        service_active = _mariadb_unit_active()

        if packages_present or service_active:
            if ctx.log_fn:
                ctx.log_fn(
                    "MariaDB already present on this host — skipping apt install"
                )
        else:
            self._sudo(
                ctx, ["apt-get", "install", "-y", "mariadb-server", "mariadb-client"]
            )

        if not _frappe_cnf_exists(self.CNF_PATH):
            if ctx.log_fn:
                ctx.log_fn(f"Writing Frappe MariaDB config to {self.CNF_PATH}")
            self._sudo_write(ctx, FRAPPE_MARIADB_CNF, self.CNF_PATH)
        elif ctx.log_fn:
            ctx.log_fn(f"Frappe MariaDB config already at {self.CNF_PATH}")

        unit = _active_mariadb_unit()
        self._sudo(ctx, ["systemctl", "enable", unit])
        self._sudo(ctx, ["systemctl", "restart", unit])


class MariaDBSecureStep(InstallStep):
    name = "mariadb_secure"
    description = "Secure MariaDB"

    def check(self, ctx) -> bool:
        config = f"[client]\npassword={ctx.mariadb_root_password}\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cnf", delete=False) as tmp:
            tmp.write(config)
            tmp_name = tmp.name
        try:
            os.chmod(tmp_name, 0o600)
            result = subprocess.run(
                [
                    "mysql",
                    f"--defaults-extra-file={tmp_name}",
                    "-u",
                    "root",
                    "-e",
                    "SELECT 1;",
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
        finally:
            os.unlink(tmp_name)

    def run(self, ctx) -> None:
        pw = ctx.mariadb_root_password.replace("'", "\\'")
        sql = (
            f"ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password "
            f"USING PASSWORD('{pw}'); "
            "DELETE FROM mysql.user WHERE User=''; "
            "DELETE FROM mysql.user WHERE User='root' AND Host NOT IN "
            "('localhost', '127.0.0.1', '::1'); "
            "DROP DATABASE IF EXISTS test; "
            "DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%'; "
            "FLUSH PRIVILEGES;"
        )
        self._sudo(ctx, ["mysql", "-e", sql])
