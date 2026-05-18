import os
import subprocess

import click
from rich.console import Console

from ..utils.logging import get_logger
from ..utils.shell import RichShellRunner

console = Console()
logger = get_logger("install.mariadb")


def validate_sudo():
    console.print("[yellow]Validating sudo access[/yellow]")
    result = os.system("sudo -v")
    if result != 0:
        console.print(
            "[bold red]✗ Sudo validation failed. Please ensure you have sudo privileges.[/bold red]"
        )
        raise click.ClickException("Sudo validation failed.")
    console.print("[bold green]✓ Sudo privileges validated[/bold green]")


def detect_mariadb_version():
    try:
        out = subprocess.check_output(["mysql", "-V"]).decode()
        # Prefer 'Distrib' for MariaDB/MySQL
        import re

        distrib_match = re.search(r"Distrib ([0-9.]+)-MariaDB", out)
        if distrib_match:
            return ("mariadb", distrib_match.group(1))

        distrib_mysql = re.search(r"Distrib ([0-9.]+)", out)
        if distrib_mysql:
            return ("mysql", distrib_mysql.group(1))

        # Fallback to old logic
        if "MariaDB" in out:
            version = out.split("MariaDB")[-1].split()[0]
            return ("mariadb", version)

        elif "Ver" in out:
            version = out.split("Ver")[-1].split()[0]
            return ("mysql", version)

    except Exception:
        return (None, None)


def is_root_using_socket():
    try:
        out = (
            subprocess.check_output(
                [
                    "sudo",
                    "mysql",
                    "-NBe",
                    "SELECT plugin FROM mysql.user WHERE user='root';",
                ]
            )
            .decode()
            .strip()
        )
        return "unix_socket" in out

    except Exception:
        return False


def is_already_secured():
    try:
        # 1. No anonymous users
        anon_users = (
            subprocess.check_output(
                [
                    "sudo",
                    "mysql",
                    "-NBe",
                    "SELECT COUNT(*) FROM mysql.user WHERE user='' OR user IS NULL;",
                ]
            )
            .decode()
            .strip()
        )
        if anon_users != "0":
            return False

        # 2. No users with empty passwords
        empty_pw = (
            subprocess.check_output(
                [
                    "sudo",
                    "mysql",
                    "-NBe",
                    "SELECT COUNT(*) FROM mysql.user WHERE authentication_string='' OR authentication_string IS NULL;",
                ]
            )
            .decode()
            .strip()
        )
        if empty_pw != "0":
            return False

        # 3. No test database
        test_db = (
            subprocess.check_output(
                [
                    "sudo",
                    "mysql",
                    "-NBe",
                    "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name ='test';",
                ]
            )
            .decode()
            .strip()
        )
        if test_db != "0":
            return False

        # 4. root only allowed on localhost
        root_hosts = (
            subprocess.check_output(
                [
                    "sudo",
                    "mysql",
                    "-NBe",
                    "SELECT GROUP_CONCAT(DISTINCT host) FROM mysql.user WHERE user='root';",
                ]
            )
            .decode()
            .strip()
        )
        if root_hosts not in ("localhost", "127.0.0.1", "localhost,127.0.0.1"):
            return False

        # 5. root has a password and uses mysql_native_password
        root_auth = (
            subprocess.check_output(
                [
                    "sudo",
                    "mysql",
                    "-NBe",
                    "SELECT plugin,authentication_string FROM mysql.user WHERE user='root' AND host='localhost';",
                ]
            )
            .decode()
            .strip()
        )
        if not root_auth:
            return False

        plugin, auth_string = (
            root_auth.split("\t") if "\t" in root_auth else (root_auth, "")
        )
        if plugin != "mysql_native_password" or not auth_string:
            return False

        return True

    except Exception as e:
        logger.error(f"[mariadb] Secure state check failed: {e}")
        return False


def get_mariadb_service_name():
    """Detect the correct MariaDB/MySQL service name"""
    services = ["mariadb", "mysql"]
    for service in services:
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "is-active", service],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return service

        except Exception:
            continue
    return "mariadb"  # fallback


def get_config_path():
    """Detect the correct MariaDB config directory"""
    possible_paths = [
        "/etc/mysql/mariadb.conf.d/50-frappe.cnf",
        "/etc/mysql/conf.d/50-frappe.cnf",
        "/etc/my.cnf.d/50-frappe.cnf",
    ]
    for path in possible_paths:
        config_dir = os.path.dirname(path)
        if os.path.exists(config_dir):
            return path

    return "/etc/mysql/mariadb.conf.d/50-frappe.cnf"


def get_optimal_innodb_buffer_pool_size():
    """Calculate optimal InnoDB buffer pool size based on available RAM"""
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()
        mem_total_kb = int(
            [line for line in meminfo.split("\n") if "MemTotal" in line][0].split()[1]
        )
        mem_total_gb = mem_total_kb / 1024 / 1024
        if mem_total_gb >= 8:
            return f"{int(mem_total_gb * 0.6)}G"

        elif mem_total_gb >= 4:
            return f"{int(mem_total_gb * 0.5)}G"

        else:
            return "256M"

    except Exception:
        return "256M"


def get_mariadb_config(buffer_pool_size="256M"):
    return f"""[mysqld]

# Frappe Framework Configuration
innodb_file_per_table=1
character-set-client-handshake=FALSE
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci

# Connection settings
max_connections=1000
connect_timeout=600
wait_timeout=600
max_allowed_packet=128M

# InnoDB settings
innodb_buffer_pool_size={buffer_pool_size}
innodb_log_file_size=128M
innodb_flush_log_at_trx_commit=2
innodb_file_per_table=1
innodb_buffer_pool_instances=1

# Performance
skip-name-resolve
query_cache_type=0
query_cache_size=0

# Binary logging (optional, for replication)
log_bin=mysql-bin
binlog_format=ROW
expire_logs_days=10
max_binlog_size=100M

[mysql]
default-character-set=utf8mb4
"""


def write_mariadb_config(dry_run, debug):
    config_path = get_config_path()
    buffer_pool_size = get_optimal_innodb_buffer_pool_size()
    cnf_content = get_mariadb_config(buffer_pool_size)
    if dry_run:
        console.print(
            f"[yellow][dry-run] Would write MariaDB config to {config_path}[/yellow]"
        )
        return

    with open("/tmp/50-frappe.cnf", "w") as f:
        f.write(cnf_content)
    subprocess.run(["sudo", "mv", "/tmp/50-frappe.cnf", config_path], check=True)
    console.print(f"[green]✓ MariaDB config written to {config_path}[/green]")


def validate_mariadb_version(db_type, db_version):
    """Validate MariaDB/MySQL version compatibility"""
    if db_type == "mariadb":
        min_version = (10, 3)
        recommended_version = (10, 6)
    else:  # mysql
        min_version = (8, 0)
        recommended_version = (8, 0)
    try:
        current_version = tuple(map(int, db_version.split(".")[:2]))
        if current_version < min_version:
            console.print(
                f"[bold red]ERROR: {db_type} {db_version} is not supported. Minimum version: {'.'.join(map(str, min_version))}[/bold red]"
            )
            return False

        elif current_version < recommended_version:
            console.print(
                f"[bold yellow]WARNING: {db_type} {db_version} is below recommended version {'.'.join(map(str, recommended_version))}[/bold yellow]"
            )
        return True

    except Exception:
        console.print(
            f"[bold red]ERROR: Could not parse version {db_version}[/bold red]"
        )
        return False


@click.command()
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.option(
    "--ignore-errors", is_flag=True, help="Continue even if some commands fail"
)
@click.pass_context
def mariadb(ctx, dry_run, debug, ignore_errors):
    """Secure and configure MariaDB for Frappe."""
    validate_sudo()
    shell_runner = RichShellRunner(
        console=console, dry_run=dry_run, debug=debug, module_name="install.mariadb"
    )
    db_type, db_version = detect_mariadb_version()
    if not db_type or not db_version or not db_version.replace(".", "").isdigit():
        console.print(
            "[bold red]Could not detect a valid MariaDB/MySQL version! Please ensure MariaDB or MySQL is installed and accessible as 'mysql'.[/bold red]"
        )
        raise click.ClickException("MariaDB/MySQL not found or version not detected.")
    console.print(f"Detected {db_type} version {db_version}")
    if not validate_mariadb_version(db_type, db_version):
        raise click.ClickException(
            f"{db_type} {db_version} does not meet minimum requirements."
        )
    # Secure MariaDB using the official script
    if not is_already_secured():
        console.print(
            "[yellow]MariaDB/MySQL does not appear to be secured. Please follow the interactive secure installation procedure."
        )
        # Try mariadb-secure-installation first, then fallback to mysql_secure_installation
        secure_cmds = [
            ["sudo", "mariadb-secure-installation"],
            ["sudo", "mysql_secure_installation"],
        ]
        for cmd in secure_cmds:
            rc = shell_runner.run(
                cmd,
                "Launching secure installation script (interactive)",
                ignore_errors=True,
            )
            if rc == 0:
                break
        else:
            console.print(
                "[yellow]Could not run secure installation script automatically. Please run it manually if needed.[/yellow]"
            )
    else:
        console.print("[green]MariaDB/MySQL already appears to be secured.[/green]")
    # Write modern MariaDB config
    write_mariadb_config(dry_run, debug)
    service_name = get_mariadb_service_name()
    shell_runner.run(
        ["sudo", "systemctl", "restart", service_name],
        f"Restart {service_name}",
        ignore_errors=ignore_errors,
    )
    logger.info("[mariadb] MariaDB secured and configured.")
    console.print(
        "[bold green]✓ MariaDB secured and configured for Frappe![/bold green]"
    )
