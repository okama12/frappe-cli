# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

- Show command help for bare `fp`; start the interactive wizard with `fp setup`.
- Add task-oriented `fp setup` with searchable prompts, custom component plans,
  review/edit/cancel, compact progress, plain redirected output, and recovery actions.
- Browse server directories when choosing a new bench location, with path
  completion, write-access checks, and the full destination shown before installation.
- Add direct installation commands and first-class daily commands with per-command
  bench/site overrides while retaining existing command syntax.
- Add domain-oriented HTTPS for Frappe, nginx, Apache, local application proxies,
  and certificate-only workflows, with certificate and endpoint verification.
- Preserve interrupted files and saved plans; prevent bench-init preview deletion,
  persist progress before the first step, and revalidate resources on resume.

## [0.1.0] - 2025-07-22
### Added
- Initial release of Frappe Installer CLI to PyPI
- Modular command groups for site, app, backup, service, firewall, rollback, ssl, optimize, monitor, config, maintenance, etc.
- Professional error handling and logging
- Automated testing and CI/CD
- Rich, colored CLI output and progress bars
- MIT license
