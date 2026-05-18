from frappe_cli.install.context import InstallContext
from pathlib import Path


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


def test_app_name_from_plain_url():
    ctx = make_ctx(app_url="https://github.com/frappe/erpnext")
    assert ctx.app_name == "erpnext"


def test_app_name_strips_git_suffix():
    ctx = make_ctx(app_url="https://github.com/frappe/erpnext.git")
    assert ctx.app_name == "erpnext"


def test_app_name_custom_app():
    ctx = make_ctx(app_url="https://github.com/myorg/my_custom_app.git")
    assert ctx.app_name == "my_custom_app"


def test_bench_path_is_under_home():
    ctx = make_ctx(bench_name="frappe-bench")
    assert ctx.bench_path == Path.home() / "frappe-bench"


def test_skip_ssl_defaults_false():
    ctx = make_ctx()
    assert ctx.skip_ssl is False


def test_skip_ssl_can_be_set():
    ctx = make_ctx(skip_ssl=True)
    assert ctx.skip_ssl is True
