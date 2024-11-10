import asyncio
import re
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from .config import get_config
from .logger import console, logger

def create_openai_client() -> Dict[str, Any]:
    """创建OpenAI客户端和配置"""
    config = get_config()
    return {
        "client": AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config["api_base"],
            timeout=30.0
        ),
        "model": config["model"],
        "config": {
            "temperature": config["translation"]["temperature"],
            "batch_prompt": config["translation"]["prompts"]["batch"],
            "single_prompt": config["translation"]["prompts"]["single"],
            "max_retries": config["translation"]["max_retries"],
            "retry_delay": config["translation"]["retry_delay"]
        }
    }

async def make_request(
    messages: List[dict],
    client: Optional[Dict[str, Any]] = None
) -> str:
    """发送API请求并处理重试"""
    if client is None:
        client = create_openai_client()
    
    config = client["config"]
    max_retries = config["max_retries"]
    retry_delay = config["retry_delay"]
    
    for attempt in range(max_retries):
        try:
            response = await client["client"].chat.completions.create(
                model=client["model"],
                messages=messages,
                temperature=config["temperature"]
            )
            result = response.choices[0].message.content.strip()
            return result
            
        except Exception as e:
            logger.debug(f"API请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(retry_delay * (2 ** attempt))

async def translate_single(
    text: str,
    client: Optional[Dict[str, Any]] = None
) -> str:
    """翻译单条文本"""
    if not text.strip():
        return ""
        
    if client is None:
        client = create_openai_client()
        
    result = await make_request([
        {"role": "system", "content": client["config"]["single_prompt"]},
        {"role": "user", "content": text}
    ], client)
    
    # 记录翻译结果
    logger.debug(f"翻译: {text} -> {result}")
    return result.strip()

def parse_batch_response(response: str) -> List[str]:
    """解析批量翻译响应"""
    lines = response.split('\n')
    translations = []
    current_text = []
    
    for line in lines:
        line = line.strip()
        
        # 如果是新的编号行，保存之前的翻译
        if re.match(r'^\d+[.。、]', line):
            if current_text:
                translations.append(' '.join(current_text))
                current_text = []
            # 移除行号
            text = re.sub(r'^\d+[.。、\s]*', '', line).strip()
            if text:
                current_text.append(text)
        elif line:
            current_text.append(line)
    
    # 添加最后一条翻译
    if current_text:
        translations.append(' '.join(current_text))
    
    return translations

async def translate_batch(
    texts: List[str],
    client: Optional[Dict[str, Any]] = None,
    batch_size: int = 50
) -> List[str]:
    """批量翻译文本"""
    if not texts:
        return []
    
    if client is None:
        client = create_openai_client()
    
    # 移除空行并记录位置
    valid_texts = [(i, text) for i, text in enumerate(texts) if text.strip()]
    if not valid_texts:
        return [''] * len(texts)
    
    result = [''] * len(texts)
    total_valid = len(valid_texts)
    
    # 批量处理
    for start in range(0, total_valid, batch_size):
        batch_indices = valid_texts[start:start + batch_size]
        batch_texts = [text for _, text in batch_indices]
        
        # 格式化输入
        formatted_input = '\n'.join(
            f"{i+1}. {text}" for i, text in enumerate(batch_texts)
        )
        
        try:
            console.print(
                f"[info]批量翻译 {len(batch_texts)} 条字幕 "
                f"({start+1}-{min(start+len(batch_texts), total_valid)}/{total_valid})[/info]"
            )
            
            response = await make_request([
                {"role": "system", "content": client["config"]["batch_prompt"]},
                {"role": "user", "content": formatted_input}
            ], client)
            
            translations = parse_batch_response(response)
            
            # 记录翻译结果
            for orig, trans in zip(batch_texts, translations):
                logger.debug(f"翻译: {orig} -> {trans}")
            
            # 验证翻译数量
            if len(translations) != len(batch_texts):
                logger.warning(
                    f"翻译行数不匹配 (预期: {len(batch_texts)}, 实际: {len(translations)})"
                )
                translations.extend([''] * (len(batch_texts) - len(translations)))
            
            # 还原到原始位置
            for (orig_index, _), trans_text in zip(batch_indices, translations):
                result[orig_index] = trans_text.strip()
                
        except Exception as e:
            logger.error(f"批量翻译失败: {str(e)}")
            return [''] * len(texts)
    
    return result
