import yaml
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    with open('config.yaml', 'r') as config_file:
        return yaml.safe_load(config_file)

CONFIG = load_config()
