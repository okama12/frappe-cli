"""Resolve selected components into the wizard's canonical execution order."""

import click

from .steps import ALL_STEPS

# OS upgrades and passwordless sudo are optional, never implicit prerequisites.
DEPENDENCIES = {
    "uv_check": {"system_deps"},
    "nodejs": {"system_deps"},
    "mariadb_install": {"system_deps"},
    "mariadb_secure": {"mariadb_install"},
    "redis": {"system_deps"},
    "wkhtmltopdf": {"system_deps"},
    "bench_install": {"uv_check"},
    "bench_init": {"bench_install", "nodejs", "redis", "wkhtmltopdf"},
    "site_create": {"bench_init", "mariadb_secure"},
    "app_get": {"bench_init"},
    "dns_multitenant": {"bench_init"},
    "production_setup": {"dns_multitenant"},
    "sudoers_setup": {"production_setup"},
    "app_install": {"site_create", "app_get", "production_setup"},
    "bench_restart": {"production_setup"},
    "ssl_setup": {"site_create", "production_setup"},
}


def resolve_steps(selected: list[str]) -> list[str]:
    known = {step.name for step in ALL_STEPS}
    unknown = set(selected) - known
    if unknown:
        raise click.BadParameter("Unknown components: " + ", ".join(sorted(unknown)))
    required = set(selected)
    pending = list(selected)
    while pending:
        for dependency in DEPENDENCIES.get(pending.pop(), set()):
            if dependency not in required:
                required.add(dependency)
                pending.append(dependency)
    return [step.name for step in ALL_STEPS if step.name in required]
