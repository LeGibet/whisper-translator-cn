from typing import Dict, Any
import yaml
import os

class ConfigurationError(Exception):
    """配置错误异常"""
    pass

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
    """读取并验证基础配置"""
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # 支持从环境变量读取 API 密钥
        if "OPENAI_API_KEY" in os.environ:
            config["api_key"] = os.environ["OPENAI_API_KEY"]
            
        validate_config(config)
        return config
        
    except FileNotFoundError:
        raise ConfigurationError("找不到配置文件 config.yaml")
    except yaml.YAMLError:
        raise ConfigurationError("配置文件格式错误")

def get_whisper_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """获取 whisper 配置"""
    return config["whisper"]