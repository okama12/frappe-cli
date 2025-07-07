import click
from ..utils import shell
import logging

LOG_FILE = "/var/log/frappe-installer.log"

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

@click.command()
@click.pass_context
def mariadb(ctx):
    """Secure and configure MariaDB for Frappe."""
    config = ctx.obj.get('CONFIG', {})
    root_password = config.get('frappe', {}).get('mariadb_root_password', None)
    if not root_password:
        root_password = click.prompt('MariaDB root password', hide_input=True, confirmation_prompt=True)
    logger.info("[mariadb] Securing MariaDB...")
    click.echo("Setting MariaDB root password and securing installation...")
    shell.run(["sudo", "mysql", "-e", f"UPDATE mysql.user SET Password=PASSWORD('{root_password}') WHERE User='root';"])
    shell.run(["sudo", "mysql", "-e", "DELETE FROM mysql.user WHERE User='';"])
    shell.run(["sudo", "mysql", "-e", "DROP DATABASE IF EXISTS test;"])
    shell.run(["sudo", "mysql", "-e", "DELETE FROM mysql.db WHERE Db='test' OR Db='test\_%';"])
    shell.run(["sudo", "mysql", "-e", "FLUSH PRIVILEGES;"])
    click.echo("Configuring MariaDB for Frappe...")
    frappe_cnf = "/etc/mysql/mariadb.conf.d/50-frappe.cnf"
    cnf_content = '''[mysqld]
innodb_file_format=barracuda
innodb_file_per_table=1
innodb_large_prefix=1
character-set-client-handshake=FALSE
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
max_connections=1000

[mysql]
default-character-set=utf8mb4
'''
    with open("/tmp/50-frappe.cnf", "w") as f:
        f.write(cnf_content)
    shell.run(["sudo", "mv", "/tmp/50-frappe.cnf", frappe_cnf])
    shell.run(["sudo", "systemctl", "restart", "mariadb"])
    logger.info("[mariadb] MariaDB secured and configured.")
    click.secho("MariaDB secured and configured for Frappe!", fg="green") 