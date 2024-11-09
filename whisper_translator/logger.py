import logging
import functools
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any, TypeVar
from rich.console import Console
from rich.theme import Theme
from rich.logging import RichHandler
import rich.errors
from .config import ConfigurationError

# 自定义主题色彩
custom_theme = Theme({
    'info': 'cyan',
    'warning': 'yellow',
    'error': 'red',
    'success': 'green',
    'progress': 'blue'
})

# 全局控制台和日志器实例
console = Console(theme=custom_theme)
logger: Optional[logging.Logger] = None

# 类型变量定义
F = TypeVar('F', bound=Callable[..., Any])
AsyncF = TypeVar('AsyncF', bound=Callable[..., Any])

class DetailedLogHandler(logging.FileHandler):
    """详细日志处理器"""
    def __init__(self, filename: str) -> None:
        super().__init__(filename, encoding='utf-8')
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.setFormatter(formatter)
        
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.stream.write(msg + '\n')
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logger(log_to_file: bool = False) -> Optional[Path]:
    """
    设置日志系统
    
    Args:
        log_to_file: 是否启用文件日志
        
    Returns:
        Optional[Path]: 日志文件路径（如果启用了文件日志）
    """
    global logger
    
    # 创建logger
    logger = logging.getLogger('whisper_translator')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    # 控制台处理器 - 简洁输出
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
        markup=True,
        tracebacks_suppress=[rich.errors]
    )
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    console_handler.addFilter(
        lambda record: not getattr(record, 'detailed_only', False)
    )
    logger.addHandler(console_handler)
    
    # 文件日志处理器 - 详细输出
    if log_to_file:
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'translate_{timestamp}.log'
        
        file_handler = DetailedLogHandler(str(log_file))
        logger.addHandler(file_handler)
        return log_file
    
    return None

def log_detail(message: str) -> None:
    """
    记录详细日志信息
    
    Args:
        message: 日志信息
    """
    if logger:
        record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        record.detailed_only = True
        logger.handle(record)

def api_call(func: F) -> F:
    """
    API调用装饰器，处理异常并记录日志
    
    Args:
        func: 要装饰的函数
        
    Returns:
        装饰后的函数
    """
    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            log_detail(f"API调用失败: {func.__name__} -> {str(e)}")
            raise
            
    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log_detail(f"API调用失败: {func.__name__} -> {str(e)}")
            raise
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

def handle_error(e: Exception) -> None:
    """
    统一错误处理
    
    Args:
        e: 异常对象
    """
    # 错误类型映射
    error_prefixes = {
        FileNotFoundError: "找不到文件",
        ConfigurationError: "配置错误",
        rich.errors.LiveError: "显示错误：不能同时显示多个进度条",
        PermissionError: "权限错误",
        ValueError: "参数错误",
        OSError: "系统错误"
    }
    
    # 获取错误前缀
    prefix = error_prefixes.get(type(e), "错误")
    error_msg = f"{prefix}: {str(e)}"
    
    # 记录到日志
    if logger:
        logger.error(error_msg)
    
    # 控制台显示
    console.print(f"[error]✗ {error_msg}[/error]")

def get_logger() -> logging.Logger:
    """
    获取或初始化logger
    
    Returns:
        logging.Logger: 日志器实例
    """
    global logger
    if logger is None:
        setup_logger()
    assert logger is not None  # 类型检查
    return logger
