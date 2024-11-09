from typing import Dict, Any, Optional
import yaml
import os
import shutil
from pathlib import Path
import pkg_resources

CONFIG_ENV_VAR = "WHISPER_TRANSLATOR_CONFIG"
DEFAULT_CONFIG_PATHS = [
    Path.cwd() / "config.yaml",  # 当前工作目录
    Path.home() / ".config" / "whisper_translator" / "config.yaml",  # 用户配置目录
]

class ConfigurationError(Exception):
    """配置错误异常"""
    pass

def get_template_path() -> str:
    """获取配置模板文件路径"""
    return pkg_resources.resource_filename('whisper_translator', 'config.yaml.template')

def init_config(config_path: Optional[Path] = None) -> Path:
    """
    初始化配置文件
    
    Args:
        config_path: 指定的配置文件路径，如果为None则使用默认路径

    Returns:
        Path: 创建的配置文件路径
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATHS[1]  # 默认使用用户配置目录
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not config_path.exists():
        template_path = get_template_path()
        shutil.copy2(template_path, config_path)
        print(f"已在 {config_path} 创建配置文件模板，请编辑此文件填入必要的配置信息。")
    
    return config_path

def find_config_file() -> Path:
    """
    查找配置文件
    
    优先级：
    1. 环境变量指定的路径
    2. 当前工作目录
    3. 用户配置目录
    """
    # 检查环境变量
    if CONFIG_ENV_VAR in os.environ:
        config_path = Path(os.environ[CONFIG_ENV_VAR])
        if config_path.exists():
            return config_path
        raise ConfigurationError(f"环境变量 {CONFIG_ENV_VAR} 指定的配置文件不存在: {config_path}")
    
    # 检查默认路径
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return path
    
    # 如果都不存在，初始化一个新的配置文件
    return init_config()

def validate_config(config: Dict[str, Any]) -> None:
    """验证基础配置有效性"""
    if not isinstance(config, dict):
        raise ConfigurationError("配置文件格式错误")
    
    # 基础配置验证
    if not isinstance(config.get("api_key"), str) or not config["api_key"]:
        raise ConfigurationError("API 密钥不能为空")
        
    if not isinstance(config.get("api_base"), str) or not config["api_base"].startswith(("http://", "https://")):
        raise ConfigurationError("无效的 API 基础URL")
        
    if not isinstance(config.get("model"), str):
        raise ConfigurationError("无效的模型名称")
    
    # Whisper 配置验证
    whisper = config.get("whisper", {})
    engine = whisper.get("engine")
    if not engine or engine not in ["faster-whisper", "whisper-cpp"]:
        raise ConfigurationError("无效的 whisper engine 配置")
    
    if engine == "whisper-cpp":
        cpp_config = whisper.get("whisper_cpp", {})
        if not cpp_config.get("binary_path") or not cpp_config.get("model_path"):
            raise ConfigurationError("whisper-cpp 需要配置 binary_path 和 model_path")
    else:  # faster-whisper
        fw_config = whisper.get("faster_whisper", {})
        if not fw_config.get("model"):
            raise ConfigurationError("faster-whisper 需要配置 model")

def get_config() -> Dict[str, Any]:
    """
    读取并验证配置
    
    配置加载优先级：
    1. 环境变量中的配置值（如API密钥）
    2. 配置文件中的值
    """
    try:
        config_path = find_config_file()
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # 支持从环境变量覆盖配置
        if "OPENAI_API_KEY" in os.environ:
            config["api_key"] = os.environ["OPENAI_API_KEY"]
        
        if "OPENAI_API_BASE" in os.environ:
            config["api_base"] = os.environ["OPENAI_API_BASE"]
            
        validate_config(config)
        return config
        
    except FileNotFoundError:
        raise ConfigurationError(f"找不到配置文件: {config_path}")
    except yaml.YAMLError:
        raise ConfigurationError("配置文件格式错误")

def get_whisper_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """获取 whisper 配置"""
    return config["whisper"]
