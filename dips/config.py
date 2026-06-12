"""設定ファイル（settings/mapping/code_map）の読込とパス解決。"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# リポジトリのルート（このファイルの2階層上: dips/ の親）
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_settings() -> dict:
    return _load_yaml(CONFIG_DIR / "settings.yaml")


def load_mapping() -> dict:
    return _load_yaml(CONFIG_DIR / "mapping.yaml")


def load_code_map() -> dict:
    return _load_yaml(CONFIG_DIR / "code_map.yaml")


class Paths:
    """settings.yaml から解決した各種パス。"""

    def __init__(self, settings: dict):
        self.data_dir = Path(settings["data_dir"])
        self.master = self.data_dir / settings["master_file"]
        self.output_dir = self.data_dir / settings["output_dir"]
        self.log_dir = self.data_dir / settings["log_dir"]
        self.export_log = self.data_dir / settings["export_log"]
        # 雛形はリポジトリ相対
        self.dips_template = REPO_ROOT / settings["dips_template"]

    def ensure_dirs(self) -> None:
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)


def load_all():
    """(settings, mapping, code_map, Paths) をまとめて返す。"""
    settings = load_settings()
    mapping = load_mapping()
    code_map = load_code_map()
    return settings, mapping, code_map, Paths(settings)
