from pathlib import Path

from frappe_cli.utils.ssl_cert import (
    _bench_letsencrypt_config_exists,
    _bench_nginx_has_ssl,
    cert_exists,
)


def test_cert_exists_via_nginx_without_sudo(tmp_path):
    bench = tmp_path / "my-bench"
    conf_dir = bench / "config"
    conf_dir.mkdir(parents=True)
    (conf_dir / "nginx.conf").write_text(
        "ssl_certificate /etc/letsencrypt/live/erp.example.com/fullchain.pem;\n"
    )
    assert cert_exists("erp.example.com", bench_path=bench) is True


def test_bench_letsencrypt_config_exists(tmp_path, monkeypatch):
    cfg = tmp_path / "site.cfg"
    cfg.write_text("domains = test6.example.com\n")

    real_path = Path

    def path_factory(p):
        if str(p) == "/etc/letsencrypt/configs/test6.example.com.cfg":
            return cfg
        return real_path(p)

    monkeypatch.setattr("frappe_cli.utils.ssl_cert.Path", path_factory)
    assert _bench_letsencrypt_config_exists("test6.example.com") is True


def test_bench_nginx_has_ssl(tmp_path):
    bench = tmp_path / "bench"
    conf_dir = bench / "config"
    conf_dir.mkdir(parents=True)
    (conf_dir / "nginx.conf").write_text(
        "ssl_certificate /etc/letsencrypt/live/site.example.com/fullchain.pem;\n"
    )
    assert _bench_nginx_has_ssl("site.example.com", bench) is True
    assert _bench_nginx_has_ssl("other.example.com", bench) is False
