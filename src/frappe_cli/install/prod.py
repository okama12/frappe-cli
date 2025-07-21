import logging
import os
import subprocess

import click
from rich.console import Console

# LOG_FILE = "/var/log/frappe-installer.log" # This path requires root permissions
# Fallback to a user-writable log file if /var/log is not accessible
try:
    if not os.path.exists("/var/log"):
        os.makedirs("/var/log")
    LOG_FILE = "/var/log/frappe-installer.log"
except OSError:
    LOG_FILE = (
        "frappe-installer.log"  # Log in current directory if /var/log is not writable
    )

console = Console()


def setup_logger():
    """Sets up a logger for the Frappe installer, logging to a file."""
    logger = logging.getLogger("frappe_installer.install.prod")
    logger.setLevel(logging.INFO)
    try:
        handler = logging.FileHandler(LOG_FILE)
    except PermissionError:
        # Fallback for when /var/log is not writable
        handler = logging.FileHandler("frappe-installer.log")
    formatter = logging.Formatter("[%(asctime)s] %(message)s")
    handler.setFormatter(formatter)
    # Ensure handlers are not duplicated if setup_logger is called multiple times
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


logger = setup_logger()


class RichShell:
    """A wrapper for subprocess commands with Rich console output and logging."""

    def __init__(self, console, dry_run=False, debug=False):
        self.console = console
        self.dry_run = dry_run
        self.debug = debug

    def run(self, cmd, description, ignore_errors=False, input_text=None):
        """
        Runs a shell command.

        Args:
            cmd (list): The command and its arguments as a list.
            description (str): A human-readable description of the command.
            ignore_errors (bool): If True, continues execution even if the command fails.
            input_text (str): Text to pass to the command's stdin.

        Returns:
            int: The return code of the executed command.
        """
        cmd_str = " ".join(cmd)
        if self.debug:
            self.console.print(f"[dim]DEBUG: Command: {cmd_str}[/dim]")
        if self.dry_run:
            self.console.print(f"[yellow][dry-run] {description}: {cmd_str}")
            logger.info(f"[dry-run] {description}: {cmd_str}")
            return 0

        self.console.print(f"[blue]{description}...[/blue]")
        try:
            # Capture output and decode as text for better error reporting
            if input_text:
                result = subprocess.run(
                    cmd, input=input_text, check=True, capture_output=True, text=True
                )
            else:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)

            logger.info(f"[prod] Success: {description}")
            self.console.print(f"[green]✓ {description} - Complete[/green]")
            if self.debug and result.stdout:
                self.console.print(f"[dim]STDOUT:\n{result.stdout}[/dim]")
            if self.debug and result.stderr:
                self.console.print(f"[dim]STDERR:\n{result.stderr}[/dim]")
            return result.returncode

        except subprocess.CalledProcessError as e:
            logger.error(f"[prod] Failed: {cmd_str} - {e}")
            self.console.print(f"[bold red]✗ {description} failed:[/bold red]")
            self.console.print(f"[red]STDOUT: {e.stdout}[/red]")
            self.console.print(f"[red]STDERR: {e.stderr}[/red]")
            if not ignore_errors:
                raise click.ClickException(f"Command failed: {cmd_str}\n{e.stderr}")
            else:
                self.console.print("[yellow]Continuing despite error...[/yellow]")
            return e.returncode

        except Exception as e:
            logger.error(f"[prod] Failed: {cmd_str} - {e}")
            self.console.print(f"[bold red]✗ {description} failed: {e}[/bold red]")
            if not ignore_errors:
                raise click.ClickException(str(e))
            else:
                self.console.print("[yellow]Continuing despite error...[/yellow]")
            return 1


def clean_nginx_upstreams(conf_path):
    """
    Cleans duplicate upstream blocks from a single Nginx configuration file.
    Returns True if any duplicates were cleaned, False otherwise.
    """
    if not os.path.isfile(conf_path):
        return False

    console.print(f"[blue]Cleaning nginx config: {conf_path}[/blue]")

    try:
        with open(conf_path, "r") as f:
            lines = f.readlines()

        upstreams = set()
        new_lines = []
        i = 0
        cleaned = False

        while i < len(lines):
            line = lines[i]
            # Check for 'upstream ' followed by a name and then '{' on the same line
            if line.strip().startswith("upstream ") and "{" in line:
                # Extract upstream name, handling potential extra spaces or comments
                parts = line.strip().split()
                if len(parts) >= 2:
                    upstream_name = parts[1].rstrip("{").strip()
                else:
                    new_lines.append(line)  # Malformed upstream line, keep it
                    i += 1
                    continue

                if upstream_name in upstreams:
                    # Skip this entire duplicate upstream block
                    console.print(
                        f"[yellow]Removing duplicate upstream block '{upstream_name}' from {conf_path}[/yellow]"
                    )
                    logger.warning(
                        f"[prod] Removing duplicate upstream block '{upstream_name}' from {conf_path}"
                    )
                    cleaned = True

                    # Skip the entire block by counting braces
                    brace_count = line.count("{") - line.count("}")
                    i += 1
                    while i < len(lines) and brace_count > 0:
                        brace_count += lines[i].count("{") - lines[i].count("}")
                        i += 1
                    continue  # Continue to the next line in the outer loop
                else:
                    upstreams.add(upstream_name)
                    # Keep the first occurrence of the block
                    new_lines.append(line)
                    i += 1
                    brace_count = line.count("{") - line.count("}")
                    while i < len(lines) and brace_count > 0:
                        new_lines.append(lines[i])
                        brace_count += lines[i].count("{") - lines[i].count("}")
                        i += 1
                    continue  # Continue to the next line in the outer loop

            new_lines.append(line)  # Append non-upstream lines
            i += 1

        if cleaned:
            # Write back the cleaned config
            with open(conf_path, "w") as f:
                f.writelines(new_lines)
            console.print(
                f"[green]✓ Cleaned duplicate upstream blocks in {conf_path}[/green]"
            )
            logger.info(f"[prod] Cleaned duplicate upstream blocks in {conf_path}")
            return True

        else:
            console.print(
                f"[green]✓ No duplicate upstream blocks found in {conf_path}[/green]"
            )
            return False

    except Exception as e:
        console.print(
            f"[bold red]✗ Failed to clean nginx config {conf_path}: {e}[/bold red]"
        )
        logger.error(f"[prod] Failed to clean nginx config {conf_path}: {e}")
        return False


def clean_all_nginx_configs():
    """
    Cleans all Nginx configuration files for duplicate upstreams.
    This iterates through sites-enabled and sites-available and cleans duplicates within each file.
    """
    nginx_sites_enabled = "/etc/nginx/sites-enabled"
    nginx_sites_available = "/etc/nginx/sites-available"
    cleaned_any = False

    # Clean all files in sites-enabled
    if os.path.isdir(nginx_sites_enabled):
        for filename in os.listdir(nginx_sites_enabled):
            file_path = os.path.join(nginx_sites_enabled, filename)
            # Clean the symlink target if it's a symlink
            if os.path.islink(file_path):
                real_path = os.path.realpath(file_path)
                if clean_nginx_upstreams(real_path):
                    cleaned_any = True
            # Also clean the file itself (in case it's a regular file in sites-enabled)
            if os.path.isfile(file_path):
                if clean_nginx_upstreams(file_path):
                    cleaned_any = True

    # Clean all files in sites-available
    if os.path.isdir(nginx_sites_available):
        for filename in os.listdir(nginx_sites_available):
            file_path = os.path.join(nginx_sites_available, filename)
            if os.path.isfile(file_path):
                if clean_nginx_upstreams(file_path):
                    cleaned_any = True
    return cleaned_any


def validate_nginx_config():
    """Validates the overall Nginx configuration using 'nginx -t'."""
    console.print("[blue]Validating Nginx configuration...[/blue]")
    try:
        result = subprocess.run(["sudo", "nginx", "-t"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[green]✓ Nginx configuration is valid[/green]")
            return True

        else:
            console.print("[bold red]✗ Nginx configuration test failed:[/bold red]")
            console.print(
                f"[red]{result.stdout}[/red]"
            )  # Nginx -t often puts errors on stdout
            console.print(f"[red]{result.stderr}[/red]")
            return False

    except FileNotFoundError:
        console.print(
            "[bold red]✗ Nginx command not found. Please ensure Nginx is installed.[/bold red]"
        )
        return False

    except Exception as e:
        console.print(f"[bold red]✗ Failed to test nginx config: {e}[/bold red]")
        return False


@click.command()
@click.option(
    "--bench-name",
    prompt="Enter bench name (folder)",
    default="frappe-bench",
    show_default=True,
    help="Bench directory name",
)
@click.option(
    "--dry-run", is_flag=True, help="Simulate commands without executing them"
)
@click.option("--debug", is_flag=True, help="Enable debug output with command details")
@click.option(
    "--ignore-errors", is_flag=True, help="Continue even if some commands fail"
)
@click.pass_context
def prod(ctx, bench_name, dry_run, debug, ignore_errors):
    """Setup production environment for Frappe."""
    logger.info(f"[prod] Setting up production environment for bench: {bench_name}")

    # Determine bench path
    user_home = os.path.expanduser("~")
    if not os.path.isabs(bench_name):
        bench_path = os.path.join(user_home, bench_name)
    else:
        bench_path = bench_name

    # Validate bench directory exists
    if not os.path.isdir(bench_path):
        console.print(f"[bold red]Bench directory '{bench_path}' not found.[/bold red]")
        logger.error(f"[prod] Bench directory '{bench_path}' not found.")
        raise click.ClickException(f"Bench directory '{bench_path}' not found.")

    # Change to bench directory
    os.chdir(bench_path)
    shell_runner = RichShell(console, dry_run=dry_run, debug=debug)

    # Find bench command
    try:
        bench_cmd = subprocess.check_output(["which", "bench"], text=True).strip()
    except subprocess.CalledProcessError:
        console.print(
            "[bold red]Bench command not found in PATH. Please ensure bench is installed.[/bold red]"
        )
        logger.error("[prod] Bench command not found in PATH.")
        raise click.ClickException("Bench command not found in PATH.")

    # --- CRITICAL NGINX CLEANUP BEFORE RUNNING BENCH SETUP PRODUCTION ---
    console.print(
        "[blue]Performing comprehensive Nginx configuration cleanup...[/blue]"
    )
    if not dry_run:
        # Explicitly remove potential old default Frappe bench Nginx config files
        # This targets the common 'frappe-bench' default config location
        shell_runner.run(
            ["sudo", "rm", "-f", "/etc/nginx/sites-enabled/frappe-bench"],
            "Removing old default bench Nginx symlink",
            ignore_errors=True,
        )
        shell_runner.run(
            ["sudo", "rm", "-f", "/etc/nginx/sites-available/frappe-bench"],
            "Removing old default bench Nginx config file",
            ignore_errors=True,
        )

        # Explicitly remove potential old Nginx config files for the *current* bench name
        # This covers cases where the script was run before for the same bench_name
        current_bench_nginx_symlink = os.path.join(
            "/etc/nginx/sites-enabled", os.path.basename(bench_path)
        )
        current_bench_nginx_config = os.path.join(
            "/etc/nginx/sites-available", os.path.basename(bench_path)
        )
        shell_runner.run(
            ["sudo", "rm", "-f", current_bench_nginx_symlink],
            f"Removing old '{os.path.basename(bench_path)}' Nginx symlink",
            ignore_errors=True,
        )
        shell_runner.run(
            ["sudo", "rm", "-f", current_bench_nginx_config],
            f"Removing old '{os.path.basename(bench_path)}' Nginx config file",
            ignore_errors=True,
        )

        # Also run the general cleaner for any remaining internal duplicates in other files
        clean_all_nginx_configs()

    # Validate nginx config after cleanup but before running bench setup production
    if not dry_run:
        if not validate_nginx_config():
            console.print(
                "[bold red]Nginx configuration is invalid even after cleanup. Please investigate manually.[/bold red]"
            )
            if not ignore_errors:
                raise click.ClickException(
                    "Invalid nginx configuration after initial cleanup"
                )

    # Run production setup with automatic confirmation
    console.print("[blue]Running bench setup production...[/blue]")
    production_cmd = ["sudo", bench_cmd, "setup", "production", os.getenv("USER")]

    # Handle interactive prompts automatically for supervisor and nginx overwrite
    input_responses = "y\ny\n"  # Answer 'y' to supervisor and nginx overwrite prompts

    try:
        if not dry_run:
            result = subprocess.run(
                production_cmd,
                input=input_responses,  # Pass input as string since text=True
                text=True,
                capture_output=True,
            )

            if result.returncode != 0:
                console.print("[bold red]✗ Production setup failed:[/bold red]")
                console.print(f"[red]STDOUT: {result.stdout}[/red]")
                console.print(f"[red]STDERR: {result.stderr}[/red]")

                # Attempt to clean up and retry once
                console.print("[yellow]Attempting to clean up and retry...[/yellow]")
                # Re-run comprehensive cleanup after a failed bench setup production
                if not dry_run:
                    shell_runner.run(
                        ["sudo", "rm", "-f", "/etc/nginx/sites-enabled/frappe-bench"],
                        "Removing old default bench Nginx symlink (retry)",
                        ignore_errors=True,
                    )
                    shell_runner.run(
                        ["sudo", "rm", "-f", "/etc/nginx/sites-available/frappe-bench"],
                        "Removing old default bench Nginx config file (retry)",
                        ignore_errors=True,
                    )
                    shell_runner.run(
                        ["sudo", "rm", "-f", current_bench_nginx_symlink],
                        f"Removing old '{os.path.basename(bench_path)}' Nginx symlink (retry)",
                        ignore_errors=True,
                    )
                    shell_runner.run(
                        ["sudo", "rm", "-f", current_bench_nginx_config],
                        f"Removing old '{os.path.basename(bench_path)}' Nginx config file (retry)",
                        ignore_errors=True,
                    )
                    clean_all_nginx_configs()  # Clean internal duplicates again

                if validate_nginx_config():
                    console.print("[blue]Retrying production setup...[/blue]")
                    result = subprocess.run(
                        production_cmd,
                        input=input_responses,
                        text=True,
                        capture_output=True,
                    )

                    if result.returncode != 0:
                        if not ignore_errors:
                            # --- BEGIN: Enhanced summary reporting and error context ---
                            console.print(
                                "[bold red]✗ Production setup failed after retry. See details below:[/bold red]"
                            )
                            console.print(f"[red]STDOUT: {result.stdout}[/red]")
                            console.print(f"[red]STDERR: {result.stderr}[/red]")
                            raise click.ClickException(
                                f"Production setup failed after retry: {result.stderr}"
                            )
                        else:
                            console.print(
                                "[yellow]Production setup failed after retry but continuing...[/yellow]"
                            )
                    else:
                        console.print(
                            "[green]✓ Production setup completed successfully on retry[/green]"
                        )
                else:
                    # --- BEGIN: Enhanced summary reporting and error context ---
                    if not ignore_errors:
                        console.print(
                            "[bold red]✗ Production setup failed and nginx config is invalid after retry cleanup. See details below:[/bold red]"
                        )
                        console.print(f"[red]STDOUT: {result.stdout}[/red]")
                        console.print(f"[red]STDERR: {result.stderr}[/red]")
                        raise click.ClickException(
                            "Production setup failed and nginx config is invalid after retry cleanup"
                        )
                    else:
                        console.print(
                            "[yellow]Production setup failed but continuing...[/yellow]"
                        )
            else:
                console.print(
                    "[green]✓ Production setup completed successfully[/green]"
                )
        else:
            console.print(
                f"[yellow][dry-run] Would run: {' '.join(production_cmd)}[/yellow]"
            )

    except Exception as e:
        console.print(f"[bold red]✗ Production setup failed: {e}[/bold red]")
        if not ignore_errors:
            raise click.ClickException(str(e))

    # Final cleanup and validation
    if not dry_run:
        console.print(
            "[blue]Final Nginx configuration cleanup and service restart...[/blue]"
        )
        # Perform comprehensive cleanup one last time
        shell_runner.run(
            ["sudo", "rm", "-f", "/etc/nginx/sites-enabled/frappe-bench"],
            "Removing old default bench Nginx symlink (final)",
            ignore_errors=True,
        )
        shell_runner.run(
            ["sudo", "rm", "-f", "/etc/nginx/sites-available/frappe-bench"],
            "Removing old default bench Nginx config file (final)",
            ignore_errors=True,
        )
        shell_runner.run(
            ["sudo", "rm", "-f", current_bench_nginx_symlink],
            f"Removing old '{os.path.basename(bench_path)}' Nginx symlink (final)",
            ignore_errors=True,
        )
        shell_runner.run(
            ["sudo", "rm", "-f", current_bench_nginx_config],
            f"Removing old '{os.path.basename(bench_path)}' Nginx config file (final)",
            ignore_errors=True,
        )
        clean_all_nginx_configs()

        # --- BEGIN: Automatically update server_name to public IP (search all configs) ---
        import re
        import tempfile
        import urllib.request

        def get_public_ip():
            try:
                with urllib.request.urlopen("https://api.ipify.org") as response:
                    return response.read().decode("utf-8").strip()

            except Exception:
                return None

        public_ip = get_public_ip()
        nginx_sites_available = "/etc/nginx/sites-available"
        updated = False
        if public_ip and os.path.isdir(nginx_sites_available):
            for filename in os.listdir(nginx_sites_available):
                file_path = os.path.join(nginx_sites_available, filename)
                if not os.path.isfile(file_path):
                    continue
                try:
                    with open(file_path, "r") as f:
                        conf = f.read()
                    # Only update if this config has a server_name and mentions the bench name or is the only config
                    if re.search(r"server_name\s+[^;]+;", conf):
                        if (
                            len(os.listdir(nginx_sites_available)) == 1
                            or os.path.basename(bench_path) in conf
                            or "frappe" in conf
                        ):
                            new_conf, count = re.subn(
                                r"server_name\s+[^;]+;",
                                f"server_name {public_ip};",
                                conf,
                            )
                            if count > 0:
                                # Write to a temp file first
                                with tempfile.NamedTemporaryFile(
                                    "w", delete=False
                                ) as tmpf:
                                    tmpf.write(new_conf)
                                    tmp_path = tmpf.name
                                # Move temp file to original with sudo
                                shell_runner.run(
                                    ["sudo", "mv", tmp_path, file_path],
                                    f"Update server_name to {public_ip} in {file_path}",
                                )
                                console.print(
                                    f"[green]✓ Updated server_name to {public_ip} in {file_path}[/green]"
                                )
                                logger.info(
                                    f"[prod] Updated server_name to {public_ip} in {file_path}"
                                )
                                updated = True
                                break
                except Exception as e:
                    console.print(
                        f"[bold red]✗ Failed to update server_name in {file_path}: {e}[/bold red]"
                    )
                    logger.error(
                        f"[prod] Failed to update server_name in {file_path}: {e}"
                    )
            if not updated:
                console.print(
                    f"[yellow]No suitable NGINX config found to update server_name in {nginx_sites_available}[/yellow]"
                )
        elif not public_ip:
            console.print(
                "[yellow]Could not determine public IP. Skipping server_name update.[/yellow]"
            )
        else:
            console.print(
                f"[yellow]NGINX config directory {nginx_sites_available} not found. Skipping server_name update.[/yellow]"
            )
        # --- END: Automatically update server_name to public IP (search all configs) ---

        # Final nginx test
        if validate_nginx_config():
            # Restart services
            shell_runner.run(
                ["sudo", "systemctl", "restart", "supervisor"],
                "Restart supervisor",
                ignore_errors=ignore_errors,
            )

            shell_runner.run(
                ["sudo", "systemctl", "reload", "nginx"],
                "Reload nginx",
                ignore_errors=ignore_errors,
            )

            shell_runner.run(
                ["sudo", "systemctl", "enable", "supervisor", "nginx"],
                "Enable supervisor and nginx on boot",
                ignore_errors=ignore_errors,
            )
        else:
            console.print(
                "[bold red]✗ Final Nginx configuration is still invalid! Manual intervention required.[/bold red]"
            )
            if not ignore_errors:
                raise click.ClickException(
                    "Final Nginx configuration validation failed"
                )

    logger.info(f"[prod] Production environment configured for bench: {bench_name}")
    console.print(
        f"[bold green]✓ Production environment configured for bench: {bench_name}[/bold green]"
    )
