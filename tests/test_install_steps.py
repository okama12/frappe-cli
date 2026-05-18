# tests/test_install_steps.py
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
    def test_check_always_returns_false(self):
        from frappe_cli.install.steps.system import SystemUpdateStep

        step = SystemUpdateStep()
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
    def test_check_true_when_node_present(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert NodeJSStep().check(make_ctx()) is True

    def test_check_false_when_node_missing(self):
        from frappe_cli.install.steps.nodejs import NodeJSStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
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
            mock_run.return_value = MagicMock(returncode=0)
            assert BenchInstallStep().check(make_ctx()) is True

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
        assert "--mariadb-root-password-from-env" in all_args
        assert "--admin-password-from-env" in all_args


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

    def test_run_calls_certbot(self):
        from frappe_cli.install.steps.ssl import SSLSetupStep

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")
            SSLSetupStep().run(make_ctx())
        all_args = " ".join(str(a) for c in mock_run.call_args_list for a in c.args[0])
        assert "certbot" in all_args
        assert "mysite.com" in all_args
        assert "admin@mysite.com" in all_args


# ── ALL_STEPS registry ────────────────────────────────────────────────────────


def test_all_steps_has_correct_count():
    from frappe_cli.install.steps import ALL_STEPS

    assert len(ALL_STEPS) == 15


def test_all_steps_have_unique_names():
    from frappe_cli.install.steps import ALL_STEPS

    names = [s.name for s in ALL_STEPS]
    assert len(names) == len(set(names))
