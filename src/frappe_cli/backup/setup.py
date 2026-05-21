"""``fp backup setup`` — configure rotated backups to an external drive.

The original implementation passed user-supplied values (admin email, bench
name, site name, fstab UUID) inside ``bash -c "…"`` strings, which is shell
injection waiting to happen if any of those fields contain a quote or
``$(...)``. This rewrite:

* Validates ``bench_name``/``site_name``/``admin_email`` with strict
  allowlists from :mod:`frappe_cli.utils.validators`.
* Uses ``subprocess`` with argv lists everywhere; no ``bash -c`` interpolation.
* Streams fstab and crontab edits via ``sudo tee`` with stdin instead of
  inline ``echo '...' | sudo tee``.
* Writes the backup script with ``shlex.quote`` for every interpolated value
  so a hostile site name like ``'; rm -rf /'`` cannot break out.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path

import click
from rich.console import Console

from ..utils import shell
from ..utils.errors import ValidationError
from ..utils.logging import get_logger
from ..utils.validators import validate_bench_name, validate_email, validate_site_name


def print_success(message: str) -> None:
    Console().print(f"[bold green]✓ {message}[/bold green]")


def print_warning(message: str) -> None:
    Console().print(f"[bold yellow]⚠ {message}[/bold yellow]")


console = Console()
logger = get_logger("backup.setup")


def _sudo_write(path: str, content: str, mode: str = "644") -> None:
    """Write *content* to a privileged *path* without going through a shell."""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".tmp", encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_name = tmp.name
    try:
        subprocess.run(["sudo", "cp", tmp_name, path], check=True)
        subprocess.run(["sudo", "chmod", mode, path], check=True)
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def _sudo_append(path: str, line: str) -> None:
    """Append *line* (followed by newline) to a privileged *path* via tee -a."""
    proc = subprocess.run(
        ["sudo", "tee", "-a", path],
        input=line.rstrip("\n") + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    logger.debug(f"sudo tee -a {path}: {proc.stdout!r}")


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
def setup(admin_email: str, bench_name: str, site_name: str) -> None:
    """Set up rotated nightly backups to an external HD with email alerts.

    Example:

        fp backup setup --admin-email user@example.com \
            --bench-name mybench --site-name example.com
    """
    try:
        admin_email = validate_email(admin_email)
        bench_name = validate_bench_name(bench_name)
        site_name = validate_site_name(site_name)
    except ValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    logger.info(
        f"[backup] Setting up backup for site: {site_name} in bench: {bench_name}"
    )

    # Test email — keep this on argv-free path (echo body via stdin).
    console.print(f"[blue]Sending test email to {admin_email}...[/blue]")
    try:
        subprocess.run(
            [
                "mail",
                "-s",
                "[TEST] Frappe Backup Email Test",
                admin_email,
            ],
            input="This is a test email from the Frappe Installer backup system.\n",
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print_warning(f"Failed to send test email: {exc}")
        if not click.confirm("Continue anyway?", default=False):
            return

    if not click.confirm("Did you receive the test email?", abort=True):
        print_warning("Test email not received. Please check your email settings.")
        return

    # Detect unmounted external drives.
    console.print("[blue]Detecting available external drives...[/blue]")
    lsblk_out = shell.run(["lsblk", "-o", "NAME,UUID,MOUNTPOINT"]) or ""
    devices: list[tuple[str, str]] = []
    for line in lsblk_out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] == "":
            devices.append((parts[0], parts[1]))
    if not devices:
        print_warning(
            "No unmounted external drives detected. "
            "Please insert the backup drive and rerun."
        )
        logger.error("[backup] No unmounted external drives detected.")
        return

    console.print("[blue]Available drives:[/blue]")
    for i, (name, uuid) in enumerate(devices):
        console.print(f"{i + 1}: {name} ({uuid})")
    idx = click.prompt("Select drive number for backup", type=int, default=1) - 1
    if not 0 <= idx < len(devices):
        raise click.ClickException("Drive selection out of range.")
    hd_uuid = devices[idx][1]

    # UUIDs are hex + hyphens; sanity-check before letting it near fstab.
    if not all(c.isalnum() or c == "-" for c in hd_uuid):
        raise click.ClickException(f"Refusing to use suspicious UUID: {hd_uuid!r}")

    # Prepare /mnt/external_hd + fstab entry.
    shell.run(["sudo", "mkdir", "-p", "/mnt/external_hd"])
    fstab_line = (
        f"UUID={hd_uuid} /mnt/external_hd auto nosuid,nodev,nofail,x-gvfs-show 0 0"
    )
    fstab = Path("/etc/fstab").read_text() if Path("/etc/fstab").exists() else ""
    if fstab_line not in fstab:
        _sudo_append("/etc/fstab", fstab_line)
    shell.run(["sudo", "mount", "/mnt/external_hd"])

    backup_dest = f"/mnt/external_hd/backups/{site_name}"
    shell.run(["sudo", "mkdir", "-p", backup_dest])
    shell.run(["sudo", "chown", os.getenv("USER") or "frappe", backup_dest])

    # Build backup script. Every interpolated value is shlex.quote-d so a
    # hostile site_name like "$(reboot)" or "'; rm -rf /;'" stays literal.
    home = Path.home()
    src1 = home / bench_name / "sites" / site_name / "private" / "backups"
    src2 = home / bench_name / "sites" / site_name / "private" / "files"
    src3 = home / bench_name / "sites" / site_name / "public" / "files"

    qsite = shlex.quote(site_name)
    qemail = shlex.quote(admin_email)
    qsrc1 = shlex.quote(str(src1))
    qsrc2 = shlex.quote(str(src2))
    qsrc3 = shlex.quote(str(src3))
    qdest = shlex.quote(backup_dest)

    script_content = f"""#!/bin/bash
set -u
SITE_NAME={qsite}
ADMIN_EMAIL={qemail}
BACKUP_SRC1={qsrc1}
BACKUP_SRC2={qsrc2}
BACKUP_SRC3={qsrc3}
BACKUP_DEST={qdest}

if ! mountpoint -q /mnt/external_hd; then
  sudo mount /mnt/external_hd
fi

if ! mountpoint -q /mnt/external_hd; then
  echo "[Frappe Backup] $(date): External HD not mounted. Backup skipped." \\
    | mail -s "[ALERT] Frappe Backup Failed for $SITE_NAME" "$ADMIN_EMAIL"
  exit 1
fi

TS=$(date +%Y%m%d-%H%M)
ZIPFILE="$BACKUP_DEST/backup-$TS.zip"

zip -r "$ZIPFILE" "$BACKUP_SRC1" "$BACKUP_SRC2" "$BACKUP_SRC3" > /dev/null 2>&1
if [[ $? -eq 0 && -f "$ZIPFILE" ]]; then
  echo "[Frappe Backup] $(date): Backup successful: $ZIPFILE" \\
    | mail -s "[OK] Frappe Backup Success for $SITE_NAME" "$ADMIN_EMAIL"
else
  echo "[Frappe Backup] $(date): Backup failed." \\
    | mail -s "[ALERT] Frappe Backup Failed for $SITE_NAME" "$ADMIN_EMAIL"
  exit 2
fi

# Retain only last 7 backups.
ls -1t "$BACKUP_DEST"/backup-*.zip | tail -n +8 | xargs -r rm --
"""

    backup_script = "/usr/local/bin/frappe_site_backup.sh"
    _sudo_write(backup_script, script_content, mode="755")

    # Add cron entry without bash -c interpolation.
    cron_line = f"0 2 * * * {backup_script}"
    crontab = shell.run(["sudo", "crontab", "-l"], check=False) or ""
    if cron_line in crontab:
        logger.info("[backup] cron entry already present")
    else:
        new_crontab = (
            "\n".join(
                line
                for line in crontab.splitlines()
                if backup_script not in line and line.strip()
            )
            + f"\n{cron_line}\n"
        )
        subprocess.run(
            ["sudo", "crontab", "-"], input=new_crontab, text=True, check=True
        )

    logger.info(
        f"[backup] Backup cron job set up. Backups will be stored at {backup_dest} "
        f"and alerts sent to {admin_email}."
    )
    print_success(
        f"Backup cron job set up. Backups will be stored at {backup_dest} "
        f"and alerts sent to {admin_email}."
    )
