import click
from ..utils import shell
import logging
import os
import sys
import platform
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.table import Table
import time
import subprocess
import threading
import queue

LOG_FILE = "/var/log/frappe-installer.log"

def setup_logger():
    logger = logging.getLogger("frappe_installer.install.deps")
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
console = Console()

def validate_sudo():
    """Ensure sudo privileges and cache credentials for subsequent commands."""
    try:
        console.print("[yellow]Validating sudo privileges...[/yellow]")
        subprocess.run(["sudo", "-v"], check=True)
        console.print("[green]✓ Sudo privileges validated[/green]")
    except subprocess.CalledProcessError:
        console.print("[bold red]Error: Failed to get sudo privileges.[/bold red]")
        console.print("[red]Please run: sudo -v[/red]")
        sys.exit(1)

def print_system_info():
    """Print system information for logging and debugging."""
    info_table = Table(title="System Information", show_header=True, header_style="bold cyan")
    info_table.add_column("Property", style="cyan")
    info_table.add_column("Value", style="white")
    
    # Get system info
    info_table.add_row("OS", platform.system())
    info_table.add_row("OS Release", platform.release())
    info_table.add_row("OS Version", platform.version())
    info_table.add_row("Machine", platform.machine())
    info_table.add_row("Python Version", platform.python_version())
    info_table.add_row("Architecture", platform.architecture()[0])
    
    # Get distribution info on Linux
    if platform.system() == "Linux":
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        distro = line.split("=")[1].strip().strip('"')
                        info_table.add_row("Distribution", distro)
                        break
        except FileNotFoundError:
            info_table.add_row("Distribution", "Unknown")
    
    console.print(info_table)
    console.print()

def stream_output(process, output_queue, stream_type):
    """Stream output from subprocess to queue."""
    stream = process.stdout if stream_type == 'stdout' else process.stderr
    for line in iter(stream.readline, b''):
        output_queue.put((stream_type, line.decode('utf-8').rstrip()))
    stream.close()

class RichShell:
    """Enhanced shell runner with rich progress output and proper error handling"""
    
    def __init__(self, console, progress_instance=None, dry_run=False, debug=False):
        self.console = console
        self.progress = progress_instance
        self.completed_tasks = []
        self.dry_run = dry_run
        self.debug = debug
    
    def run_with_progress(self, cmd, description, simulate_progress=True, interactive=False, ignore_errors=False):
        """Run command with rich progress bar and proper error handling"""
        
        if self.debug:
            self.console.print(f"[dim]DEBUG: Command: {' '.join(cmd)}[/dim]")
        
        if self.dry_run:
            self.console.print(f"[yellow]DRY RUN:[/yellow] Would run: {' '.join(cmd)}")
            if self.progress:
                task = self.progress.add_task(description, total=100)
                self.progress.update(task, completed=100, description=f"[blue]DRY RUN: {description}[/blue]")
                self.completed_tasks.append(f"  [blue]DRY RUN: {description}[/blue]")
            return None
        
        logger.info(f"[deps] Running command: {' '.join(cmd)}")
        
        # If we have a progress instance, use it; otherwise create a temporary one
        if self.progress:
            task = self.progress.add_task(description, total=100)
            
            try:
                if interactive:
                    # For interactive commands, temporarily stop the progress display
                    self.progress.stop()
                    self.console.print(f"[yellow]Running interactive command:[/yellow] {description}")
                    if self.debug:
                        self.console.print(f"[dim]Command: {' '.join(cmd)}[/dim]")
                    
                    # Run the command interactively
                    result = subprocess.run(cmd, check=True)
                    
                    # Restart the progress display
                    self.progress.start()
                    self.progress.update(task, completed=100, description=f"[green]✓ {description} - Complete")
                    self.completed_tasks.append(f"  [green]✓ {description} - Complete[/green]")
                    return result
                    
                elif simulate_progress and any(x in cmd for x in ["apt", "install", "update", "upgrade"]):
                    # Start the actual process with streaming output
                    process = subprocess.Popen(
                        cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        universal_newlines=False
                    )
                    
                    # Create output queue and threads for streaming
                    output_queue = queue.Queue()
                    stdout_thread = threading.Thread(target=stream_output, args=(process, output_queue, 'stdout'))
                    stderr_thread = threading.Thread(target=stream_output, args=(process, output_queue, 'stderr'))
                    
                    stdout_thread.start()
                    stderr_thread.start()
                    
                    # Simulate progress while process runs
                    progress_counter = 0
                    while process.poll() is None:
                        # Update progress
                        progress_counter = min(progress_counter + 5, 90)
                        self.progress.update(task, completed=progress_counter)
                        
                        # Process any output
                        try:
                            while True:
                                stream_type, line = output_queue.get_nowait()
                                if self.debug:
                                    color = "blue" if stream_type == 'stdout' else "red"
                                    self.console.print(f"[{color}]{stream_type}: {line}[/{color}]")
                                logger.info(f"[deps] {stream_type}: {line}")
                        except queue.Empty:
                            pass
                        
                        time.sleep(0.3)
                    
                    # Wait for threads to complete
                    stdout_thread.join()
                    stderr_thread.join()
                    
                    # Process remaining output
                    try:
                        while True:
                            stream_type, line = output_queue.get_nowait()
                            if self.debug:
                                color = "blue" if stream_type == 'stdout' else "red"
                                self.console.print(f"[{color}]{stream_type}: {line}[/{color}]")
                            logger.info(f"[deps] {stream_type}: {line}")
                    except queue.Empty:
                        pass
                    
                    if process.returncode != 0:
                        self.progress.update(task, completed=100, description=f"[red]✗ {description} - Failed")
                        self.completed_tasks.append(f"  [red]✗ {description} - Failed[/red]")
                        error_msg = f"Command failed with return code {process.returncode}: {' '.join(cmd)}"
                        logger.error(f"[deps] {error_msg}")
                        
                        if not ignore_errors:
                            self.console.print(f"[red]Error: {error_msg}[/red]")
                            raise subprocess.CalledProcessError(process.returncode, cmd)
                        else:
                            self.console.print(f"[yellow]Warning: {error_msg} (ignored)[/yellow]")
                    else:
                        self.progress.update(task, completed=100, description=f"[green]✓ {description} - Complete")
                        self.completed_tasks.append(f"  [green]✓ {description} - Complete[/green]")
                else:
                    # For other commands, run with proper error handling
                    try:
                        if hasattr(shell, 'run'):
                            result = shell.run(cmd)
                        else:
                            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                            if self.debug and result.stdout:
                                self.console.print(f"[blue]stdout: {result.stdout}[/blue]")
                            if self.debug and result.stderr:
                                self.console.print(f"[red]stderr: {result.stderr}[/red]")
                        
                        self.progress.update(task, completed=100, description=f"[green]✓ {description} - Complete")
                        self.completed_tasks.append(f"  [green]✓ {description} - Complete[/green]")
                        return result
                        
                    except (subprocess.CalledProcessError, Exception) as e:
                        self.progress.update(task, completed=100, description=f"[red]✗ {description} - Failed")
                        self.completed_tasks.append(f"  [red]✗ {description} - Failed[/red]")
                        logger.error(f"[deps] Command failed: {' '.join(cmd)} - {str(e)}")
                        
                        if not ignore_errors:
                            raise e
                        else:
                            self.console.print(f"[yellow]Warning: Command failed but ignored: {str(e)}[/yellow]")
                    
            except Exception as e:
                if interactive:
                    # Make sure to restart progress display even on error
                    self.progress.start()
                self.progress.update(task, completed=100, description=f"[red]✗ {description} - Failed")
                self.completed_tasks.append(f"  [red]✗ {description} - Failed[/red]")
                logger.error(f"[deps] Unexpected error: {str(e)}")
                
                if not ignore_errors:
                    raise e
                else:
                    self.console.print(f"[yellow]Warning: Unexpected error ignored: {str(e)}[/yellow]")
        else:
            # Fallback to simple console output
            self.console.print(f"[blue]Running:[/blue] {description}")
            try:
                if interactive:
                    result = subprocess.run(cmd, check=True)
                else:
                    if hasattr(shell, 'run'):
                        result = shell.run(cmd)
                    else:
                        result = subprocess.run(cmd, check=True)
                
                self.console.print(f"[green]✓ {description} - Complete[/green]")
                self.completed_tasks.append(f"  [green]✓ {description} - Complete[/green]")
                return result
                
            except Exception as e:
                self.console.print(f"[red]✗ {description} - Failed: {str(e)}[/red]")
                self.completed_tasks.append(f"  [red]✗ {description} - Failed[/red]")
                logger.error(f"[deps] Command failed: {' '.join(cmd)} - {str(e)}")
                
                if not ignore_errors:
                    raise e
                else:
                    self.console.print(f"[yellow]Warning: Command failed but ignored: {str(e)}[/yellow]")

def create_dependency_table(selected_deps):
    """Create a table showing selected dependencies"""
    table = Table(title="Selected Dependencies", show_header=True, header_style="bold magenta")
    table.add_column("Dependency", style="cyan")
    table.add_column("Description", style="white")
    
    dep_descriptions = {
        'python': 'Python development environment',
        'mariadb': 'MariaDB database server',
        'redis': 'Redis in-memory data store',
        'pdf': 'PDF generation tools',
        'node': 'Node.js runtime via NVM',
        'tools': 'Development build tools',
        'bench-deps': 'Bench framework dependencies',
        'mail': 'Mail utilities'
    }
    
    for dep in selected_deps:
        desc = dep_descriptions.get(dep, 'Unknown dependency')
        table.add_row(dep, desc)
    
    return table

@click.command()
@click.option('--dry-run', is_flag=True, help='Simulate commands without executing them')
@click.option('--debug', is_flag=True, help='Enable debug output with command details')
@click.option('--ignore-errors', is_flag=True, help='Continue installation even if some commands fail')
@click.pass_context
def deps(ctx, dry_run, debug, ignore_errors):
    """Install system dependencies for Frappe/ERPNext."""
    config = ctx.obj.get('CONFIG', {})
    default_deps = 'python,mariadb,redis,pdf,node,tools,bench-deps,mail'
    deps_val = config.get('system', {}).get('deps', default_deps)
    
    # Print system information
    if debug:
        print_system_info()
    
    # Create rich console output
    console.print(Panel.fit(
        "[bold blue]Frappe/ERPNext Dependencies Installer[/bold blue]",
        border_style="blue"
    ))
    
    if dry_run:
        console.print("[yellow]🔍 DRY RUN MODE - No commands will be executed[/yellow]")
    
    if debug:
        console.print("[yellow]🐛 DEBUG MODE - Verbose output enabled[/yellow]")
    
    if ignore_errors:
        console.print("[yellow]⚠️  IGNORE ERRORS MODE - Will continue on failures[/yellow]")
    
    # Validate sudo privileges (skip in dry run)
    if not dry_run:
        validate_sudo()
    
    deps = click.prompt('Select dependencies (comma-separated)', default=deps_val, show_default=True)
    logger.info(f"[deps] Installing dependencies: {deps}")
    selected = [d.strip() for d in deps.split(',') if d.strip()]
    
    # Show selected dependencies table
    console.print(create_dependency_table(selected))
    console.print()
    
    # Keep track of all completed tasks
    all_completed_tasks = []
    
    # Install each dependency (no progress bar)
    total_deps = len(selected)
    
    # Create rich shell runner (no progress instance)
    rich_shell = RichShell(console, progress_instance=None, dry_run=dry_run, debug=debug)
    
    try:
        for i, dep in enumerate(selected):
            console.print(f"\n[bold yellow]Installing {dep}...[/bold yellow]")
            try:
                if dep == 'python':
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "update"],
                        "Updating package lists",
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "install", "-y", "python3-dev", "python3-venv", "python3-pip", "python3-setuptools", "python3-wheel", "pipx"],
                        "Installing Python dependencies",
                        interactive=True,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["pipx", "ensurepath"],
                        "Setting up pipx path",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                elif dep == 'mariadb':
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "install", "-y", "mariadb-server", "mariadb-client"],
                        "Installing MariaDB server and client",
                        interactive=True,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "systemctl", "enable", "mariadb"],
                        "Enabling MariaDB service",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "systemctl", "start", "mariadb"],
                        "Starting MariaDB service",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                elif dep == 'redis':
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "install", "-y", "redis-server"],
                        "Installing Redis server",
                        interactive=True,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "systemctl", "enable", "redis-server"],
                        "Enabling Redis service",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "systemctl", "start", "redis-server"],
                        "Starting Redis service",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                elif dep == 'pdf':
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "install", "-y", "xvfb", "libfontconfig1", "wkhtmltopdf", "fonts-dejavu-core"],
                        "Installing PDF generation tools",
                        interactive=True,
                        ignore_errors=ignore_errors
                    )
                elif dep == 'node':
                    nvm_dir = os.path.expanduser("~/.nvm")
                    if not os.path.isdir(nvm_dir):
                        rich_shell.run_with_progress(
                            ["bash", "-c", "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash"],
                            "Downloading and installing NVM",
                            simulate_progress=False,
                            ignore_errors=ignore_errors
                        )
                        rich_shell.run_with_progress(
                            ["bash", "-c", f"source ~/.bashrc || source ~/.profile || true"],
                            "Sourcing shell profile",
                            simulate_progress=False,
                            ignore_errors=True
                        )
                    rich_shell.run_with_progress(
                        ["bash", "-c", f"source {nvm_dir}/nvm.sh && nvm install 18 && nvm use 18 && nvm alias default 18"],
                        "Installing Node.js 18 via NVM",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["bash", "-c", f"source {nvm_dir}/nvm.sh && node -v && npm -v"],
                        "Verifying Node.js installation",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                elif dep == 'tools':
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "install", "-y", "build-essential", "libssl-dev", "libffi-dev", "python3-dev", "libjpeg-dev", "zlib1g-dev"],
                        "Installing development tools",
                        interactive=True,
                        ignore_errors=ignore_errors
                    )
                elif dep == 'bench-deps':
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "install", "-y", "supervisor", "nginx", "ufw"],
                        "Installing Bench system dependencies",
                        interactive=True,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["bash", "-c", "curl -fsSL https://dl.yarnpkg.com/debian/pubkey.gpg | sudo gpg --dearmor --batch --yes -o /usr/share/keyrings/yarnkey.gpg"],
                        "Adding Yarn repository key",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["bash", "-c", 'echo "deb [signed-by=/usr/share/keyrings/yarnkey.gpg] https://dl.yarnpkg.com/debian/ stable main" | sudo tee /etc/apt/sources.list.d/yarn.list > /dev/null'],
                        "Adding Yarn repository",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "update"],
                        "Updating package lists for Yarn",
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "install", "-y", "yarn", "pipx"],
                        "Installing Yarn and pipx",
                        interactive=True,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["pipx", "ensurepath"],
                        "Setting up pipx path",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "systemctl", "enable", "supervisor"],
                        "Enabling supervisor service",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "systemctl", "enable", "nginx"],
                        "Enabling nginx service",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "systemctl", "start", "supervisor"],
                        "Starting supervisor service",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                    rich_shell.run_with_progress(
                        ["sudo", "systemctl", "start", "nginx"],
                        "Starting nginx service",
                        simulate_progress=False,
                        ignore_errors=ignore_errors
                    )
                elif dep == 'mail':
                    rich_shell.run_with_progress(
                        ["sudo", "apt", "install", "-y", "mailutils"],
                        "Installing mail utilities",
                        interactive=True,
                        ignore_errors=ignore_errors
                    )
                # Add all completed tasks from this dependency to the overall list
                all_completed_tasks.extend(rich_shell.completed_tasks)
                rich_shell.completed_tasks = []  # Clear for next dependency
                
                # Print completion message with all completed tasks visible
                console.print(f"[green]✓ {dep} installed successfully[/green]")
                
            except Exception as e:
                console.print(f"[red]✗ Failed to install {dep}: {str(e)}[/red]")
                logger.error(f"[deps] Failed to install {dep}: {str(e)}")
                if not ignore_errors:
                    console.print(f"[red]Installation stopped due to error. Use --ignore-errors to continue on failures.[/red]")
                    break
                else:
                    console.print(f"[yellow]Continuing with next dependency...[/yellow]")
                    continue
                
    finally:
        pass  # No progress to stop
    
    # Final success message
    console.print()
    if dry_run:
        console.print(Panel.fit(
            "[bold blue]🔍 Dry run completed successfully![/bold blue]",
            border_style="blue"
        ))
    else:
        console.print(Panel.fit(
            "[bold green]🎉 All dependencies installed successfully![/bold green]",
            border_style="green"
        ))
    
    logger.info("[deps] Dependencies installation process completed.")