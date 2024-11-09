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
    async def get_config(cls) -> Dict[str, Any]:
        """获取API配置"""
        if cls._instance is None:
            config = get_config()
            client = AsyncOpenAI(
                api_key=config["api_key"],
                base_url=config["api_base"],
                timeout=30.0
            )
            
            cls._instance = {
                "client": client,
                "model": config["model"],
                "temperature": config["translation"]["temperature"],
                "prompts": {
                    "batch": config["translation"]["prompts"]["batch"],
                    "single": config["translation"]["prompts"]["single"]
                },
                "max_retries": config["translation"]["max_retries"],
                "retry_delay": config["translation"]["retry_delay"]
            }
        return cls._instance

async def make_request(messages: List[dict], config: Optional[Dict[str, Any]] = None) -> str:
    """发送API请求"""
    if config is None:
        config = await APIClient.get_config()
        
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
            log_detail(f"API请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            
            if attempt == max_retries - 1:
                raise TranslationError(f"API请求失败: {str(e)}")
                
            delay = retry_delay * (2 ** attempt)
            log_detail(f"等待 {delay} 秒后重试...")
            await asyncio.sleep(delay)

async def translate_text(text: str, prompt: str, config: Optional[Dict[str, Any]] = None) -> str:
    """统一的翻译处理"""
    if not text.strip():
        return ""
        
    if config is None:
        config = await APIClient.get_config()
    
    try:
        result = await make_request([
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ], config)
        return result.strip()
    except Exception as e:
        raise TranslationError(f"翻译失败: {text} -> {str(e)}")

async def translate_single(text: str, config: Optional[Dict[str, Any]] = None) -> str:
    """翻译单条文本"""
    if config is None:
        config = await APIClient.get_config()
    return await translate_text(text, config["prompts"]["single"], config)

async def translate_batch(texts: List[str], config: Optional[Dict[str, Any]] = None) -> List[str]:
    """批量翻译文本"""
    if not texts:
        return []
        
    if config is None:
        config = await APIClient.get_config()
        
    try:
        # 过滤空行并记录位置
        valid_indices = [(i, text) for i, text in enumerate(texts) if text.strip()]
        if not valid_indices:
            return [''] * len(texts)
            
        indices, valid_texts = zip(*valid_indices)
        formatted_input = "\n".join(f"{i+1}. {text}" for i, text in enumerate(valid_texts))
        
        console.print(f"[info]批量翻译 {len(valid_texts)} 条字幕...[/info]")
        try:
            response = await translate_text(
                formatted_input,
                config["prompts"]["batch"],
                config
            )
        except TranslationError:
            # 批量翻译失败时切换到单条模式
            log_detail("批量翻译失败，切换到单条翻译模式")
            translations = []
            for text in valid_texts:
                try:
                    trans = await translate_single(text, config)
                    translations.append(trans)
                except TranslationError:
                    translations.append("")
            
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
            
            match = re.match(r'^\d+[.。、\s]*(.+)$', line)
            translations.append(match.group(1).strip() if match else line)
        
        # 结果数量验证
        if len(translations) != len(valid_texts):
            log_detail(f"翻译结果行数不匹配，进行修复")
            if len(translations) < len(valid_texts):
                translations.extend([''] * (len(valid_texts) - len(translations)))
            else:
                translations = translations[:len(valid_texts)]
        
        # 还原到原始位置
        result = [''] * len(texts)
        for idx, trans in zip(indices, translations):
            result[idx] = trans
            
        return result
        
    except Exception as e:
        raise TranslationError(f"批量翻译失败: {str(e)}")
