"""
Configuration Loader
Simple YAML config file loader
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """Simple configuration loader for YAML files"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize config loader
        
        Args:
            config_path: Path to config file (default: config/live_trading.yaml)
        """
        if config_path is None:
            # Default to config/live_trading.yaml in project root
            project_root = Path(__file__).parent.parent
            config_path = project_root / 'config' / 'live_trading.yaml'
        
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        
        if self.config_path.exists():
            self.load()
        else:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
    
    def load(self):
        """Load configuration from YAML file"""
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value by dot notation key
        
        Args:
            key: Dot notation key (e.g., 'trading.mode')
            default: Default value if key not found
            
        Returns:
            Config value
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_trading_config(self) -> Dict:
        """Get trading configuration"""
        return self.config.get('trading', {})
    
    def get_risk_config(self) -> Dict:
        """Get risk management configuration"""
        return self.config.get('risk', {})
    
    def get_schedule_config(self) -> Dict:
        """Get schedule configuration"""
        return self.config.get('schedule', {})
    
    def get_filters_config(self) -> Dict:
        """Get filters configuration"""
        return self.config.get('filters', {})
    
    def get_alerts_config(self) -> Dict:
        """Get alerts configuration"""
        return self.config.get('alerts', {})
    
    def get_database_config(self) -> Dict:
        """Get database configuration"""
        return self.config.get('database', {})
    
    def get_logging_config(self) -> Dict:
        """Get logging configuration"""
        return self.config.get('logging', {})
    
    def save(self, config_path: str = None):
        """
        Save configuration to YAML file
        
        Args:
            config_path: Path to save config (default: use loaded path)
        """
        save_path = Path(config_path) if config_path else self.config_path
        
        with open(save_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
    
    def update(self, key: str, value: Any):
        """
        Update config value by dot notation key
        
        Args:
            key: Dot notation key (e.g., 'trading.mode')
            value: New value
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def __repr__(self) -> str:
        return f"ConfigLoader(path={self.config_path})"
