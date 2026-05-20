# frappe-cli

[![PyPI version](https://img.shields.io/pypi/v/frappe-cli.svg)](https://pypi.org/project/frappe-cli/)
[![Python](https://img.shields.io/pypi/pyversions/frappe-cli.svg)](https://pypi.org/project/frappe-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-163%20passing-brightgreen.svg)](#development)

```
  ███████╗ ██████╗
  ██╔════╝██╔════╝
  █████╗  ██║
  ██╔══╝  ██║
  ██║     ╚██████╗
  ╚═╝      ╚═════╝  frappe-cli  ·  fc
```

**A production-ready CLI that installs and operates [Frappe](https://frappeframework.com/) / [ERPNext](https://erpnext.com/) — from a bare VPS to a working HTTPS site in one command. Also your daily `bench` shortcut.**

Built with Python + [Click](https://click.palletsprojects.com/) + [Rich](https://rich.readthedocs.io/). Every step is independently runnable, self-healing, and idempotent — safe to re-run on partially-installed servers.

---

## Two tools in one

```
┌─────────────────────────────────────────────────────────────────────┐
│                          fc  (frappe-cli)                           │
├──────────────────────────────┬──────────────────────────────────────┤
│   🏗  INSTALLER / OPS        │   ⚡  DAILY DEV WORKFLOW             │
│                              │                                      │
│  fc install wizard           │  fc use <site>     ← set context     │
│  fc step <name>              │  fc migrate        ← auto --site     │
│  fc ssl setup/list           │  fc console                          │
│  fc service status           │  fc restart                          │
│  fc backup setup             │  fc build / watch                    │
│  fc firewall setup           │  fc get-app <url>                    │
│                              │  fc sites / fc context               │
└──────────────────────────────┴──────────────────────────────────────┘
```

---

## Highlights

- **One-command bootstrap:** `fc install wizard` provisions a fresh Ubuntu VPS end-to-end (MariaDB → Redis → Node → bench → site → ERPNext → nginx → supervisor → SSL).
- **17 individually runnable steps:** `fc step <name>` lets you re-run, debug, or compose any wizard step on its own (same code path as the wizard).
- **Context-aware dev workflow:** `fc use mysite.local` remembers your active bench + site — then every `bench` command becomes one word.
- **Multi-bench friendly:** works on fresh and non-fresh VPS — auto-detects existing bench installs and directories.
- **Self-healing:** automatically repairs the supervisor symlink that vanilla `bench setup production` sometimes misses on multi-bench hosts.
- **Hard verification:** polls `supervisorctl status` for RUNNING and pings bench Redis for PONG before declaring success.
- **Resumable:** the wizard saves progress; if a step fails you can fix and `fc install wizard --resume`.
- **Operator-friendly utilities:** `fc ssl list/setup`, `fc service status`, `fc backup setup`, `fc firewall setup`, and more.

---

## Installation

`frappe-cli` is published on PyPI: <https://pypi.org/project/frappe-cli/>.

### With [uv](https://docs.astral.sh/uv/) (recommended)

```bash
# Install uv (if you don't have it yet)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install frappe-cli globally
uv tool install frappe-cli

# Verify
fc --version
fc --help
```

To upgrade later:

```bash
uv tool upgrade frappe-cli
```

### With pip

```bash
pip install --user frappe-cli
export PATH="$HOME/.local/bin:$PATH"
fc --help
```

### With pipx

```bash
pipx install frappe-cli
fc --help
```

### Requirements

| Requirement | Version |
|---|---|
| Python | ≥ 3.10 |
| OS | Ubuntu 22.04 or 24.04 (other Debian variants work, others untested) |
| User | A non-root user with `sudo` access |

> **Note:** `frappe-cli` will install Node.js, MariaDB, Redis, nginx, supervisor, wkhtmltopdf, certbot, and `uv` for you. You do not need to pre-install them.

---

## Quick start: bootstrap a fresh VPS

The fastest path from a clean Ubuntu server to a working HTTPS Frappe site:

```
Fresh Ubuntu VPS
      │
      ▼
  apt install python3-pip curl
      │
      ▼
  uv tool install frappe-cli
      │
      ▼
  fc install wizard          ← interactive prompts, ~30-60 min
      │
      ├─ system-update
      ├─ system-deps
      ├─ nodejs
      ├─ mariadb-install + mariadb-secure
      ├─ redis
      ├─ wkhtmltopdf
      ├─ bench-install + bench-init
      ├─ site-create
      ├─ get-app + install-app
      ├─ production (nginx + supervisor)
      └─ ssl (Let's Encrypt)
            │
            ▼
  ✓ https://erp.example.com  ← live in one command
```

```bash
sudo apt update && sudo apt install -y python3-pip curl

# 1. Install frappe-cli
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install frappe-cli

# 2. Run the interactive wizard (≈30–60 min depending on the host)
fc install wizard
```

You'll be prompted for:

| Prompt | Example |
|---|---|
| Bench directory | `my-bench` |
| Site (FQDN, must resolve to this host) | `erp.example.com` |
| Frappe branch | `version-15` |
| App to install | `erpnext` |
| App branch | `version-15` |
| MariaDB root password | (new password) |
| Site Administrator password | (new password) |
| Let's Encrypt email | `you@example.com` |
| Sudo password | (your user password) |

If a step fails, fix the issue and resume from where it stopped:

```bash
fc install wizard --resume
```

When it's done:

```bash
curl -I https://erp.example.com   # HTTP/2 200, served by nginx, valid Let's Encrypt cert
```

---

## ⚡ Daily dev workflow

This is where `fc` really shines. Instead of typing `bench --site <long.site.name> migrate` every time, you set your context once and then use short commands.

```
  ~/my-bench/                    ← bench root
  ├── apps/
  │   ├── frappe/
  │   └── my_custom_app/         ← you are here, deep in code
  ├── sites/
  │   ├── dev.local/
  │   └── staging.example.com/
  └── .fp.yaml                   ← fc writes: site: dev.local
```

### Step 1 — set your active site (once per session)

Works from any directory inside the bench — bench root, `apps/`, `apps/my_app/`, etc.

```bash
cd ~/my-bench
fc use dev.local
# ✓ Active site set to dev.local  (bench: my-bench)
```

### Step 2 — run bench commands without the boilerplate

```bash
# Before fc:
bench --site dev.local migrate
bench --site dev.local console
bench --site dev.local clear-cache

# With fc:
fc migrate
fc console
fc clear-cache
```

### Switching between sites

You never "lose" a site — just `use` a different one. The old site is still there.

```
fc sites
  ● dev.local          ← active (green dot)
    staging.example.com

fc use staging.example.com
# ✓ Active site set to staging.example.com

fc migrate            → bench --site staging.example.com migrate
```

### All dev commands

```
  fc use <site>         Write active site to .fp.yaml
  fc context            Show current bench + active site
  fc sites              List all sites (active site marked with ●)

  ── site-scoped (auto-injects --site) ─────────────────────────────
  fc migrate            Sync schema, run patches, rebuild assets
  fc console            IPython console for the active site
  fc install-app <app>  Install app on active site
  fc uninstall-app <a>  Remove app from active site
  fc list-apps          Apps installed on active site
  fc clear-cache        Clear framework cache
  fc mariadb            MariaDB shell for active site

  ── bench-scoped (no --site needed) ───────────────────────────────
  fc restart            Restart supervisor / systemd processes
  fc build              Build JS + CSS assets
  fc start              Start dev server (Procfile)
  fc watch              Watch + recompile JS/CSS on change
  fc get-app <url>      Download app from git URL
```

> **How it works:** `fc` detects the bench root by walking up from your current directory looking for both a `sites/` and `apps/` folder. The active site is stored in `<bench_root>/.fp.yaml` — a plain YAML file you can inspect or edit directly. The wizard's state (`~/.frappe-cli-state.json`) is completely separate and untouched.

---

## Command structure

```
fc <group> <command> [options]
```

| Group | What it does |
|---|---|
| `install wizard` | End-to-end automated installer with state + resume |
| **`step`** | **Run any individual wizard step on its own** |
| `ssl` | Issue / list Let's Encrypt certificates for existing sites |
| `site` | Create, list, backup, restore sites |
| `app` | Get / install / update / remove Frappe apps |
| `service` | Restart, status, logs for bench + system services |
| `backup` | Manual + scheduled backups (optionally to an external HD) |
| `firewall` | UFW configuration with secure defaults |
| `maintenance` | Log rotation, etc. |
| `monitor` | Live logs and system health |
| `optimize` | Performance tuning |
| `rollback` | Restore from backup, uninstall site, etc. |
| `config` | YAML config get/set/validate |
| **`use`** | **Set active bench + site context** |
| **`context`** | **Show current bench + active site** |
| **`sites`** | **List sites in the current bench** |

Every command supports `--help` and many support `--dry-run` and `--debug`.

---

## Everyday recipes

### Add SSL to an existing site

```bash
# See all sites and which are still on HTTP
fc ssl list

# Issue an HTTPS cert for one site (auto-detects the owning bench)
fc ssl setup --site-name erp.example.com

# First time ever using Let's Encrypt on this host? Provide an email
fc ssl setup --site-name new.example.com --email you@example.com
```

### Re-run a single wizard step

Every step the wizard runs is also exposed as a standalone command. Same code, same self-healing, same verification.

```bash
# Show all steps in execution order
fc step list

# Run just SSL for one site
fc step ssl --bench-name my-bench --site-name erp.example.com

# Re-do the production setup (nginx + supervisor) for a bench
fc step production --bench-name my-bench

# Try a step without executing anything
fc step production --bench-name my-bench --dry-run

# Force a step even when check() says "already done"
fc step ssl --bench-name my-bench --site-name erp.example.com --force
```

The full step catalogue:

| # | Command | Purpose |
|---|---|---|
| 1 | `fc step system-update` | `apt-get update && upgrade` |
| 2 | `fc step system-deps` | Frappe's required apt packages |
| 3 | `fc step uv-check` | Ensure `uv` is installed |
| 4 | `fc step nodejs` | Install Node.js + Yarn |
| 5 | `fc step mariadb-install` | Install MariaDB + utf8mb4 config |
| 6 | `fc step mariadb-secure` | Secure MariaDB root user |
| 7 | `fc step redis` | Install Redis server |
| 8 | `fc step wkhtmltopdf` | Install wkhtmltopdf + X11 fonts |
| 9 | `fc step bench-install` | `uv tool install frappe-bench` |
| 10 | `fc step bench-init` | `bench init <name> --frappe-branch ...` |
| 11 | `fc step site-create` | `bench new-site <site>` |
| 12 | `fc step app-get` | `bench get-app <url>` |
| 13 | `fc step dns-multitenant` | `bench config dns_multitenant on` |
| 14 | `fc step production` | `bench setup production` + supervisor self-heal + verify |
| 15 | `fc step app-install` | `bench --site <s> install-app <app>` |
| 16 | `fc step bench-restart` | `supervisorctl reread/update` + nginx reload |
| 17 | `fc step ssl` | `bench setup lets-encrypt <site>` |

### Add another site to an existing bench

```bash
fc step site-create     --bench-name my-bench --site-name shop.example.com
fc step dns-multitenant --bench-name my-bench
fc step app-install     --bench-name my-bench --site-name shop.example.com --app-url erpnext
fc step bench-restart   --bench-name my-bench
fc step ssl             --bench-name my-bench --site-name shop.example.com
```

### Set up an automated backup

```bash
fc backup setup \
  --bench-name my-bench \
  --site-name erp.example.com \
  --admin-email you@example.com
```

### Service health check

```bash
fc service status --bench-name my-bench --site-name erp.example.com
fc service restart
```

### Firewall (UFW)

```bash
fc firewall setup        # opens 22, 80, 443 by default
```

---

## Tips for non-fresh VPS

`frappe-cli` is designed to work on hosts that already have bench installed or already have other Frappe benches:

- `fc step bench-install` — checks if `bench` is on `PATH` (any of `~/.local/bin`, `/usr/local/bin`, `/usr/bin`) and skips if found.
- `fc step bench-init` — skips if the target bench directory already has `apps/frappe/`.
- `fc step production` — explicitly creates the missing `supervisor.conf` symlink that vanilla `bench setup production` sometimes forgets on multi-bench hosts.
- `fc step ssl` — uses `sudo test -f` so it can correctly detect existing certs in the root-owned `/etc/letsencrypt/live/` directory.

---

## Why `frappe-cli` over raw `bench`?

| Pain point | `bench` alone | `frappe-cli` |
|---|---|---|
| Fresh VPS bootstrap | 8+ manual steps, lots of doc-hopping | `fc install wizard` |
| Daily `migrate` / `console` | `bench --site long.site.name migrate` | `fc migrate` |
| Multi-bench supervisor symlink | Sometimes silently missing → errors | Auto-created and verified |
| Redis health check before `install-app` | None | TCP `PING`/`PONG` on queue/cache/socketio ports |
| `bench setup lets-encrypt` prompts | Two interactive `[y/N]` prompts | Automated |
| State across reboots / partial failures | Manual | `--resume` from saved state |
| Re-running a single step | Find the command, get the args right | `fc step <name>` |
| Listing sites without SSL | grep + sudo find | `fc ssl list` |

---

## Configuration file (optional)

For reproducible installs, pass a YAML config with `--config`:

```yaml
# production.yaml
system:
  timezone: "Africa/Nairobi"
  locale: "en_US.UTF-8"
  user: "frappe"
frappe:
  branch: "version-15"
  bench_name: "my-bench"
  site_name: "erp.example.com"
  admin_password: "changeme"
  mariadb_root_password: "changeme"
services:
  enable_ssl: true
  enable_ufw: true
backup:
  admin_email: "you@example.com"
  retention_days: 7
```

See [`src/frappe_cli/data/example_config.yaml`](src/frappe_cli/data/example_config.yaml).

---

## Logs and troubleshooting

- All commands log to `/var/log/frappe-installer.log` (with local fallback if not writable).
- Use `--debug` on any command for verbose subprocess output.
- Use `--dry-run` on `step` / `install` commands to preview what would run.
- For a known-working manual flow you can compare against, see [`docs/superpowers/test3-bench-setup.md`](docs/superpowers/test3-bench-setup.md) — a step-by-step runbook used to verify every wizard step.

---

## Development

```bash
git clone https://github.com/okama12/frappe-cli.git
cd frappe-cli

# Install dependencies
poetry install

# Run all tests (163 passing)
PYTHONPATH=src poetry run pytest tests/

# Lint (ruff + black --check + isort --check + mypy)
poetry run bash scripts/lint.sh

# Install locally and try it
poetry run fc --help
```

### Project layout

```
src/frappe_cli/
├── cli.py                  # root Click group — registers all commands
├── dev/
│   ├── context.py          # bench detection + .fp.yaml read/write
│   └── commands.py         # use, context, sites + passthrough commands
├── install/
│   ├── wizard.py           # fc install wizard
│   ├── context.py          # InstallContext dataclass
│   ├── state.py            # ~/.frappe-cli-state.json (resume support)
│   └── steps/              # one InstallStep class per wizard step
├── step/                   # fc step <name> — thin wrappers around steps/
├── ssl/                    # fc ssl setup, fc ssl list
├── site/, app/, service/, backup/, firewall/, ...
└── utils/                  # shell, errors, logging, validators
```

Tests live under `tests/` (one file per command group, plus `test_install_steps.py` for the wizard step classes and `test_dev_commands.py` for dev workflow).

---

## Contributing

1. Fork → feature branch.
2. Add or improve a command group / step.
3. Add tests in `tests/` (use `click.testing.CliRunner`).
4. Run `poetry run bash scripts/lint.sh` and `PYTHONPATH=src poetry run pytest`.
5. Open a PR with a clear description.

---

## About

Built by **Rashidi Okama** in Tanzania to make day-to-day Frappe work easier.

- Website: <https://rashidiokama.com>
- GitHub: <https://github.com/okama12>

Run `fc about` for the in-CLI credits panel. If this project saves you time, please [star the repo](https://github.com/okama12/frappe-cli) — it really helps.

---

## License

[MIT](LICENSE) © Rashidi Okama
