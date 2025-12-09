import os
import yaml
import logging

# Default configuration paths
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')

def load_config(path=CONFIG_PATH):
    """Load configuration from a YAML file."""
    if not os.path.exists(path):
        logging.warning(f"Config file not found at {path}. Using defaults.")
        return {}
    
    with open(path, 'r') as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logging.error(f"Error parsing config file: {e}")
            return {}

# Load config once
_config = load_config()

def get_config(key, default=None):
    """Get a configuration value using dot notation (e.g., 'llm.model_vision')."""
    keys = key.split('.')
    value = _config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return default
    
    return value if value is not None else default

# Expose specific settings for easy access
OLLAMA_URL = get_config('llm.ollama_url', "http://localhost:11434/api/generate")
MODEL_VISION = get_config('llm.model_vision', "llava")
MODEL_TEXT = get_config('llm.model_text', "qwen3:8b")
MAX_WORKERS = get_config('processing.max_workers', 4)
RETRY_ATTEMPTS = get_config('processing.retry_attempts', 3)
RETRY_DELAY = get_config('processing.retry_delay', 2)
