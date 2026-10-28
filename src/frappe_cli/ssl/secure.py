"""Domain-oriented HTTPS automation for Frappe and ordinary web servers."""

import os
import re
import shutil
import socket
import ssl as tls
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path

import click
from rich.console import Console
from rich.text import Text

from frappe_cli.dev.context import find_bench_root, read_active_site
from frappe_cli.install.steps.base import StepError, privileged_command
from frappe_cli.ui import terminal
from frappe_cli.utils.targets import validated
from frappe_cli.utils.validators import validate_email, validate_site_name

from .setup import _find_bench_for_site, _local_bin_path


class Runner:
    def __init__(self, password=""):
        self.password = password

    def run(self, command, *, check=True, stdin=b"", cwd=None, timeout=180):
        try:
            full_command = privileged_command(self.password, command)
            result = subprocess.run(
                full_command,
                input=stdin,
                capture_output=True,
                cwd=cwd,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired, StepError) as exc:
            raise click.ClickException(f"Could not run {command[0]}: {exc}") from exc
        if check and result.returncode:
            output = result.stderr.decode(errors="replace") or result.stdout.decode(
                errors="replace"
            )
            if self.password:
                output = output.replace(self.password, "[redacted]")
            raise click.ClickException(f"{command[0]} failed:\n{output.strip()}")
        return result


def validate_domain(value):
    domain = validated(value.lower(), validate_site_name)
    if "." not in domain or domain.endswith((".local", ".localhost")):
        raise click.BadParameter("Use a public domain name for Let's Encrypt.")
    return domain


def verify_https(domain):
    """Validate trust, hostname, and validity on the public TLS endpoint."""
    context = tls.create_default_context()
    try:
        with socket.create_connection((domain, 443), timeout=10) as connection:
            with context.wrap_socket(connection, server_hostname=domain) as secure:
                return secure.getpeercert()
    except (OSError, tls.SSLError) as exc:
        raise click.ClickException(
            f"Certificate configuration finished, but HTTPS verification failed for {domain}: {exc}. Check DNS, port 443, and the web-server configuration."
        ) from exc


def certificate_valid(domain, runner):
    cert = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
    if not shutil.which("openssl"):
        return False
    result = runner.run(
        [
            "openssl",
            "x509",
            "-in",
            cert,
            "-noout",
            "-checkend",
            "2592000",
            "-checkhost",
            domain,
        ],
        check=False,
        timeout=15,
    )
    return result.returncode == 0 and b"does match certificate" in result.stdout


def _domain_configured(domain, config):
    return any(
        domain in [name.strip("\"'") for name in names.split()]
        for names in re.findall(r"(?m)^\s*server_name\s+([^;]+);", config)
    )


def _apache_configured(domain, config):
    boundary = r"(?<![\w.-])" + re.escape(domain) + r"(?![\w.-])"
    return any(
        re.search(boundary, line)
        for line in config.splitlines()
        if line.lstrip().startswith(("*:", "port ", "alias ", "default server "))
    )


def _ensure_certbot(runner, method):
    packages = []
    if not shutil.which("openssl"):
        packages.append("openssl")
    if not shutil.which("certbot"):
        packages.append("certbot")
    if method in {"nginx", "apache", "frappe"}:
        plugin = "nginx" if method == "frappe" else method
        result = runner.run(
            ["dpkg-query", "-W", "-f=${Status}", f"python3-certbot-{plugin}"],
            check=False,
        )
        if result.returncode or b"install ok installed" not in result.stdout:
            packages.append(f"python3-certbot-{plugin}")
    if packages:
        if not shutil.which("apt-get"):
            raise click.ClickException(
                "Install Certbot and the selected web-server plugin with your system package manager, then retry."
            )
        runner.run(["apt-get", "install", "-y", *packages], timeout=900)


def _renewal(domain, runner):
    runner.run(["test", "-f", f"/etc/letsencrypt/renewal/{domain}.conf"])
    if shutil.which("systemctl"):
        runner.run(["systemctl", "enable", "--now", "certbot.timer"])
        runner.run(["systemctl", "is-active", "--quiet", "certbot.timer"])
    else:
        raise click.ClickException(
            "Certificate issued. Configure a scheduled 'certbot renew' job on this host; automatic renewal could not be enabled without systemd."
        )


def _proxy(domain, port, runner):
    """Create an owned virtual host without replacing existing configuration."""
    if not shutil.which("nginx"):
        if shutil.which("apachectl"):
            raise click.ClickException(
                "Apache is installed. Configure its virtual host or use --method apache; nginx proxy bootstrapping would conflict with it."
            )
        if not shutil.which("apt-get"):
            raise click.ClickException(
                "Install nginx before using --port on this operating system."
            )
        runner.run(["apt-get", "install", "-y", "nginx"], timeout=900)
    runner.run(["nginx", "-t"])
    path = f"/etc/nginx/conf.d/fp-{sha256(domain.encode()).hexdigest()[:16]}.conf"
    if runner.run(["test", "-e", path], check=False).returncode == 0:
        raise click.ClickException(
            f"A managed proxy file already exists: {path}. Inspect it before changing the application port."
        )
    config = f"""# Managed by fp ssl for {domain}
server {{
    listen 80;
    server_name {domain};
    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf") as temporary:
        temporary.write(config)
        temporary.flush()
        runner.run(["install", "-m", "0644", temporary.name, path])
    try:
        runner.run(["nginx", "-t"])
        runner.run(["systemctl", "reload", "nginx"])
    except click.ClickException:
        runner.run(["rm", "--", path], check=False)
        runner.run(["systemctl", "reload", "nginx"], check=False)
        raise
    return path


def configure_https(
    domain,
    *,
    email="",
    bench=None,
    method="auto",
    webroot=None,
    force=False,
    dry_run=False,
    sudo_password=None,
    console=None,
    port=None,
):
    console = console or Console()
    domain = validate_domain(domain)
    if port is not None and (not isinstance(port, int) or not 1 <= port <= 65535):
        raise click.BadParameter("Application port must be between 1 and 65535.")
    if port is not None and method not in {"auto", "nginx"}:
        raise click.UsageError(
            "--port bootstraps an nginx proxy; use --method auto or nginx."
        )
    if email:
        validated(email, validate_email)
    if bench is not None:
        bench = Path(bench).expanduser().resolve()
        if not (bench / "sites" / domain / "site_config.json").is_file():
            raise click.ClickException(f"No Frappe site {domain} in {bench}.")
    elif method == "auto":
        try:
            bench = _find_bench_for_site(domain)
        except click.ClickException as exc:
            if "Multiple benches" in str(exc):
                raise
            # No Frappe site is a normal case for a general HTTPS command.
            bench = None
    selected = "frappe" if bench is not None and method == "auto" else method
    if port is not None and selected == "frappe":
        raise click.UsageError(
            "This domain belongs to a Frappe site. Its bench manages the upstream port; omit --port."
        )
    if dry_run:
        console.print(Text(f"Preview: configure HTTPS for {domain}"))
        console.print(
            Text(f"Integration: {selected}" + (f" · {bench}" if bench else ""))
        )
        if port is not None:
            console.print(f"Reverse proxy: http://127.0.0.1:{port}", markup=False)
        console.print(
            "Will check DNS, detect the web server, validate configuration, configure a certificate and renewal, then verify HTTPS. No commands ran.",
            style="dim",
        )
        return
    try:
        socket.getaddrinfo(domain, 80, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise click.ClickException(
            f"DNS lookup failed for {domain}. Create or correct its DNS records, then rerun fp ssl {domain}."
        ) from exc
    password = sudo_password
    if password is None:
        password = (
            ""
            if os.geteuid() == 0
            else terminal.ask(console, "Sudo password", password=True)
        )
    runner = Runner(password)
    console.print(Text(f"Domain: {domain}", style="cyan"))
    if not force and port is None and certificate_valid(domain, runner):
        try:
            verify_https(domain)
        except click.ClickException:
            pass
        else:
            if selected != "frappe":
                _renewal(domain, runner)
            console.print(
                "✓ HTTPS is already valid and serving this domain.", style="green"
            )
            return
    proxy_created = False
    if port is not None:
        if shutil.which("nginx"):
            runner.run(["nginx", "-t"])
            config = runner.run(["nginx", "-T"]).stdout.decode(errors="replace")
            if _domain_configured(domain, config):
                raise click.UsageError(
                    "This domain already has an nginx virtual host. --port is for bootstrapping a new proxy; omit it to configure HTTPS on the existing host."
                )
        console.print(
            Text(f"Configuring reverse proxy to 127.0.0.1:{port}", style="cyan")
        )
        _proxy(domain, port, runner)
        selected = "nginx"
        proxy_created = True
    if selected == "auto":
        if shutil.which("nginx"):
            runner.run(["nginx", "-t"])
            config = runner.run(["nginx", "-T"]).stdout.decode(errors="replace")
            if _domain_configured(domain, config):
                selected = "nginx"
        if selected == "auto" and shutil.which("apachectl"):
            config = runner.run(["apachectl", "-S"]).stdout.decode(errors="replace")
            if _apache_configured(domain, config):
                selected = "apache"
        if selected == "auto":
            if not terminal.interactive():
                raise click.ClickException(
                    f"No supported website configuration found for {domain}. Pass --port PORT to configure an nginx proxy, --method webroot --webroot PATH, or --method standalone for a certificate only."
                )
            selected = terminal.choose(
                "No website configuration found. Choose a certificate method",
                [
                    (
                        "proxy",
                        "Configure nginx for an application running on this server",
                    ),
                    ("webroot", "Use an existing website's webroot"),
                    (
                        "standalone",
                        "Obtain a certificate only using temporary HTTP validation",
                    ),
                ],
            )
            if selected == "webroot":
                webroot = terminal.ask(console, "Existing website webroot")
            elif selected == "proxy":
                port = click.IntRange(1, 65535).convert(
                    terminal.ask(console, "Application port", default="8000"),
                    None,
                    None,
                )
                _proxy(domain, port, runner)
                proxy_created = True
                selected = "nginx"
    if selected == "nginx":
        runner.run(["nginx", "-t"])
        config = runner.run(["nginx", "-T"]).stdout.decode(errors="replace")
        if not proxy_created and not _domain_configured(domain, config):
            raise click.ClickException(
                f"No exact nginx server_name for {domain}. Configure its virtual host first."
            )
    elif selected == "apache":
        runner.run(["apachectl", "configtest"])
        config = runner.run(["apachectl", "-S"]).stdout.decode(errors="replace")
        if not _apache_configured(domain, config):
            raise click.ClickException(
                f"No Apache virtual host for {domain}. Configure ServerName/ServerAlias before requesting HTTPS."
            )
    elif selected == "webroot":
        if not webroot or not Path(webroot).expanduser().is_dir():
            raise click.BadParameter(
                "--method webroot requires --webroot pointing to an existing website directory."
            )
    console.print(
        Text(f"Integration: {selected}" + (f" · {bench}" if bench else ""), style="dim")
    )
    _ensure_certbot(runner, selected)
    account = runner.run(["certbot", "show_account"], check=False)
    if not email:
        if account.returncode:
            if not terminal.interactive():
                raise click.UsageError(
                    "Pass --email for initial Let's Encrypt registration."
                )
            email = validated(
                terminal.ask(console, "Certificate email"), validate_email
            )
    if selected == "frappe":
        if email and account.returncode:
            runner.run(
                [
                    "certbot",
                    "register",
                    "--email",
                    email,
                    "--agree-tos",
                    "--no-eff-email",
                    "--non-interactive",
                ]
            )
        executable = shutil.which("bench") or str(
            Path.home() / ".local" / "bin" / "bench"
        )
        runner.run(
            [
                "env",
                f"PATH={_local_bin_path()}",
                executable,
                "setup",
                "lets-encrypt",
                domain,
            ],
            stdin=b"y\ny\n",
            cwd=str(bench),
            timeout=900,
        )
        runner.run(["nginx", "-t"])
        # Bench manages its own renewal cron and generated site configuration.
    else:
        console.print("Requesting the certificate…", style="cyan")
        command = ["certbot"]
        if selected in {"webroot", "standalone"}:
            command.append("certonly")
        command.extend(
            [
                f"--{selected}",
                "-d",
                domain,
                "--cert-name",
                domain,
                "--non-interactive",
                "--agree-tos",
                "--keep-until-expiring",
            ]
        )
        if email:
            command.extend(["--email", email])
        if selected == "webroot":
            command.extend(
                ["--webroot-path", str(Path(webroot).expanduser().resolve())]
            )
        if selected in {"nginx", "apache"}:
            command.append("--redirect")
        if force:
            command.append("--force-renewal")
        runner.run(command, timeout=900)
        _renewal(domain, runner)
    if not certificate_valid(domain, runner):
        raise click.ClickException(
            "The resulting certificate is missing, invalid, or does not cover the domain."
        )
    if selected in {"standalone", "webroot"}:
        console.print(Text(f"✓ Certificate ready: /etc/letsencrypt/live/{domain}/"))
        console.print(
            "Automatic renewal enabled. Install the certificate in your application's TLS configuration to serve HTTPS.",
            style="yellow",
        )
    else:
        verify_https(domain)
        console.print(Text(f"✓ HTTPS verified: https://{domain}", style="green"))


class DomainCommand(click.Command):
    def format_usage(self, ctx, formatter):
        path = ctx.parent.command_path if ctx.parent else ctx.command_path
        formatter.write_usage(path, " ".join(self.collect_usage_pieces(ctx)))


@click.command("secure", cls=DomainCommand, hidden=True)
@click.argument("domain", required=False)
@click.option(
    "--email",
    default="",
    envvar="FP_SSL_EMAIL",
    help="Certificate account email for initial registration.",
)
@click.option(
    "--bench",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Explicit Frappe bench path.",
)
@click.option(
    "--method",
    type=click.Choice(["auto", "nginx", "apache", "webroot", "standalone"]),
    default="auto",
    show_default=True,
)
@click.option(
    "--webroot",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--force", is_flag=True, help="Request certificate renewal even before it is due."
)
@click.option("--dry-run", is_flag=True, help="Preview without changing the server.")
@click.option(
    "--port",
    type=click.IntRange(1, 65535),
    default=None,
    help="Create a new nginx proxy to a local application port.",
)
def secure(domain, email, bench, method, webroot, force, dry_run, port):
    """Configure HTTPS for DOMAIN, with or without a Frappe bench."""
    if domain is None:
        current = find_bench_root(Path.cwd())
        default = read_active_site(current) if current else None
        if not terminal.interactive():
            raise click.UsageError("Pass a domain: fp ssl example.com")
        domain = terminal.ask(Console(), "Domain", default=default)
    configure_https(
        domain,
        email=email,
        bench=bench,
        method=method,
        webroot=webroot,
        force=force,
        dry_run=dry_run,
        port=port,
    )
