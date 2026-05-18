# frappe-cli — Production Installer Design Spec

**Date:** 2026-05-18  
**Author:** Rashidi Okama  
**Status:** Approved

---

## 1. Problem

Manually installing Frappe on a production VPS requires memorising 15+ ordered steps, running commands across apt, pip/uv, MariaDB, bench, nginx, supervisor, and certbot — in the right order, with the right config, handling prompts along the way. One missed step or wrong config breaks the whole stack. This is tedious, error-prone, and has to be repeated for every new VPS.

---

## 2. Goal

A `pip`/`uv`-installable CLI tool (`frappe-cli`) that automates the complete end-to-end production installation of Frappe on an Ubuntu 22.04 or 24.04 VPS — from raw server to a live HTTPS Frappe site with any app — through a single interactive wizard command: `frappe install`.

---

## 3. Scope

**In scope:**
- Production-only installation (nginx + supervisor, SSL via certbot)
- Ubuntu 22.04 LTS and 24.04 LTS
- Any Frappe app installable by GitHub URL
- One app per install run (additional apps can be added by re-running)
- Resume support: retry a failed install from the point of failure

**Out of scope (for now):**
- Development mode installs
- Docker-based installs
- Multi-app installs in a single run
- Non-Ubuntu distros

---

## 4. Bootstrap (user does this once per VPS)

```bash
sudo apt update && sudo apt upgrade -y
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv tool install frappe-cli
frappe install
```

The user runs as their VPS sudo user (e.g. `ubuntu`, `deploy`). No separate `frappe` OS user is created. `bench setup production` uses `$(whoami)`.

---

## 5. Architecture

### 5.1 What stays

The existing module layout is kept:
- One directory per command group (`install/`, `site/`, `ssl/`, `service/`, `backup/`, etc.)
- Shared utilities in `utils/` (`shell.py`, `logging.py`, `errors.py`, `validators.py`)
- Existing day-2 commands (`frappe ssl setup`, `frappe site backup`, `frappe service restart`) stay as-is after deduplication cleanup

### 5.2 What changes

1. **Deduplication** — every module that has its own copy of `RichShell` / `setup_logger` gets those replaced with imports from `utils/shell.py` and `utils/logging.py`
2. **New UI layer** — `src/frappe_cli/ui/` with shared Rich components
3. **New install wizard** — `src/frappe_cli/install/wizard.py` — the main `frappe install` command
4. **New step modules** — `src/frappe_cli/install/steps/` — one file per install step
5. **Resume state** — `src/frappe_cli/install/state.py` — tracks completed steps

### 5.3 New directory additions

```
src/frappe_cli/
  ui/
    __init__.py
    prompts.py        # styled Rich input collection
    steps.py          # live step-list renderer (✓ / ⠸ / ○ / ✗)
    panels.py         # header, summary, error panels
  install/
    wizard.py         # `frappe install` orchestrator (NEW)
    state.py          # resume state manager (NEW)
    steps/            # one file per install step (NEW)
      __init__.py
      system.py       # apt update/upgrade + system deps
      uv_check.py     # verify/install uv
      nodejs.py       # Node.js 18/20 + Yarn via NodeSource
      mariadb.py      # install + utf8mb4 config + secure install
      redis.py        # redis-server
      wkhtmltopdf.py  # version-aware install per Ubuntu version
      bench.py        # uv tool install frappe-bench
      init_bench.py   # bench init
      site.py         # bench new-site
      app.py          # bench get-app + bench install-app
      production.py   # bench setup production
      ssl.py          # certbot
```

---

## 6. Install Context

All wizard inputs and auto-detected values live in one dataclass passed to every step. No globals.

```python
@dataclass
class InstallContext:
    bench_name: str           # default: "frappe-bench"
    site_name: str            # FQDN e.g. "mysite.com"
    frappe_branch: str        # e.g. "version-15"
    app_url: str              # GitHub URL of app to install
    app_branch: str           # e.g. "version-15"
    sudo_password: str        # in memory only, never written to disk
    mariadb_root_password: str
    admin_password: str
    ssl_email: str
    ubuntu_version: str       # auto-detected: "22.04" or "24.04"
    dry_run: bool
```

`ubuntu_version` is detected from `/etc/os-release` at startup. `app_name` is derived automatically from `app_url` by taking the last path segment and stripping `.git` (e.g. `https://github.com/frappe/erpnext.git` → `erpnext`). It controls:
- Node.js setup script URL (NodeSource 18.x vs 20.x)
- wkhtmltopdf download URL / apt source

---

## 7. Wizard UI Flow

### 7.1 Welcome panel

```
╭──────────────────────────────────────────────────────╮
│                                                      │
│   🌿  Frappe CLI  v0.1.x                            │
│       Production Server Installer                    │
│                                                      │
╰──────────────────────────────────────────────────────╯

  Let's get your Frappe production server ready.
  This will install bench, configure MariaDB, create
  a site, install your app, and set up SSL.
```

### 7.2 Input collection

```
  ┌─ Server Configuration ──────────────────────────┐
  │  Bench name         [frappe-bench] ›            │
  │  Site name (FQDN)   › mysite.com               │
  │  Frappe branch      [version-15] ›              │
  ├─ App ───────────────────────────────────────────┤
  │  App GitHub URL     › https://github.com/…      │
  │  App branch         [version-15] ›              │
  ├─ Credentials ───────────────────────────────────┤
  │  Sudo (VPS admin)   › ••••••••                  │
  │  MariaDB root pwd   › ••••••••                  │
  │  Site admin pwd     › ••••••••                  │
  │  SSL email          › admin@mysite.com           │
  └─────────────────────────────────────────────────┘

  Ready to install. This will take 10–20 minutes.
  Continue? [Y/n] ›
```

All credentials collected upfront. No prompts during execution.

### 7.3 Live step execution

```
 ─── Installing Frappe Production Stack ──────────────

   ✓  System update & upgrade
   ✓  Install system dependencies
   ✓  Verify uv
   ✓  Install Node.js + Yarn
   ✓  Install & configure MariaDB
   ✓  Secure MariaDB
   ✓  Install Redis
   ✓  Install wkhtmltopdf
   ✓  Install frappe-bench (uv)
   ⠸  Initializing bench...              [02:14]
   ○  Create site
   ○  Get app from GitHub
   ○  Install app on site
   ○  Setup production (nginx + supervisor)
   ○  Configure SSL (Let's Encrypt)
```

Rendered with `rich.live`. Current step shows a spinner + elapsed time. Completed steps show ✓. Pending steps show ○.

### 7.4 Success summary

```
 ─── Installation Complete ───────────────────────────

  ╭─────────────────────────────────────────────────╮
  │  ✓  Frappe is live at https://mysite.com        │
  │                                                 │
  │  Bench       ~/frappe-bench                     │
  │  Site        mysite.com                         │
  │  App         erpnext  (version-15)              │
  │  SSL         Let's Encrypt — auto-renews        │
  ╰─────────────────────────────────────────────────╯

  Next steps:
    frappe service status   — check running services
    frappe site backup      — take a manual backup
    frappe ssl renew        — renew SSL certificate
```

### 7.5 Failure panel

```
   ✓  Install & configure MariaDB
   ✗  Secure MariaDB                     [failed]

  ╭─ Error ─────────────────────────────────────────╮
  │  mysql_secure_installation exited with code 1   │
  │                                                 │
  │  stderr: Access denied for user root@localhost  │
  │                                                 │
  │  Tip: Check that the MariaDB root password      │
  │       you entered is correct.                   │
  │                                                 │
  │  Fix the issue above, then re-run:              │
  │    frappe install --resume                       │
  ╰─────────────────────────────────────────────────╯
```

---

## 8. Installation Step Sequence

Each step implements `check() -> bool` (already done?) and `run(ctx: InstallContext)`. If `check()` returns `True`, the step is shown as ✓ skipped.

| # | Step | check() skips when… |
|---|------|---------------------|
| 1 | System update & upgrade | — always runs |
| 2 | System deps (python3-dev, git, build-essential, libssl-dev, libffi-dev, curl) | all packages present via `dpkg -l` |
| 3 | Verify uv / install if missing | `uv --version` succeeds |
| 4 | Node.js 18 (22.04) or 20 (24.04) + Yarn | `node --version` succeeds |
| 5 | Install MariaDB + write utf8mb4 config to `/etc/mysql/mariadb.conf.d/99-frappe.cnf` | `mysqladmin status` succeeds + config file exists |
| 6 | `mysql_secure_installation` (non-interactive, piped) | root login works with provided password |
| 7 | Install Redis | `redis-cli ping` returns PONG |
| 8 | Install wkhtmltopdf (version-aware per Ubuntu version) | `wkhtmltopdf --version` matches required version |
| 9 | `uv tool install frappe-bench` | `bench --version` succeeds |
| 10 | `bench init <bench-name> --frappe-branch <version>` | bench dir exists with `apps/frappe/` |
| 11 | `bench new-site <site> --db-root-password <pw> --admin-password <pw>` | `sites/<site>/site_config.json` exists |
| 12 | `bench get-app <app-url> --branch <version>` | app dir exists in `apps/` |
| 13 | `bench --site <site> install-app <app>` | app listed in `bench --site <site> list-apps` |
| 14 | `bench setup production $(whoami)` | nginx config exists for site |
| 15 | `certbot --nginx -d <site> --non-interactive --agree-tos -m <email>` | SSL cert exists and is valid |

### MariaDB utf8mb4 config written at step 5

```ini
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
```

---

## 9. Resume State

On failure, completed step names are written to `~/.frappe-cli-state.json`:

```json
{
  "bench_name": "frappe-bench",
  "site_name": "mysite.com",
  "frappe_branch": "version-15",
  "app_url": "https://github.com/frappe/erpnext",
  "app_branch": "version-15",
  "ssl_email": "admin@mysite.com",
  "ubuntu_version": "22.04",
  "completed_steps": ["system", "deps", "uv", "nodejs", "mariadb", "secure_mariadb"]
}
```

Passwords are **never** written to state. On `--resume`, the wizard reads state, re-prompts for credentials only, and skips completed steps.

---

## 10. sudo handling

All `sudo` commands use `sudo -S` (reads password from stdin) with the collected sudo password piped in. This ensures the full 15–25 minute install runs without any mid-process prompts.

```python
subprocess.run(
    ["sudo", "-S", ...],
    input=ctx.sudo_password + "\n",
    ...
)
```

---

## 11. CLI flags

```
frappe install              # full wizard
frappe install --resume     # resume from last failed step
frappe install --dry-run    # print all commands without executing
frappe install --debug      # show full command output during execution
```

---

## 12. Deduplication cleanup (parallel to wizard work)

Every existing module (`install/system.py`, `install/mariadb.py`, `ssl/setup.py`, etc.) that has its own `RichShell` class and `setup_logger()` gets those removed and replaced with:

```python
from ..utils.shell import RichShellRunner
from ..utils.logging import get_logger
```

This is a pure refactor — no behaviour changes to existing commands.

---

## 13. Testing

- Wizard input collection: tested with `click.testing.CliRunner` and mocked prompts
- Each step's `check()` and `run()`: unit tested with mocked `subprocess` calls
- `--dry-run` mode: integration test that runs the full wizard and asserts no real commands execute
- Resume: test that `--resume` with a state file skips the right steps
