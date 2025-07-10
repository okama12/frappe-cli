import click
from ..utils import shell
import logging
import os
import subprocess
from rich.console import Console
from rich.prompt import Prompt, Confirm

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.mariadb")
    logger.setLevel(logging.INFO)
    try:
        handler = logging.FileHandler(LOG_FILE)
    except PermissionError:
        handler = logging.FileHandler("frappe-installer.log")
    formatter = logging.Formatter('[%(asctime)s] %(message)s')
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

logger = setup_logger()

def validate_sudo():
    console.print("[yellow]Validating sudo access[/yellow]")
    result = os.system("sudo -v")
    if result != 0:
        console.print("[bold red]✗ Sudo validation failed. Please ensure you have sudo privileges.[/bold red]")
        raise click.ClickException("Sudo validation failed.")
    console.print("[bold green]✓ Sudo privileges validated[/bold green]")

class RichShell:
    def __init__(self, console, dry_run=False, debug=False):
        self.console = console
        self.dry_run = dry_run
        self.debug = debug
    def run(self, cmd, description, ignore_errors=False, input_text=None):
        if self.debug:
            self.console.print(f"[dim]DEBUG: Command: {' '.join(cmd)}[/dim]")
        if self.dry_run:
            self.console.print(f"[yellow][dry-run] {description}: {' '.join(cmd)}")
            logger.info(f"[dry-run] {description}: {' '.join(cmd)}")
            return 0
        self.console.print(f"[blue]{description}...[/blue]")
        try:
            if input_text:
                result = subprocess.run(cmd, input=input_text.encode(), check=True)
            else:
                result = subprocess.run(cmd, check=True)
            logger.info(f"[mariadb] Success: {description}")
            self.console.print(f"[green]✓ {description} - Complete[/green]")
            return result.returncode
        except Exception as e:
            logger.error(f"[mariadb] Failed: {' '.join(cmd)} - {e}")
            self.console.print(f"[bold red]✗ {description} failed: {e}[/bold red]")
            if not ignore_errors:
                raise click.ClickException(str(e))
            else:
                self.console.print(f"[yellow]Continuing despite error...[/yellow]")
            return 1

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
        out = subprocess.check_output([
            "sudo", "mysql", "-NBe", "SELECT plugin FROM mysql.user WHERE user='root';"
        ]).decode().strip()
        return "unix_socket" in out
    except Exception:
        return False

def is_already_secured():
    try:
        out = subprocess.check_output([
            "sudo", "mysql", "-NBe", "SELECT COUNT(*) FROM mysql.user WHERE user='' OR host='localhost' AND password='';"
        ]).decode().strip()
        return out == "0"
    except Exception:
        return False

def get_config_path():
    # Ubuntu 20.04/22.04/24.04 all use this path for MariaDB 10.3+/10.6+
    return "/etc/mysql/mariadb.conf.d/50-frappe.cnf"

def write_mariadb_config(dry_run, debug):
    config_path = get_config_path()
    cnf_content = '''[mysqld]
# Modern Frappe/MariaDB config
innodb_file_per_table=1
character-set-client-handshake=FALSE
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
max_connections=1000
innodb_buffer_pool_size=256M
innodb_log_file_size=128M
innodb_flush_log_at_trx_commit=2
skip-name-resolve

[mysql]
default-character-set=utf8mb4
'''
    if dry_run:
        console.print(f"[yellow][dry-run] Would write MariaDB config to {config_path}[/yellow]")
        return
    with open("/tmp/50-frappe.cnf", "w") as f:
        f.write(cnf_content)
    subprocess.run(["sudo", "mv", "/tmp/50-frappe.cnf", config_path], check=True)
    console.print(f"[green]✓ MariaDB config written to {config_path}[/green]")

def create_frappe_user(shell_runner, frappe_user, frappe_password, ignore_errors, dry_run):
    # Create user and database if not exists
    shell_runner.run([
        "sudo", "mysql", "-e",
        f"CREATE USER IF NOT EXISTS '{frappe_user}'@'localhost' IDENTIFIED BY '{frappe_password}';"
    ], f"Create MariaDB user '{frappe_user}'", ignore_errors=ignore_errors)
    shell_runner.run([
        "sudo", "mysql", "-e",
        f"GRANT ALL PRIVILEGES ON *.* TO '{frappe_user}'@'localhost' WITH GRANT OPTION;"
    ], f"Grant privileges to '{frappe_user}'", ignore_errors=ignore_errors)
    shell_runner.run([
        "sudo", "mysql", "-e",
        f"CREATE DATABASE IF NOT EXISTS frappe DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    ], "Create Frappe database if needed", ignore_errors=ignore_errors)

@click.command()
@click.option('--dry-run', is_flag=True, help='Simulate commands without executing them')
@click.option('--debug', is_flag=True, help='Enable debug output with command details')
@click.option('--ignore-errors', is_flag=True, help='Continue even if some commands fail')
@click.option('--frappe-user', default='frappe', help='Frappe DB user to create')
@click.option('--frappe-password', default=None, help='Frappe DB user password')
@click.pass_context
def mariadb(ctx, dry_run, debug, ignore_errors, frappe_user, frappe_password):
    """Secure and configure MariaDB for Frappe."""
    validate_sudo()
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
    db_type, db_version = detect_mariadb_version()
    if not db_type or not db_version or not db_version.replace('.', '').isdigit():
        console.print("[bold red]Could not detect a valid MariaDB/MySQL version! Please ensure MariaDB or MySQL is installed and accessible as 'mysql'.[/bold red]")
        raise click.ClickException("MariaDB/MySQL not found or version not detected.")
    console.print(f"Detected {db_type} version {db_version}")
    if db_type == "mariadb":
        try:
            version_tuple = tuple(map(int, db_version.split(".")))
        except Exception:
            version_tuple = (0, 0)
        if version_tuple < (10, 6):
            console.print("[bold red]MariaDB 10.6+ is required for best compatibility.[/bold red]")
    if db_type == "mysql":
        try:
            version_tuple = tuple(map(int, db_version.split(".")))
        except Exception:
            version_tuple = (0, 0)
        if version_tuple < (8, 0):
            console.print("[bold red]MySQL 8.0+ is required for best compatibility.[/bold red]")
    # Secure MariaDB using the official script
    if not is_already_secured():
        # Try mariadb-secure-installation first, then fallback to mysql_secure_installation
        secure_cmds = [
            ["sudo", "mariadb-secure-installation", "--use-default"],
            ["sudo", "mysql_secure_installation", "--use-default"]
        ]
        for cmd in secure_cmds:
            rc = shell_runner.run(cmd, "Running secure installation script", ignore_errors=True)
            if rc == 0:
                break
        else:
            console.print("[yellow]Could not run secure installation script automatically. Please run it manually if needed.[/yellow]")
    else:
        console.print("[green]MariaDB/MySQL already appears to be secured.[/green]")
    # Check root authentication method
    if is_root_using_socket():
        console.print("[cyan]Root user uses unix_socket authentication. No password set for root (recommended for local use).[/cyan]")
    else:
        set_root = Confirm.ask("Root does not use unix_socket. Set a root password?", default=False)
        if set_root:
            root_password = Prompt.ask('Enter new MariaDB root password', password=True)
            shell_runner.run([
                "sudo", "mysql", "-e",
                f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{root_password}';"
            ], "Set root password", ignore_errors=ignore_errors)
    # Write modern MariaDB config
    write_mariadb_config(dry_run, debug)
    # Optionally create Frappe user
    if frappe_password is None:
        frappe_password = Prompt.ask(f"Enter password for MariaDB user '{frappe_user}'", password=True)
    create_frappe_user(shell_runner, frappe_user, frappe_password, ignore_errors, dry_run)
    shell_runner.run(["sudo", "systemctl", "restart", "mariadb"], "Restart MariaDB", ignore_errors=ignore_errors)
    logger.info("[mariadb] MariaDB secured and configured.")
    console.print("[bold green]✓ MariaDB secured and configured for Frappe![/bold green]")