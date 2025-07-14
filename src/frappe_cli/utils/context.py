import os
import json
import click
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console

console = Console()

class FrappeContext:
    """Smart context detection for Frappe CLI, similar to Flask CLI's app context."""
    
    def __init__(self):
        self.bench_path: Optional[str] = None
        self.site_name: Optional[str] = None
        self.config: Dict[str, Any] = {}
        self._detect_context()
    
    def _detect_context(self):
        """Automatically detect Frappe bench and site context."""
        current_dir = Path.cwd()
        
        # Look for bench in current directory or parent directories
        search_path = current_dir
        while search_path != Path("/") and not self.bench_path:
            if (search_path / "sites").exists():
                self.bench_path = str(search_path)
                break
            search_path = search_path.parent
        
        # If we found a bench, try to detect the active site
        if self.bench_path:
            self._detect_active_site()
    
    def _detect_active_site(self):
        """Detect the active site from common indicators."""
        if not self.bench_path:
            return
        bench_path = Path(self.bench_path)
        sites_dir = bench_path / "sites"
        
        # Check for common site detection methods
        # 1. Check if there's only one site
        site_dirs = [d for d in sites_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        if len(site_dirs) == 1:
            self.site_name = site_dirs[0].name
            return
        
        # 2. Check for common site names
        common_names = ["localhost", "127.0.0.1", "site1.local"]
        for name in common_names:
            if (sites_dir / name).exists():
                self.site_name = name
                return
        
        # 3. Check for site_config.json with hostname
        try:
            import socket
            hostname = socket.gethostname()
            if (sites_dir / hostname).exists():
                self.site_name = hostname
                return
        except:
            pass
    
    def get_bench_path(self) -> Optional[str]:
        """Get the detected bench path."""
        return self.bench_path
    
    def get_site_name(self) -> Optional[str]:
        """Get the detected site name."""
        return self.site_name
    
    def require_bench(self) -> str:
        """Require a bench to be detected, raise error if not found."""
        if not self.bench_path:
            console.print("[bold red]Error: No Frappe bench detected[/bold red]")
            console.print("[yellow]Hint:[/yellow] Run this command from a bench directory")
            console.print("[yellow]      or run 'frappe bench init' to create a new bench[/yellow]")
            raise click.ClickException("No bench detected")
        return self.bench_path
    
    def require_site(self) -> str:
        """Require a site to be detected, raise error if not found."""
        if not self.site_name:
            console.print("[bold red]Error: No Frappe site detected[/bold red]")
            console.print("[yellow]Hint:[/yellow] Run 'frappe site create <site-name>' to create a site[/yellow]")
            raise click.ClickException("No site detected")
        return self.site_name
    
    def get_site_config(self) -> Dict[str, Any]:
        """Get the site configuration."""
        if not self.bench_path or not self.site_name:
            return {}
        
        config_path = Path(self.bench_path) / "sites" / self.site_name / "site_config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def print_context_info(self):
        """Print current context information."""
        from rich.table import Table
        
        table = Table(title="Frappe Context", show_header=True, header_style="bold cyan")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Bench Path", self.bench_path or "Not detected")
        table.add_row("Site Name", self.site_name or "Not detected")
        
        if self.bench_path:
            bench_path = Path(self.bench_path)
            sites_count = len([d for d in (bench_path / "sites").iterdir() 
                             if d.is_dir() and not d.name.startswith('.')])
            table.add_row("Sites Count", str(sites_count))
        
        console.print(table)

# Global context instance
frappe_context = FrappeContext()

def get_context() -> FrappeContext:
    """Get the global Frappe context."""
    return frappe_context 