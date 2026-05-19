# tests/test_install_steps.py
import time
from unittest.mock import MagicMock, patch

from frappe_cli.install.context import InstallContext


def make_ctx(**overrides):
    defaults = dict(
        bench_name="frappe-bench",
        site_name="mysite.com",
        frappe_branch="version-15",
        app_url="https://github.com/frappe/erpnext",
        app_branch="version-15",
        sudo_password="secret",
        mariadb_root_password="dbpass",
        admin_password="adminpass",
        ssl_email="admin@mysite.com",
        ubuntu_version="22.04",
        dry_run=False,
        debug=False,
    )
    defaults.update(overrides)
    return InstallContext(**defaults)


# ── SystemUpdateStep ──────────────────────────────────────────────────────────


class TestSystemUpdateStep:
    def test_check_true_when_stamp_is_fresh(self):
        from frappe_cli.install.steps.system import SystemUpdateStep

        step = SystemUpdateStep()
        with patch("frappe_cli.install.steps.system.Path") as mock_path:
            mock_stamp = MagicMock()
            mock_stamp.exists.return_value = True
            mock_stamp.stat.return_value = MagicMock(st_mtime=time.time() - 3600)
            mock_path.return_value = mock_stamp
            assert step.check(make_ctx()) is True

    def test_check_false_when_stamp_missing(self):
        from frappe_cli.install.steps.system import SystemUpdateStep

        step = SystemUpdateStep()
        with patch("frappe_cli.install.steps.system.Path") as mock_path:
            mock_stamp = MagicMock()
            mock_stamp.exists.return_value = False
            mock_path.return_value = mock_stamp
            assert step.check(make_ctx()) is False

    def test_check_false_when_stamp_old(self):
        from frappe_cli.install.steps.system import SystemUpdateStep

        step = SystemUpdateStep()
        with patch("frappe_cli.install.steps.system.Path") as mock_path:
            mock_stamp = MagicMock()
            mock_stamp.exists.return_value = True
            mock_stamp.stat.return_value = MagicMock(st_mtime=time.time() - 90000)
            mock_path.return_value = mock_stamp
            assert step.check(make_ctx()) is False

    def test_run_calls_apt_update_and_upgrade(self):
        from frappe_cli.install.steps.system import SystemUpdateStep

        step = SystemUpdateStep()
        ctx = make_ctx()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            step.run(ctx)
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("apt-get" in c and "update" in c for c in calls)
        assert any("apt-get" in c and "upgrade" in c for c in calls)

    def test_dry_run_does_not_call_subprocess(self):
        from frappe_cli.install.steps.system import SystemUpdateStep

        step = SystemUpdateStep()
        ctx = make_ctx(dry_run=True)
        with patch("subprocess.run") as mock_run:
            step.run(ctx)
        mock_run.assert_not_called()


# ── SystemDepsStep ────────────────────────────────────────────────────────────


class TestSystemDepsStep:
    def test_check_returns_true_when_all_packages_present(self):
        from frappe_cli.install.steps.system import SystemDepsStep

        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_returns_false_when_package_missing(self):
        from frappe_cli.install.steps.system import SystemDepsStep

        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False

    def test_run_installs_required_packages(self):
        from frappe_cli.install.steps.system import SYSTEM_PACKAGES, SystemDepsStep

        step = SystemDepsStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            step.run(make_ctx())
        all_args = [str(a) for c in mock_run.call_args_list for a in c.args[0]]
        for pkg in SYSTEM_PACKAGES:
            assert pkg in all_args


# ── UvCheckStep ───────────────────────────────────────────────────────────────


class TestUvCheckStep:
    def test_check_returns_true_when_uv_installed(self):
        from frappe_cli.install.steps.uv_check import UvCheckStep

        step = UvCheckStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_returns_false_when_uv_missing(self):
        from frappe_cli.install.steps.uv_check import UvCheckStep

        step = UvCheckStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False


# ── NodeJSStep ────────────────────────────────────────────────────────────────


class TestNodeJSStep:
    def test_check_true_when_correct_node_version(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="v18.20.4\n")
            assert NodeJSStep().check(make_ctx(ubuntu_version="22.04")) is True

    def test_check_false_when_wrong_node_version(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="v16.0.0\n")
            assert NodeJSStep().check(make_ctx(ubuntu_version="22.04")) is False

    def test_check_false_when_node_missing(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            assert NodeJSStep().check(make_ctx()) is False

    def test_run_uses_node18_for_2204(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep

        ctx = make_ctx(ubuntu_version="22.04")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            NodeJSStep().run(ctx)
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "18" in all_args

    def test_run_uses_node20_for_2404(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep

        ctx = make_ctx(ubuntu_version="24.04")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            NodeJSStep().run(ctx)
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "20" in all_args


# ── MariaDB ───────────────────────────────────────────────────────────────────


class TestMariaDBInstallStep:
    def test_check_true_when_running_and_config_exists(self, tmp_path):
        from frappe_cli.install.steps.mariadb import MariaDBInstallStep

        step = MariaDBInstallStep()
        fake_cnf = tmp_path / "99-frappe.cnf"
        fake_cnf.write_text("[mysqld]")
        with patch("subprocess.run") as mock_run, patch.object(
            step, "CNF_PATH", str(fake_cnf)
        ):
            mock_run.return_value = MagicMock(returncode=0)
            assert step.check(make_ctx()) is True

    def test_check_false_when_mysqladmin_fails(self):
        from frappe_cli.install.steps.mariadb import MariaDBInstallStep

        step = MariaDBInstallStep()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert step.check(make_ctx()) is False


class TestMariaDBSecureStep:
    def test_check_true_when_password_auth_works(self):
        from frappe_cli.install.steps.mariadb import MariaDBSecureStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert MariaDBSecureStep().check(make_ctx()) is True

    def test_check_false_when_auth_fails(self):
        from frappe_cli.install.steps.mariadb import MariaDBSecureStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert MariaDBSecureStep().check(make_ctx()) is False


# ── RedisStep ─────────────────────────────────────────────────────────────────


class TestRedisStep:
    def test_check_true_when_ping_returns_pong(self):
        from frappe_cli.install.steps.redis import RedisStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="PONG\n")
            assert RedisStep().check(make_ctx()) is True

    def test_check_false_when_ping_fails(self):
        from frappe_cli.install.steps.redis import RedisStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            assert RedisStep().check(make_ctx()) is False


# ── WkhtmltopdfStep ───────────────────────────────────────────────────────────


class TestWkhtmltopdfStep:
    def test_check_true_when_installed(self):
        from frappe_cli.install.steps.wkhtmltopdf import WkhtmltopdfStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="wkhtmltopdf 0.12.6")
            assert WkhtmltopdfStep().check(make_ctx()) is True

    def test_check_false_when_not_installed(self):
        from frappe_cli.install.steps.wkhtmltopdf import WkhtmltopdfStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert WkhtmltopdfStep().check(make_ctx()) is False


# ── BenchInstallStep ──────────────────────────────────────────────────────────


class TestBenchInstallStep:
    def test_check_true_when_bench_present(self):
        from frappe_cli.install.steps.bench import BenchInstallStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="5.29.1\n", stderr=""
            )
            assert BenchInstallStep().check(make_ctx()) is True

    def test_check_false_when_bench_completely_missing(self):
        """Non-fresh VPS without bench anywhere -> need to install."""
        from frappe_cli.install.steps.bench import BenchInstallStep

        with (
            patch("subprocess.run", side_effect=FileNotFoundError()),
            patch("pathlib.Path.exists", return_value=False),
        ):
            assert BenchInstallStep().check(make_ctx()) is False

    def test_check_true_via_fallback_path_when_not_on_PATH(self, tmp_path):
        """Bench installed via pip into /usr/local/bin but `bench` not on PATH
        (sudo env etc.). check() must still detect it and skip install."""
        from frappe_cli.install.steps.bench import BenchInstallStep

        fake_bench = tmp_path / "bench"
        fake_bench.write_text("#!/bin/sh\necho 5.29.1")
        fake_bench.chmod(0o755)

        call_log = []

        def fake_run(cmd, *args, **kwargs):
            call_log.append(cmd)
            # First call: `bench --version` from PATH -> not found
            if cmd == ["bench", "--version"]:
                raise FileNotFoundError()
            # Subsequent fallback calls use the absolute path
            return MagicMock(returncode=0, stdout="5.29.1\n", stderr="")

        step = BenchInstallStep()
        with (
            patch("subprocess.run", side_effect=fake_run),
            patch.object(
                BenchInstallStep,
                "_CANDIDATE_PATHS",
                (fake_bench,),
            ),
        ):
            assert step.check(make_ctx()) is True

    def test_check_logs_existing_benches(self, tmp_path):
        """A non-fresh VPS with existing benches should announce them so the
        user sees the wizard is sharing the host."""
        from frappe_cli.install.steps.bench import BenchInstallStep

        (tmp_path / "test2-bench" / "apps" / "frappe").mkdir(parents=True)
        (tmp_path / "test2-bench" / "sites").mkdir()
        (tmp_path / "test3-bench" / "apps" / "frappe").mkdir(parents=True)
        (tmp_path / "test3-bench" / "sites").mkdir()

        logs: list[str] = []
        ctx = make_ctx()
        ctx.log_fn = logs.append

        with (
            patch("subprocess.run") as mock_run,
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            mock_run.return_value = MagicMock(
                returncode=0, stdout="5.29.1\n", stderr=""
            )
            assert BenchInstallStep().check(ctx) is True

        joined = "\n".join(logs)
        assert "Found existing bench" in joined
        assert "test2-bench" in joined
        assert "test3-bench" in joined

    def test_run_calls_uv_tool_install(self):
        from frappe_cli.install.steps.bench import BenchInstallStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            BenchInstallStep().run(make_ctx())
        all_args = [c.args[0] for c in mock_run.call_args_list]
        assert any("uv" in a and "tool" in a and "install" in a for a in all_args)


# ── BenchInitStep ─────────────────────────────────────────────────────────────


class TestBenchInitStep:
    def test_check_true_when_apps_frappe_exists(self, tmp_path):
        from frappe_cli.install.steps.init_bench import BenchInitStep

        # Create the bench directory structure: home/bench_name/apps/frappe
        bench_dir = tmp_path / "mybenches" / "frappe-bench"
        (bench_dir / "apps" / "frappe").mkdir(parents=True)
        ctx = make_ctx(bench_name="frappe-bench")
        with patch("pathlib.Path.home", return_value=tmp_path / "mybenches"):
            assert BenchInitStep().check(ctx) is True

    def test_check_false_when_bench_missing(self, tmp_path):
        from frappe_cli.install.steps.init_bench import BenchInitStep

        ctx = make_ctx(bench_name="nonexistent-bench")
        with patch("pathlib.Path.home", return_value=tmp_path):
            assert BenchInitStep().check(ctx) is False

    def test_check_announces_existing_bench_dir(self, tmp_path):
        """When the target bench is already initialised, log it so the user
        knows the wizard skipped re-init (non-fresh VPS scenario)."""
        from frappe_cli.install.steps.init_bench import BenchInitStep

        bench_dir = tmp_path / "test4-bench"
        (bench_dir / "apps" / "frappe").mkdir(parents=True)

        logs: list[str] = []
        ctx = make_ctx(bench_name="test4-bench")
        ctx.log_fn = logs.append

        with patch("pathlib.Path.home", return_value=tmp_path):
            assert BenchInitStep().check(ctx) is True
        assert any("test4-bench" in line for line in logs)

    def test_run_calls_bench_init(self):
        from frappe_cli.install.steps.init_bench import BenchInitStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            BenchInitStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "bench" in all_args and "init" in all_args


# ── SiteCreateStep ────────────────────────────────────────────────────────────


class TestSiteCreateStep:
    def test_check_true_when_site_config_exists(self, tmp_path):
        from frappe_cli.install.steps.site import SiteCreateStep

        # Create the bench directory structure: home/bench_name/sites/site_name/site_config.json
        bench_dir = tmp_path / "mybenches" / "frappe-bench"
        site_dir = bench_dir / "sites" / "mysite.com"
        site_dir.mkdir(parents=True)
        (site_dir / "site_config.json").write_text("{}")
        ctx = make_ctx(site_name="mysite.com")
        with patch("pathlib.Path.home", return_value=tmp_path / "mybenches"):
            assert SiteCreateStep().check(ctx) is True

    def test_check_false_when_site_missing(self, tmp_path):
        from frappe_cli.install.steps.site import SiteCreateStep

        ctx = make_ctx(site_name="mysite.com")
        with patch("pathlib.Path.home", return_value=tmp_path):
            assert SiteCreateStep().check(ctx) is False

    def test_run_calls_bench_new_site_with_passwords(self):
        from frappe_cli.install.steps.site import SiteCreateStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            SiteCreateStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "new-site" in all_args
        assert "--mariadb-root-password" in all_args
        assert "--admin-password" in all_args


# ── AppGetStep ────────────────────────────────────────────────────────────────


class TestAppGetStep:
    def test_check_true_when_app_dir_exists(self, tmp_path):
        from frappe_cli.install.steps.app import AppGetStep

        (tmp_path / "apps" / "erpnext").mkdir(parents=True)
        ctx = make_ctx()
        with patch("pathlib.Path.home", return_value=tmp_path / "bench_parent"):
            # Create the expected directory structure
            bench_parent = tmp_path / "bench_parent"
            bench_parent.mkdir(exist_ok=True)
            (bench_parent / "frappe-bench" / "apps" / "erpnext").mkdir(parents=True)
            assert AppGetStep().check(ctx) is True

    def test_check_false_when_app_missing(self, tmp_path):
        from frappe_cli.install.steps.app import AppGetStep

        ctx = make_ctx()
        with patch("pathlib.Path.home", return_value=tmp_path):
            assert AppGetStep().check(ctx) is False

    def test_run_calls_bench_get_app(self):
        from frappe_cli.install.steps.app import AppGetStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            AppGetStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "get-app" in all_args


# ── AppInstallStep ────────────────────────────────────────────────────────────


class TestAppInstallStep:
    def test_check_true_when_app_listed(self):
        from frappe_cli.install.steps.app import AppInstallStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="erpnext\nfrappe\n")
            assert AppInstallStep().check(make_ctx()) is True

    def test_check_false_when_app_not_listed(self):
        from frappe_cli.install.steps.app import AppInstallStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="frappe\n")
            assert AppInstallStep().check(make_ctx()) is False


# ── SSLSetupStep ──────────────────────────────────────────────────────────────


class TestSSLSetupStep:
    def test_check_true_when_cert_exists(self, tmp_path):
        from frappe_cli.install.steps.ssl import SSLSetupStep

        cert_dir = tmp_path / "live" / "mysite.com"
        cert_dir.mkdir(parents=True)
        (cert_dir / "fullchain.pem").write_text("cert")
        step = SSLSetupStep()
        with patch.object(step, "_cert_path", return_value=cert_dir / "fullchain.pem"):
            assert step.check(make_ctx()) is True

    def test_run_calls_bench_lets_encrypt(self):
        from frappe_cli.install.steps.ssl import SSLSetupStep

        step = SSLSetupStep()
        with (
            patch("subprocess.run") as mock_run,
            patch.object(step, "_sudo_with_stdin") as mock_sudo_stdin,
        ):
            # `which certbot` returns 0 -> skip apt-get install
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            step.run(make_ctx())

        assert mock_sudo_stdin.called
        invoked_cmd = mock_sudo_stdin.call_args.args[1]
        joined = " ".join(invoked_cmd)
        assert "setup" in joined and "lets-encrypt" in joined
        assert "mysite.com" in joined
        # Two interactive prompts are answered "y"
        assert mock_sudo_stdin.call_args.kwargs.get("stdin") == b"y\ny\n"


# ── DnsMultitenantStep ────────────────────────────────────────────────────────


class TestDnsMultitenantStep:
    def test_check_true_when_dns_multitenant_set(self, tmp_path):
        from frappe_cli.install.steps.dns_multitenant import DnsMultitenantStep

        bench_dir = tmp_path / "mybenches" / "frappe-bench"
        sites_dir = bench_dir / "sites"
        sites_dir.mkdir(parents=True)
        (sites_dir / "common_site_config.json").write_text('{"dns_multitenant": true}')
        ctx = make_ctx()
        with patch("pathlib.Path.home", return_value=tmp_path / "mybenches"):
            assert DnsMultitenantStep().check(ctx) is True

    def test_check_false_when_dns_multitenant_missing(self, tmp_path):
        from frappe_cli.install.steps.dns_multitenant import DnsMultitenantStep

        bench_dir = tmp_path / "mybenches" / "frappe-bench"
        sites_dir = bench_dir / "sites"
        sites_dir.mkdir(parents=True)
        (sites_dir / "common_site_config.json").write_text("{}")
        ctx = make_ctx()
        with patch("pathlib.Path.home", return_value=tmp_path / "mybenches"):
            assert DnsMultitenantStep().check(ctx) is False

    def test_check_false_when_config_missing(self, tmp_path):
        from frappe_cli.install.steps.dns_multitenant import DnsMultitenantStep

        ctx = make_ctx()
        with patch("pathlib.Path.home", return_value=tmp_path):
            assert DnsMultitenantStep().check(ctx) is False

    def test_run_calls_bench_config_dns_multitenant_on(self):
        from frappe_cli.install.steps.dns_multitenant import DnsMultitenantStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            DnsMultitenantStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "config" in all_args
        assert "dns_multitenant" in all_args
        assert "on" in all_args


# ── ProductionSetupStep — self-heal + verification ───────────────────────────


class TestProductionSetupStepVerify:
    def test_check_requires_both_nginx_and_supervisor(self):
        from frappe_cli.install.steps.production import ProductionSetupStep

        step = ProductionSetupStep()
        ctx = make_ctx(bench_name="frappe-bench")

        # Only nginx exists -> NOT done yet (supervisor missing == still partial)
        with patch("frappe_cli.install.steps.production.Path") as mock_path:

            def side_effect(path):
                mock = MagicMock()
                mock.exists.return_value = "nginx" in str(path)
                return mock

            mock_path.side_effect = side_effect
            assert step.check(ctx) is False

        # Both exist -> done
        with patch("frappe_cli.install.steps.production.Path") as mock_path:
            mock = MagicMock()
            mock.exists.return_value = True
            mock_path.return_value = mock
            assert step.check(ctx) is True

    def test_verify_supervisor_running_returns_when_all_running(self):
        from frappe_cli.install.steps.production import ProductionSetupStep

        ctx = make_ctx(bench_name="test3-bench")
        status_output = (
            "test3-bench-redis:test3-bench-redis-cache  RUNNING  pid 1, uptime 0:01\n"
            "test3-bench-web:test3-bench-frappe-web     RUNNING  pid 2, uptime 0:01\n"
        ).encode()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=status_output, stderr=b""
            )
            ProductionSetupStep()._verify_supervisor_running(ctx, timeout=1)

    def test_verify_supervisor_running_raises_on_timeout(self):
        from frappe_cli.install.steps.base import StepError
        from frappe_cli.install.steps.production import ProductionSetupStep

        ctx = make_ctx(bench_name="test3-bench")
        with (
            patch("subprocess.run") as mock_run,
            patch("time.sleep"),
        ):
            # No matching bench lines at all -> never satisfied
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            try:
                ProductionSetupStep()._verify_supervisor_running(ctx, timeout=1)
            except StepError as e:
                assert "test3-bench" in e.message
            else:
                raise AssertionError("StepError not raised")

    def test_verify_supervisor_running_raises_when_not_running(self):
        from frappe_cli.install.steps.base import StepError
        from frappe_cli.install.steps.production import ProductionSetupStep

        ctx = make_ctx(bench_name="test3-bench")
        status_output = (
            b"test3-bench-redis:test3-bench-redis-cache  FATAL    exit status 1\n"
        )
        with (
            patch("subprocess.run") as mock_run,
            patch("time.sleep"),
        ):
            mock_run.return_value = MagicMock(
                returncode=3, stdout=status_output, stderr=b""
            )
            try:
                ProductionSetupStep()._verify_supervisor_running(ctx, timeout=1)
            except StepError as e:
                assert "FATAL" in e.hint
            else:
                raise AssertionError("StepError not raised")

    def test_bench_redis_ports_parses_config(self, tmp_path):
        from frappe_cli.install.steps.production import ProductionSetupStep

        bench_dir = tmp_path / "mybenches" / "frappe-bench"
        sites_dir = bench_dir / "sites"
        sites_dir.mkdir(parents=True)
        (sites_dir / "common_site_config.json").write_text(
            '{"redis_queue": "redis://127.0.0.1:11004", '
            '"redis_cache": "redis://127.0.0.1:13004", '
            '"redis_socketio": "redis://127.0.0.1:13004"}'
        )
        ctx = make_ctx(bench_name="frappe-bench")
        with patch("pathlib.Path.home", return_value=tmp_path / "mybenches"):
            ports = sorted(ProductionSetupStep()._bench_redis_ports(ctx))
        assert ports == [11004, 13004]

    def test_verify_redis_pong_raises_on_timeout(self):
        from frappe_cli.install.steps.base import StepError
        from frappe_cli.install.steps.production import ProductionSetupStep

        ctx = make_ctx()
        step = ProductionSetupStep()
        with (
            patch.object(step, "_bench_redis_ports", return_value=[11004]),
            patch("socket.create_connection", side_effect=OSError("refused")),
            patch("time.sleep"),
        ):
            try:
                step._verify_redis_pong(ctx, timeout=1)
            except StepError as e:
                assert "11004" in e.message
            else:
                raise AssertionError("StepError not raised")


# ── ALL_STEPS registry ────────────────────────────────────────────────────────


def test_all_steps_has_correct_count():
    from frappe_cli.install.steps import ALL_STEPS

    assert len(ALL_STEPS) == 17


def test_all_steps_have_unique_names():
    from frappe_cli.install.steps import ALL_STEPS

    names = [s.name for s in ALL_STEPS]
    assert len(names) == len(set(names))


def test_dns_multitenant_runs_before_production():
    from frappe_cli.install.steps import ALL_STEPS

    names = [s.name for s in ALL_STEPS]
    assert names.index("dns_multitenant") < names.index("production_setup")


def test_app_install_check_uses_substring_match():
    """`bench list-apps` prints `erpnext 15.108.1 version-15`, not bare names."""
    from frappe_cli.install.steps.app import AppInstallStep

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="frappe  15.107.5 version-15\nerpnext 15.108.1 version-15\n",
        )
        assert AppInstallStep().check(make_ctx()) is True
