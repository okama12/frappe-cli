# Frappe Installer CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A professional-grade, modular, and extensible command-line tool to automate Frappe deployment and server management on Ubuntu-based servers. Built with Python, Click, and best practices for production and developer workflows.

---

## 🚀 Overview

**Frappe Installer CLI** is a professional-grade, production-ready Python CLI for managing Frappe and ERPNext deployments. It provides a modern, developer-friendly alternative to Bash scripts, with:

- Consistent, colored output and progress bars (Rich/Click)
- Professional error handling and actionable messages
- Modular command groups for all aspects of Frappe/ERPNext management
- Automated backups, SSL, firewall, and security hardening
- Robust logging with log level control
- Automated tests and continuous integration for code quality

---

## ✨ Key Features

- **Step-by-step or full-stack install**
- **Config-driven**: YAML/JSON config for reproducible, production-safe installs
- **Multi-tenancy**: Manage multiple sites and apps
- **Automated backups**: External HD, cron, email alerts
- **SSL/HTTPS**: Certbot with auto-renewal
- **Firewall/UFW**: Secure defaults, custom ports
- **Service management**: Restart, status, logs
- **Security**: Fail2Ban, SSH hardening, log rotation
- **Extensible**: Modular command groups, easy to add features
- **Rich logging**: All actions logged to `/var/log/frappe-installer.log`
- **Professional error handling**: All user errors are clear and actionable
- **Automated testing**: Pytest and Click CLI runner for all commands
- **CI/CD**: Linting, formatting, and tests run on every push/PR (GitHub Actions)

---

## 🧱 Architecture & Developer Experience

- **Click**: CLI framework
- **Rich**: Colored output, progress bars, and prompts
- **Subprocess**: Executes system commands (apt, pip, nginx, etc.)
- **YAML/JSON**: Configurable install/runtime settings
- **Logging**: `/var/log/frappe-installer.log` (with logrotate)
- **Modular codebase**: Each command group in its own file/module
- **Automated tests**: All major commands and error cases covered
- **Code quality automation**: Black, flake8, isort, and CI pipeline

---

## 🧪 Automated Testing & Quality

- All commands are tested using `pytest` and `click.testing.CliRunner`
- Linting and formatting enforced with `flake8`, `black`, and `isort`
- GitHub Actions workflow runs tests and code checks on every PR
- See `requirements-dev.txt` for development dependencies

---

## 🛠️ Usage

```sh
frappe --help
frappe site create --help
frappe app clone --help
frappe backup setup --help
# ...and more
```

All commands support `--help` with examples. Use `--debug` and `--dry-run` for safe experimentation.

---

## 🤝 Contributing

- Keep commands modular (one file/module per group)
- Add new tests in `tests/` using `pytest` and `click.testing.CliRunner`
- Run `black`, `flake8`, and `isort` before PRs
- See `CONTRIBUTING.md` for more guidelines (coming soon)

---

## 📦 Installation

### Requirements
- Python ≥ 3.10
- Ubuntu 22.04/24.04 (Debian variants: partial support)
- [pipx](https://pypa.github.io/pipx/) (optional, for global CLI install)

### Quick Start (Dev)
```bash
# Clone the repo
cd frappe-installer/frappe_cli
python3 -m venv venv
source venv/bin/activate
pip install --editable .
frappe --help
```

### Quick Start (Production)
```bash
pipx install git+https://github.com/your/repo
frappe --help
```

---

## 🧩 Command Structure

```bash
frappe <group> <action> [options]
```

### Core Command Groups
| Group      | Description                       |
| ---------- | --------------------------------- |
| `install`  | Full or step-by-step system setup |
| `site`     | Site creation, listing, backup    |
| `service`  | Restart, view status, logs        |
| `ssl`      | HTTPS via Certbot                 |
| `firewall` | UFW/iptables config               |
| `backup`   | Manual + scheduled backups        |
| `app`      | Install/Update/Remove Frappe apps |
| `config`   | Config set/get/validate           |
| `monitor`  | Live logs and system health       |
| `optimize` | Performance tuning                |
| `rollback` | Backup restore or stage rollback  |
| `logrotate`| Log rotation management           |

---

## 🧪 Usage Examples

### Full Install (with config)
```bash
frappe install system --config production.yaml
frappe install user --config production.yaml
frappe install deps --config production.yaml
frappe install mariadb --config production.yaml
frappe install bench --config production.yaml
frappe install init --config production.yaml
frappe install prod --config production.yaml
```

### Create a Site
```bash
frappe site create --bench-name frappe-bench --site-name example.com --mariadb-root-password rootpass --admin-password admin123
```

### SSL Setup
```bash
frappe ssl setup --site-name example.com --email admin@example.com
```

### Backup Setup
```bash
frappe backup setup --admin-email admin@example.com --bench-name frappe-bench --site-name example.com
```

### Service Management
```bash
frappe service restart
frappe service status --bench-name frappe-bench --site-name example.com
```

### Firewall
```bash
frappe firewall setup
```

### App Management
```bash
frappe app clone --bench-name frappe-bench --repo-url https://github.com/your/app.git --branch main
```

### Rollback/Uninstall
```bash
frappe rollback uninstall --bench-name frappe-bench --site-name example.com
```

### Log Rotation
```bash
frappe logrotate setup
```

---

## 🛠️ Config File Usage

- Place your config in YAML (see `data/example_config.yaml`).
- Pass `--config production.yaml` to any command for reproducible, non-interactive installs.

**Example:**
```yaml
system:
  timezone: "Africa/Dar_es_Salaam"
  locale: "en_US.UTF-8"
  user: "frappe"
frappe:
  branch: "version-15"
  bench_name: "frappe-bench"
  site_name: "example.com"
  admin_password: "changeme"
  mariadb_root_password: "rootpass"
services:
  enable_ssl: true
  enable_ufw: true
backup:
  admin_email: "admin@example.com"
  external_hd_uuid: ""
  retention_days: 7
## 📝 License

This project is licensed under the [MIT License](LICENSE).

---

## 🛡️ Server Management Best Practices
- Timezone and locale configuration
- Dedicated `frappe` user
- Automatic UFW (firewall) setup
- Fail2Ban setup (optional)
- SSH hardening (optional)
- Certbot HTTPS auto-renewal
- Systemd + Supervisor integration
- Log rotation

---

## 🧠 Advanced/Extensible
- **Multi-tenancy:** `site list`, `site backup`, `site restore`
- **Monitoring:** `monitor logs`, `monitor health` (stubs for future)
- **Performance:** `optimize performance` (stub)
- **Config management:** `config set/get/validate` (stubs)

---

## 🐞 Troubleshooting
- All actions are logged to `/var/log/frappe-installer.log` (or local fallback)
- Use `frappe service status` to check system health
- Use `frappe logrotate setup` to prevent log bloat
- For permission issues, ensure you run as a sudo-capable user

---

## 🤝 Contributing

1. Fork the repo and create a feature branch
2. Add or improve a command group/module
3. Write clear commit messages and update the README if needed
4. Submit a pull request with a clear description

---

## 📄 License
MIT (or your preferred license) 