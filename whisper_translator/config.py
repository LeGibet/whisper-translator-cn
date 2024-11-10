import yaml
import os
from typing import Dict, Any
from pathlib import Path

class ConfigurationError(Exception):
    """配置错误异常"""
    pass

def validate_config(config: Dict[str, Any]) -> None:
    """验证配置有效性"""
    if not isinstance(config, dict):
        raise ConfigurationError("配置文件格式错误")
    
    # 基础配置验证
    if not isinstance(config.get("api_key"), str) or not config["api_key"]:
        raise ConfigurationError("API 密钥不能为空")
    if not isinstance(config.get("api_base"), str) or not config["api_base"].startswith(("http://", "https://")):
        raise ConfigurationError("无效的 API 基础URL")
    if not isinstance(config.get("model"), str):
        raise ConfigurationError("无效的模型名称")
    
    # Whisper配置验证
    whisper = config.get("whisper", {})
    if not isinstance(whisper, dict):
        raise ConfigurationError("无效的 whisper 配置格式")
    
    engine = whisper.get("engine")
    if not engine or engine not in ["faster-whisper", "whisper-cpp"]:
        raise ConfigurationError("无效的 whisper engine 配置")
    
    if engine == "whisper-cpp":
        cpp_config = whisper.get("whisper_cpp", {})
        if not cpp_config.get("binary_path") or not cpp_config.get("model_path"):
            raise ConfigurationError("whisper-cpp 需要配置 binary_path 和 model_path")
    elif not whisper.get("faster_whisper", {}).get("model"):
        raise ConfigurationError("faster-whisper 需要配置 model")
    
    # 翻译配置验证
    translation = config.get("translation", {})
    if not isinstance(translation, dict):
        raise ConfigurationError("无效的翻译配置格式")
    
    prompts = translation.get("prompts", {})
    if not isinstance(prompts, dict) or not prompts.get("single") or not prompts.get("batch"):
        raise ConfigurationError("prompts 配置需要包含 single 和 batch")
    
    required_fields = {
        "temperature": float,
        "max_retries": int,
        "retry_delay": int
    }
    
    for field, field_type in required_fields.items():
        value = translation.get(field)
        if not isinstance(value, field_type):
            raise ConfigurationError(f"无效的配置值: translation.{field}")

def get_config() -> Dict[str, Any]:
    """读取并验证配置"""
    try:
        config_path = Path("config.yaml")
        
        # 搜索配置文件位置
        search_paths = [
            Path.cwd() / "config.yaml",  # 当前目录
            Path.home() / ".config" / "whisper_translator" / "config.yaml",  # 用户配置目录
        ]
        
        for path in search_paths:
            if path.exists():
                config_path = path
                break
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 从环境变量读取配置
        env_configs = {
            "OPENAI_API_KEY": "api_key",
            "OPENAI_API_BASE": "api_base",
            "OPENAI_API_MODEL": "model",
        }
        
        for env_var, config_key in env_configs.items():
            if env_var in os.environ:
                config[config_key] = os.environ[env_var]
            
        # 设置默认值
        if "translation" not in config:
            config["translation"] = {
                "max_retries": 3,
                "retry_delay": 1,
                "temperature": 0.2,
                "prompts": {
                    "batch": "将以下语音识别的字幕逐行翻译成中文。注意每行是一条字幕，输出的翻译字幕行数必须与输入必须严格一致，用换行符分隔。若某行内容无法识别或无实际意义，则返回空行。保持原文语气和语境，考虑上下文连贯。仅输出翻译结果，不要附加解释。",
                    "single": "将此语音识别的字幕翻译成中文，保持原文语气和语境。若原文识别不清楚或没有实际意义则不翻译，返回空行。仅输出翻译结果，不要附加解释。"
                }
            }
            
        if "whisper" not in config:
            config["whisper"] = {
                "engine": "faster-whisper",
                "whisper_cpp": {
                    "binary_path": "/path/to/whisper.cpp",
                    "model_path": "/path/to/models/model.bin"
                },
                "faster_whisper": {
                    "model": "base",
                    "compute_type": "float16",
                    "cpu_threads": 4
                }
            }
            
        validate_config(config)
        return config
        
    except FileNotFoundError:
        raise ConfigurationError("找不到配置文件 config.yaml")
    except yaml.YAMLError:
        raise ConfigurationError("配置文件格式错误")

def get_whisper_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """获取 whisper 配置"""
    return config["whisper"]

def init_config(config_path: Path) -> None:
    """初始化配置文件"""
    if config_path.exists():
        return
        
    # 确保目录存在
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 复制模板文件
    template_path = Path(__file__).parent / "config.yaml.template"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as src, \
             open(config_path, "w", encoding="utf-8") as dst:
            dst.write(src.read())
    else:
        raise ConfigurationError("找不到配置模板文件")
