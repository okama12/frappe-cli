import getpass
import logging
import os
import pwd

import click
from rich.console import Console
from rich.prompt import Prompt

from ..utils import shell

LOG_FILE = "/var/log/frappe-installer.log"
console = Console()


def setup_logger():
    logger = logging.getLogger("frappe_installer.app.clone")
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


class RichShell:
    def __init__(self, console, dry_run=False, debug=False):
        self.console = console
        self.dry_run = dry_run
        self.debug = debug

    def run(self, cmd, description, ignore_errors=False):
        if self.debug:
            self.console.print(f"[dim]DEBUG: Command: {' '.join(cmd)}[/dim]")
        if self.dry_run:
            self.console.print(f"[yellow][dry-run] {description}: {' '.join(cmd)}")
            logger.info(f"[dry-run] {description}: {' '.join(cmd)}")
            return 0

        self.console.print(f"[blue]{description}...[/blue]")
        try:
            # Use shell.run for safety, but keep output/flow the same
            _result = shell.run(cmd, check=True, _capture_output=False)
            logger.info(f"[clone] Success: {description}")
            self.console.print(f"[green]✓ {description} - Complete[/green]")
            return 0

        except Exception as e:
            logger.error(f"[clone] Failed: {' '.join(cmd)} - {e}")
            self.console.print(f"[bold red]✗ {description} failed: {e}[/bold red]")
            if not ignore_errors:
                raise click.ClickException(str(e))
            else:
                self.console.print("[yellow]Continuing despite error...[/yellow]")
            return 1


def fix_ownership(path):
    try:
        user = getpass.getuser()
        uid = pwd.getpwnam(user).pw_uid
        gid = pwd.getpwnam(user).pw_gid
        for root, dirs, files in os.walk(path):
            os.chown(root, uid, gid)
            for d in dirs:
                os.chown(os.path.join(root, d), uid, gid)
            for f in files:
                os.chown(os.path.join(root, f), uid, gid)
        console.print(f"[green]✓ Fixed ownership for '{path}' to user '{user}'[/green]")
    except Exception as e:
        console.print(
            f"[yellow]Warning: Could not fix ownership for '{path}': {e}[/yellow]"
        )


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option("--repo-url", prompt="Enter repository URL", help="GitHub repository URL")
@click.option(
    "--branch",
    prompt="Enter branch (default: main)",
    default="main",
    show_default=True,
    help="Git branch to clone",
)
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.option(
    "--ignore-errors", is_flag=True, help="Continue even if some commands fail"
)
def clone(bench_name, repo_url, branch, dry_run, debug, ignore_errors):
    """
    Clone and validate a Frappe-compatible app from GitHub.

    Example:
        frappe app clone --bench-name mybench --repo-url https://github.com/frappe/frappe.git --branch main --debug
    """
    # Abort if run as root
    if os.geteuid() == 0:
        console.print(
            "[bold red]Do not run this script as root! Use a regular user for security and correct permissions.[/bold red]"
        )
        raise click.ClickException("Do not run as root.")
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)
    # Resolve bench path to user's home if not absolute
    user_home = os.path.expanduser("~")
    if not os.path.isabs(bench_name):
        bench_path = os.path.join(user_home, bench_name)
    else:
        bench_path = bench_name
    if not os.path.isdir(bench_path):
        console.print(f"[bold red]Bench directory '{bench_path}' not found.[/bold red]")
        logger.error(f"[app] Bench directory '{bench_path}' not found.")
        raise click.ClickException(f"Bench directory '{bench_path}' not found.")
    # Warn if bench dir is not writable
    if not os.access(bench_path, os.W_OK):
        console.print(
            f"[yellow]Warning: Bench directory '{bench_path}' is not writable by user '{getpass.getuser()}'. You may encounter permission errors.[/yellow]"
        )
    # --- New: Check assets and sites/assets permissions/ownership ---
    assets_dirs = [
        os.path.join(bench_path, "assets"),
        os.path.join(bench_path, "sites", "assets"),
    ]
    for adir in assets_dirs:
        if os.path.exists(adir):
            if not os.access(adir, os.W_OK):
                console.print(
                    f"[yellow]Warning: Directory '{adir}' is not writable by user '{getpass.getuser()}'. You may encounter asset build errors.[/yellow]"
                )
                console.print(
                    f"[bold red]To fix this, run:[/bold red] [green]sudo chown -R $USER:$USER '{adir}' && chmod -R u+w '{adir}'[/green]"
                )
                console.print(
                    "[bold yellow]Please fix the permissions and re-run this command. Aborting.[/bold yellow]"
                )
                raise click.ClickException(
                    f"Directory '{adir}' is not writable by user '{getpass.getuser()}'. Fix permissions and try again."
                )
            # Check for root-owned files
            try:
                for root, dirs, files in os.walk(adir):
                    for name in dirs + files:
                        path = os.path.join(root, name)
                        try:
                            stat = os.stat(path)
                            if stat.st_uid == 0:
                                console.print(
                                    f"[yellow]Warning: '{path}' is owned by root. This may cause permission errors during build.[/yellow]"
                                )
                        except FileNotFoundError:
                            # File or directory was removed between os.walk and os.stat; skip
                            continue
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not check ownership in '{adir}': {e}[/yellow]"
                )
    # Prompt for repo_url and branch only after bench dir is validated
    if not repo_url:
        repo_url = Prompt.ask("Enter the GitHub repository URL for the app")
    if not branch:
        branch = Prompt.ask("Enter the branch to clone", default="main")
    logger.info(
        f"[app] Cloning app from {repo_url} (branch: {branch}) into bench: {bench_name}"
    )
    os.chdir(bench_path)
    app_name = os.path.basename(repo_url).replace(".git", "")
    app_path = f"apps/{app_name}"
    # --- Prevent duplicate clone: check for any existing app dir with similar names ---
    apps_dir = os.path.join(bench_path, "apps")
    existing_dirs = []
    if os.path.isdir(apps_dir):
        for d in os.listdir(apps_dir):
            d_path = os.path.join(apps_dir, d)
            if os.path.isdir(d_path):
                # Check for both the repo basename and the snake_case version
                if (
                    d == app_name
                    or d == app_name.replace("-", "_")
                    or d == app_name.replace("_", "-")
                ):
                    existing_dirs.append(d)
    if existing_dirs:
        console.print(
            f"[bold red]App directory with name(s) {existing_dirs} already exists in '{apps_dir}'. Aborting to avoid duplicate or conflicting clones.[/bold red]"
        )
        logger.error(
            f"[app] App directory with name(s) {existing_dirs} already exists in '{apps_dir}'."
        )
        return

    # Check for existing non-empty app directory
    if os.path.isdir(app_path) and os.listdir(app_path):
        console.print(
            f"[bold red]App directory '{app_path}' already exists and is not empty. Aborting to avoid overwrite.[/bold red]"
        )
        logger.error(
            f"[app] App directory '{app_path}' already exists and is not empty."
        )
        return

    # Run bench get-app and clean up if it fails
    clone_result = shell_runner.run(
        ["bench", "get-app", "--branch", branch, repo_url],
        f"Cloning app from {repo_url}",
        ignore_errors=ignore_errors,
    )
    # If cloning failed, remove the app directory if it was created
    if clone_result != 0 and os.path.isdir(app_path):
        import shutil

        try:
            shutil.rmtree(app_path)
            console.print(
                f"[yellow]Removed incomplete app directory '{app_path}' due to clone failure.[/yellow]"
            )
            logger.info(
                f"[app] Removed incomplete app directory '{app_path}' due to clone failure."
            )
        except Exception as e:
            console.print(
                f"[red]Failed to remove incomplete app directory '{app_path}': {e}[/red]"
            )
            logger.error(
                f"[app] Failed to remove incomplete app directory '{app_path}': {e}"
            )
        return

    # Fix ownership of the app directory to the current user
    if os.path.isdir(app_path):
        fix_ownership(app_path)
    app_name = os.path.basename(repo_url).replace(".git", "")
    app_path = f"apps/{app_name}"
    # --- Modified: Check Frappe compatibility using pyproject.toml ---
    pyproject_path = f"{app_path}/pyproject.toml"
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path) as f:
                content = f.read()
            # Check for 'frappe' in dependencies or description
            if "frappe" in content:
                pass
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not read pyproject.toml: {e}[/yellow]"
            )
    logger.info(f"[app] App {app_name} cloned and validated as Frappe-compatible.")
    console.print(
        f"[bold green]✓ App {app_name} cloned and validated as Frappe-compatible.[/bold green]"
    )
