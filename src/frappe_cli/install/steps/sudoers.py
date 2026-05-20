"""Wizard step: grant passwordless ``bench restart`` / ``fp restart``."""

from frappe_cli.utils.sudoers import SUDOERS_PATH, enable, is_managed

from .base import InstallStep, StepError


class SudoersSetupStep(InstallStep):
    name = "sudoers_setup"
    description = "Allow passwordless fp restart (supervisorctl)"

    def check(self, ctx) -> bool:
        """Skip when the drop-in already exists and was written by frappe-cli."""
        if not getattr(ctx, "enable_passwordless_restart", False):
            return True  # User opted out — nothing to do.
        return is_managed()

    def run(self, ctx) -> None:
        if not getattr(ctx, "enable_passwordless_restart", False):
            if ctx.log_fn:
                ctx.log_fn("Passwordless restart skipped (opt-out).")
            return

        if ctx.log_fn:
            ctx.log_fn(f"Writing sudoers drop-in: {SUDOERS_PATH}")

        try:
            enable(ctx.sudo_password, dry_run=ctx.dry_run)
        except RuntimeError as exc:
            raise StepError(
                "Failed to configure passwordless restart",
                hint=str(exc),
            ) from exc

        if ctx.log_fn:
            ctx.log_fn("✓ Passwordless fp restart enabled")

    def rollback(self, ctx) -> None:
        """Remove the drop-in if this step wrote it."""
        if not SUDOERS_PATH.exists() or not is_managed():
            return
        try:
            from frappe_cli.utils.sudoers import disable

            disable(ctx.sudo_password, dry_run=ctx.dry_run)
        except RuntimeError:
            pass
