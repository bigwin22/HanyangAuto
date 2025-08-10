import os
import json
from typing import Dict, Any, List


def get_data_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


CONFIG_PATH = os.path.join(get_data_dir(), 'config.json')


DEFAULT_CONFIG: Dict[str, Any] = {
    "allowed_hosts": [
        "hanyang.newme.dev",
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
    ],
    # 기본은 동일 오리진만 허용. 필요시 관리자 페이지에서 추가하도록 확장 가능
    "allowed_origins": [],
}


def load_config() -> Dict[str, Any]:
    os.makedirs(get_data_dir(), exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 기본 키 보정
        for k, v in DEFAULT_CONFIG.items():
            if k not in data:
                data[k] = v
        return data
    except Exception:
        # 손상 시 기본값으로 복구
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    os.makedirs(get_data_dir(), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)



