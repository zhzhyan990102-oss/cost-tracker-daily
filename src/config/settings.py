"""全局配置管理 - 所有敏感信息通过环境变量读取"""

import os
import yaml
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = Path(__file__).parent
CACHE_DIR = ROOT_DIR / "cache"

# 确保缓存目录存在
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---- 钉钉配置（从环境变量读取，不硬编码） ----
DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")
DINGTALK_SECRET = os.environ.get("DINGTALK_SECRET", "")

# ---- GitHub Actions 环境检测 ----
IS_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS", "false") == "true"

# ---- 路径配置 ----
ANCHORS_FILE = CONFIG_DIR / "price_anchors.yaml"
MAPPING_FILE = CONFIG_DIR / "materials_mapping.yaml"
REGISTRY_FILE = CONFIG_DIR / "collectors_registry.yaml"
HOLIDAYS_FILE = CONFIG_DIR / "holidays.yaml"


def load_yaml(filepath: Path) -> dict:
    """加载 YAML 配置文件"""
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_anchors() -> list:
    """获取人工价格锚点配置"""
    data = load_yaml(ANCHORS_FILE)
    return data.get("anchors", [])


def get_mappings() -> list:
    """获取原材料-产地-品类映射配置"""
    data = load_yaml(MAPPING_FILE)
    return data.get("mappings", [])


def get_collectors_registry() -> list:
    """获取采集器注册表配置"""
    data = load_yaml(REGISTRY_FILE)
    return data.get("collectors", [])


def get_holidays() -> list:
    """获取法定节假日列表"""
    data = load_yaml(HOLIDAYS_FILE)
    return data.get("holidays", [])
