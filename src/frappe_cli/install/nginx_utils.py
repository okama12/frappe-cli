"""
nginx_utils.py: Utilities for NGINX config management, deduplication, backup, and validation.
"""
import os
import shutil
import subprocess
from typing import List, Dict, Set, Tuple
from rich.console import Console

console = Console()

def backup_nginx_configs(backup_dir: str) -> List[str]:
    """
    Atomically backup all NGINX config files in sites-enabled and sites-available to backup_dir.
    Returns a list of backed up file paths.
    """
    nginx_dirs = ["/etc/nginx/sites-enabled", "/etc/nginx/sites-available"]
    backed_up = []
    os.makedirs(backup_dir, exist_ok=True)
    for d in nginx_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                src = os.path.join(d, f)
                if os.path.isfile(src) or os.path.islink(src):
                    dst = os.path.join(backup_dir, f"{f}__{d.replace('/', '_')}")
                    shutil.copy2(src, dst)
                    backed_up.append(dst)
    return backed_up

def restore_nginx_configs(backup_dir: str):
    """
    Restore all NGINX config files from backup_dir to their original locations.
    """
    for f in os.listdir(backup_dir):
        if "__" in f:
            orig_name, orig_dir = f.split("__", 1)
            orig_dir = orig_dir.replace("_", "/")
            dst = os.path.join(orig_dir, orig_name)
            src = os.path.join(backup_dir, f)
            shutil.copy2(src, dst)

def clean_nginx_upstreams_crossfile(console: Console) -> Dict[str, List[str]]:
    """
    Detects and warns if the same upstream appears in multiple files (cross-file deduplication).
    Returns a dict mapping upstream name to list of files where it appears.
    """
    nginx_dirs = ["/etc/nginx/sites-enabled", "/etc/nginx/sites-available"]
    upstream_map: Dict[str, List[str]] = {}
    for d in nginx_dirs:
        if os.path.isdir(d):
            for f in os.listdir(d):
                path = os.path.join(d, f)
                if os.path.isfile(path) or os.path.islink(path):
                    try:
                        with open(path, 'r') as fh:
                            for line in fh:
                                if line.strip().startswith("upstream ") and "{" in line:
                                    parts = line.strip().split()
                                    if len(parts) >= 2:
                                        name = parts[1].rstrip('{').strip()
                                        upstream_map.setdefault(name, []).append(path)
                    except Exception:
                        continue
    # Warn if any upstream appears in more than one file
    for name, files in upstream_map.items():
        if len(files) > 1:
            console.print(f"[yellow]Warning: Upstream '{name}' appears in multiple files: {files}[/yellow]")
    return {k: v for k, v in upstream_map.items() if len(v) > 1}

def validate_nginx_config() -> bool:
    """
    Validates the overall NGINX configuration using 'nginx -t'.
    """
    try:
        result = subprocess.run(["sudo", "nginx", "-t"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[green]✓ Nginx configuration is valid[/green]")
            return True
        else:
            console.print(f"[bold red]✗ Nginx configuration test failed:[/bold red]")
            console.print(f"[red]{result.stdout}[/red]")
            console.print(f"[red]{result.stderr}[/red]")
            return False
    except Exception as e:
        console.print(f"[bold red]✗ Failed to test nginx config: {e}[/bold red]")
        return False
