import json
import os
import threading
from utils.signals import event_bus

class ConfigManager:
    """线程安全的单例配置管理器"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config_file="system_config.json"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConfigManager, cls).__new__(cls)
                cls._instance.config_file = config_file
                cls._instance._config_cache = {}
                cls._instance.load()
        return cls._instance

    def _get_default_config(self):
        return {
            "system": {
                "theme": "dark",
                "language": "zh_CN",
                "log_level": "INFO"
            },
            "inference": {
                "default_output_dir": "./exports",
                "last_model_path": "",
                "hardware_backend": "CUDA"
            }
        }

    def load(self):
        """防错加载机制"""
        if not os.path.exists(self.config_file):
            self._config_cache = self._get_default_config()
            self.save()
            return

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
        except Exception as e:
            event_bus.inference_error.emit(f"配置读取失败，已回退至出厂设置。原因: {str(e)}")
            self._config_cache = self._get_default_config()

    def save(self):
        """原子化写入，防止断电导致配置文件损坏"""
        temp_file = self.config_file + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_cache, f, indent=4, ensure_ascii=False)
            os.replace(temp_file, self.config_file)
        except Exception as e:
            event_bus.inference_error.emit(f"配置固化失败: {str(e)}")

    def get(self, section, key, default=None):
        return self._config_cache.get(section, {}).get(key, default)

    def set(self, section, key, value):
        if section not in self._config_cache:
            self._config_cache[section] = {}
        self._config_cache[section][key] = value
        self.save()