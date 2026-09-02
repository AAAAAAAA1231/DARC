from pathlib import Path

from backend.core.paths import BUNDLE_ROOT, DATA_ROOT, PROJECT_ROOT, config_path, frontend_dist


def test_unfrozen_roots_point_at_project():
    assert BUNDLE_ROOT == DATA_ROOT == PROJECT_ROOT
    assert config_path().name == "config.yaml"
    assert config_path().exists()
    assert (BUNDLE_ROOT / "backend" / "desktop_app.py").exists()


def test_frontend_dist_exists_for_packaging():
    dist = frontend_dist()
    assert dist.exists(), "run npm run build before packaging the EXE"
    assert (dist / "index.html").exists()


def test_packaging_splash_exists():
    assert (BUNDLE_ROOT / "packaging" / "splash.png").exists()
    assert (BUNDLE_ROOT / "packaging" / "pyi_runtime_hook_stdio.py").exists()
