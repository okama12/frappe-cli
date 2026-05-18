import subprocess
from pathlib import Path
from .base import InstallStep, StepError

FRAPPE_MARIADB_CNF = """\
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""


class MariaDBInstallStep(InstallStep):
    name = "mariadb_install"
    description = "Install & configure MariaDB"
    CNF_PATH = "/etc/mysql/mariadb.conf.d/99-frappe.cnf"

    def check(self, ctx) -> bool:
        result = subprocess.run(["mysqladmin", "status"], capture_output=True, text=True)
        return result.returncode == 0 and Path(self.CNF_PATH).exists()

    def run(self, ctx) -> None:
        self._sudo(ctx, ["apt-get", "install", "-y", "mariadb-server", "mariadb-client"])
        self._sudo_write(ctx, FRAPPE_MARIADB_CNF, self.CNF_PATH)
        self._sudo(ctx, ["systemctl", "enable", "mariadb"])
        self._sudo(ctx, ["systemctl", "restart", "mariadb"])


class MariaDBSecureStep(InstallStep):
    name = "mariadb_secure"
    description = "Secure MariaDB"

    def check(self, ctx) -> bool:
        result = subprocess.run(
            ["mysql", "-u", "root", f"-p{ctx.mariadb_root_password}", "-e", "SELECT 1;"],
            capture_output=True, text=True,
        )
        return result.returncode == 0

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
