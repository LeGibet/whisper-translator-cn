import asyncio
import re
from typing import List
from openai import AsyncOpenAI
from config import get_config
from logger import console, log_detail, logger

async def create_client() -> dict:
    """创建翻译客户端和配置"""
    config = get_config()
    return {
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

async def make_request(messages: List[dict], config: dict = None) -> str:
    """发送API请求并处理重试逻辑"""
    if config is None:
        config = await create_client()
        
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
            if attempt == max_retries - 1:  # 最后一次重试
                logger.error(f"API请求失败: {str(e)}")
                raise
            await asyncio.sleep(retry_delay * (2 ** attempt))  # 指数退避

async def translate_single(text: str, config: dict = None) -> str:
    """翻译单条文本"""
    if not text.strip():
        return ""
        
    if config is None:
        config = await create_client()
        
    try:
        result = await make_request([
            {"role": "system", "content": config["single_prompt"]},
            {"role": "user", "content": text}
        ], config)
        return result.strip()
    except Exception as e:
        logger.error(f"翻译失败: {text} -> {str(e)}")
        return ""

async def translate_batch(texts: List[str], config: dict = None) -> List[str]:
    """批量翻译文本"""
    if not texts:
        return []
        
    if config is None:
        config = await create_client()
        
    try:
        # 过滤空行并记录位置
        valid_indices = [(i, text) for i, text in enumerate(texts) if text.strip()]
        if not valid_indices:
            return [''] * len(texts)
            
        indices, valid_texts = zip(*valid_indices)
        formatted_input = "\n".join(f"{i+1}. {text}" for i, text in enumerate(valid_texts))
        
        console.print(f"[info]批量翻译 {len(valid_texts)} 条字幕...[/info]")
        response = await make_request([
            {"role": "system", "content": config["batch_prompt"]},
            {"role": "user", "content": formatted_input}
        ], config)
        
        # 解析翻译结果
        translations = []
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue
            # 移除行号前缀
            match = re.match(r'^\d+[.。、\s]*(.+)$', line)
            translations.append(match.group(1).strip() if match else line)
        
        # 还原到原始位置
        result = [''] * len(texts)
        valid_count = min(len(translations), len(valid_texts))
        
        if valid_count != len(valid_texts):
            logger.warning(
                f"翻译结果行数不匹配: 预期 {len(valid_texts)} 行，实际 {len(translations)} 行\n"
                f"将尽可能使用已有翻译结果"
            )
            
        for i in range(valid_count):
            result[indices[i]] = translations[i]
            
        return result
        
    except Exception as e:
        logger.error(f"批量翻译失败: {str(e)}")
        return [''] * len(texts)
