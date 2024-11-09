import asyncio
import re
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from .config import get_config
from .logger import console, log_detail, get_logger

class TranslationError(Exception):
    """翻译错误"""
    pass

class APIClient:
    """API客户端管理类"""
    _instance: Optional[Dict[str, Any]] = None
    
    @classmethod
    async def get_instance(cls) -> Dict[str, Any]:
        """获取单例配置实例"""
        if cls._instance is None:
            config = get_config()
            cls._instance = {
                "client": AsyncOpenAI(
                    api_key=config["api_key"],
                    base_url=config["api_base"],
                    timeout=30.0
                ),
                "model": config["model"],
                "temperature": config["translation"]["temperature"],
                "batch_prompt": config["translation"]["prompts"]["batch"],
                "single_prompt": config["translation"]["prompts"]["single"],
                "max_retries": config["translation"]["max_retries"],
                "retry_delay": config["translation"]["retry_delay"]
            }
        return cls._instance

async def make_request(messages: List[dict], config: Optional[Dict[str, Any]] = None) -> str:
    """发送API请求并处理重试逻辑"""
    logger = get_logger()
    if config is None:
        config = await APIClient.get_instance()
        
    max_retries = config["max_retries"]
    retry_delay = config["retry_delay"]
    
    for attempt in range(max_retries):
        try:
            log_detail(f"API请求: {messages}")
            response = await config["client"].chat.completions.create(
                model=config["model"],
                messages=messages,
                temperature=config["temperature"]
            )
            result = response.choices[0].message.content.strip()
            log_detail(f"API响应: {result}")
            return result
            
        except Exception as e:
            error_msg = str(e)
            log_detail(f"API请求失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
            
            if attempt == max_retries - 1:  # 最后一次重试
                raise TranslationError(f"API请求失败: {error_msg}")
                
            # 计算退避时间
            delay = retry_delay * (2 ** attempt)
            log_detail(f"等待 {delay} 秒后重试...")
            await asyncio.sleep(delay)

async def translate_single(text: str, config: Optional[Dict[str, Any]] = None) -> str:
    """翻译单条文本"""
    logger = get_logger()
    if not text.strip():
        return ""
        
    if config is None:
        config = await APIClient.get_instance()
        
    try:
        result = await make_request([
            {"role": "system", "content": config["single_prompt"]},
            {"role": "user", "content": text}
        ], config)
        return result.strip()
    except Exception as e:
        error_msg = f"单条翻译失败: {text} -> {str(e)}"
        log_detail(error_msg)
        if isinstance(e, TranslationError):
            raise
        raise TranslationError(error_msg)

async def translate_batch(texts: List[str], config: Optional[Dict[str, Any]] = None) -> List[str]:
    """批量翻译文本"""
    logger = get_logger()
    if not texts:
        return []
        
    if config is None:
        config = await APIClient.get_instance()
        
    try:
        # 过滤空行并记录位置
        valid_indices = [(i, text) for i, text in enumerate(texts) if text.strip()]
        if not valid_indices:
            return [''] * len(texts)
            
        indices, valid_texts = zip(*valid_indices)
        formatted_input = "\n".join(f"{i+1}. {text}" for i, text in enumerate(valid_texts))
        
        console.print(f"[info]批量翻译 {len(valid_texts)} 条字幕...[/info]")
        try:
            response = await make_request([
                {"role": "system", "content": config["batch_prompt"]},
                {"role": "user", "content": formatted_input}
            ], config)
        except TranslationError:
            # 如果批量翻译失败，尝试单条翻译
            log_detail("批量翻译失败，切换到单条翻译模式")
            translations = []
            for text in valid_texts:
                try:
                    trans = await translate_single(text, config)
                    translations.append(trans)
                except TranslationError as e:
                    log_detail(f"单条翻译失败: {str(e)}")
                    translations.append("")  # 对于失败的翻译，使用空字符串
            
            # 还原到原始位置
            result = [''] * len(texts)
            for idx, trans in zip(indices, translations):
                result[idx] = trans
            return result
        
        # 解析批量翻译结果
        translations = []
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue
            # 移除行号前缀
            match = re.match(r'^\d+[.。、\s]*(.+)$', line)
            translations.append(match.group(1).strip() if match else line)
        
        # 结果数量验证和修复
        if len(translations) != len(valid_texts):
            log_detail(
                f"翻译结果行数不匹配: 预期 {len(valid_texts)} 行，实际 {len(translations)} 行"
                f"将进行结果修复"
            )
            # 如果结果少了，补充空字符串
            if len(translations) < len(valid_texts):
                translations.extend([''] * (len(valid_texts) - len(translations)))
            # 如果结果多了，截断
            else:
                translations = translations[:len(valid_texts)]
        
        # 还原到原始位置
        result = [''] * len(texts)
        for idx, trans in zip(indices, translations):
            result[idx] = trans
            
        return result
        
    except Exception as e:
        error_msg = f"批量翻译失败: {str(e)}"
        log_detail(error_msg)
        if isinstance(e, TranslationError):
            raise
        raise TranslationError(error_msg)
