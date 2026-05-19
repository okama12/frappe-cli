import json

from .base import InstallStep


class DnsMultitenantStep(InstallStep):
    """Route requests by hostname so FQDN sites are served correctly.

    Mirrors the manual runbook step `bench config dns_multitenant on`.
    Required before `bench setup production` for sites like
    `test3.rashidiokama.com` to be matched by the nginx server_name.
    """

    name = "dns_multitenant"
    description = "Enable DNS multitenant"

    def check(self, ctx) -> bool:
        config_path = ctx.bench_path / "sites" / "common_site_config.json"
        if not config_path.exists():
            return False
        try:
            with open(config_path) as f:
                config = json.load(f)
        except (OSError, ValueError):
            return False
        return bool(config.get("dns_multitenant"))

    def run(self, ctx) -> None:
        self._run(
            ctx,
            ["bench", "config", "dns_multitenant", "on"],
            cwd=str(ctx.bench_path),
        )
