import logging
import os

import click
from rich.console import Console

from ..utils import shell

# Helper functions for consistent output


def print_success(message):
    Console().print(f"[bold green]✓ {message}[/bold green]")


def print_warning(message):
    Console().print(f"[bold yellow]⚠ {message}[/bold yellow]")


LOG_FILE = "/var/log/frappe-installer.log"
console = Console()


def setup_logger():
    logger = logging.getLogger("frappe_installer.backup.setup")
    logger.setLevel(logging.INFO)
    try:
        handler = logging.FileHandler(LOG_FILE)
    except PermissionError:
        handler = logging.FileHandler("frappe-installer.log")
    formatter = logging.Formatter("[%(asctime)s] %(message)s")
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


logger = setup_logger()


@click.command()
@click.option(
    "--admin-email",
    prompt="Enter admin email for backup alerts",
    help="Admin email for backup alerts",
)
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option("--site-name", prompt="Enter site name", help="Frappe site name")
def setup(admin_email, bench_name, site_name):
    """
    Set up robust backups with external HD and cron job.

    Example:
        frappe backup setup --admin-email user@example.com --bench-name mybench --site-name example.com
    """
    logger.info(
        f"[backup] Setting up backup for site: {site_name} in bench: {bench_name}"
    )
    # Test email
    console.print(f"[blue]Sending test email to {admin_email}...[/blue]")
    shell.run(
        [
            "bash",
            "-c",
            f"echo 'This is a test email from the Frappe Installer backup system.' | mail -s '[TEST] Frappe Backup Email Test' '{admin_email}'",
        ]
    )
    if not click.confirm("Did you receive the test email?", abort=True):
        print_warning("Test email not received. Please check your email settings.")
        return

    # Detect external HD by UUID
    console.print("[blue]Detecting available external drives...[/blue]")
    lsblk_out = shell.run(["lsblk", "-o", "NAME,UUID,MOUNTPOINT"]) or ""
    devices = []
    for line in lsblk_out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == "":
            devices.append((parts[0], parts[1]))
    if not devices:
        print_warning(
            "No unmounted external drives detected. Please insert the backup drive and rerun."
        )
        logger.error("[backup] No unmounted external drives detected.")
        return

    console.print("[blue]Available drives:[/blue]")
    for i, (name, uuid) in enumerate(devices):
        console.print(f"{i+1}: {name} ({uuid})")
    idx = click.prompt("Select drive number for backup", type=int, default=1) - 1
    hd_uuid = devices[idx][1]
    # Prepare backup destination
    shell.run(["sudo", "mkdir", "-p", "/mnt/external_hd"])
    fstab_line = (
        f"UUID={hd_uuid} /mnt/external_hd auto nosuid,nodev,nofail,x-gvfs-show 0 0"
    )
    fstab = shell.run(["cat", "/etc/fstab"]) or ""
    if fstab_line not in fstab:
        shell.run(["bash", "-c", f"echo '{fstab_line}' | sudo tee -a /etc/fstab"])
    shell.run(["sudo", "mount", "/mnt/external_hd"])
    backup_dest = f"/mnt/external_hd/backups/{site_name}"
    shell.run(["sudo", "mkdir", "-p", backup_dest])
    shell.run(["sudo", "chown", os.getenv("USER") or "frappe", backup_dest])
    # Create backup script
    backup_script = "/usr/local/bin/frappe_site_backup.sh"
    script_content = f"""#!/bin/bash
BACKUP_SRC1="$HOME/{bench_name}/sites/{site_name}/private/backups"
BACKUP_SRC2="$HOME/{bench_name}/sites/{site_name}/private/files"
BACKUP_SRC3="$HOME/{bench_name}/sites/{site_name}/public/files"
BACKUP_DEST="{backup_dest}"
ADMIN_EMAIL="{admin_email}"
SITE_NAME="{site_name}"

# Mount if not already
if ! mountpoint -q /mnt/external_hd; then
  sudo mount /mnt/external_hd
fi

if ! mountpoint -q /mnt/external_hd; then
  echo "[Frappe Backup] $(date): External HD not mounted. Backup skipped." | mail -s "[ALERT] Frappe Backup Failed for $SITE_NAME" "$ADMIN_EMAIL"
  exit 1
fi

TS=$(date +%Y%m%d-%H%M)
ZIPFILE="$BACKUP_DEST/backup-$TS.zip"

zip -r "$ZIPFILE" "$BACKUP_SRC1" "$BACKUP_SRC2" "$BACKUP_SRC3" > /dev/null 2>&1
if [[ $? -eq 0 && -f "$ZIPFILE" ]]; then
  echo "[Frappe Backup] $(date): Backup successful: $ZIPFILE" | mail -s "[OK] Frappe Backup Success for $SITE_NAME" "$ADMIN_EMAIL"
else
  echo "[Frappe Backup] $(date): Backup failed." | mail -s "[ALERT] Frappe Backup Failed for $SITE_NAME" "$ADMIN_EMAIL"
  exit 2
fi
# Retain only last 7 backups
ls -1t "$BACKUP_DEST"/backup-*.zip | tail -n +8 | xargs -r rm --
"""
    with open("/tmp/frappe_site_backup.sh", "w") as f:
        f.write(script_content)
    shell.run(["sudo", "mv", "/tmp/frappe_site_backup.sh", backup_script])
    shell.run(["sudo", "chmod", "+x", backup_script])
    # Add cron job
    crontab = shell.run(["sudo", "crontab", "-l"], check=False) or ""
    cron_line = f"0 2 * * * {backup_script}"
    if cron_line not in crontab:
        shell.run(
            [
                "bash",
                "-c",
                f"(sudo crontab -l 2>/dev/null | grep -v '{backup_script}'; echo '{cron_line}') | sudo crontab -",
            ]
        )
    logger.info(
        f"[backup] Backup cron job set up. Backups will be stored at {backup_dest} and alerts sent to {admin_email}."
    )
    print_success(
        f"Backup cron job set up. Backups will be stored at {backup_dest} and alerts sent to {admin_email}."
    )
