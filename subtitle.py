from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from logger import logger, console, log_detail
import re
from translate import translate_single, translate_batch

TIME_PATTERN = re.compile(r'^\d{2}:\d{2}:\d{2},\d{3}$')

def validate_time_format(time_str: str) -> bool:
    return bool(TIME_PATTERN.match(time_str))

@dataclass
class SubtitleEntry:
    """字幕条目"""
    index: int
    start_time: str
    end_time: str
    source_text: str
    target_text: str = ""

    def __post_init__(self):
        # 跳过空白时间戳的验证
        if not self.start_time.strip() or not self.end_time.strip():
            return
            
        if not validate_time_format(self.start_time):
            raise ValueError(f"无效的开始时间格式: {self.start_time}")
        if not validate_time_format(self.end_time):
            raise ValueError(f"无效的结束时间格式: {self.end_time}")

def parse_srt(file_path: str) -> List[SubtitleEntry]:
    """解析SRT字幕文件"""
    entries = []
    current_entry = None
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = [line.strip() for line in f]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 跳过空行
        if not line:
            if current_entry and current_entry.source_text:
                if current_entry.start_time and current_entry.end_time:  # 确保时间戳存在
                    entries.append(current_entry)
                current_entry = None
            i += 1
            continue
        
        # 字幕序号
        if line.isdigit():
            current_entry = SubtitleEntry(
                index=int(line),
                start_time="",
                end_time="",
                source_text=""
            )
            i += 1
            continue
        
        # 时间轴
        if ' --> ' in line and current_entry:
            try:
                start, end = line.split(' --> ')
                current_entry.start_time = start.strip()
                current_entry.end_time = end.strip()
                i += 1
                continue
            except Exception as e:
                logger.warning(f"解析时间轴失败: {line} -> {str(e)}")
                i += 1
                continue
        
        # 字幕文本
        if current_entry:
            # 收集多行文本直到遇到空行或新的字幕序号
            text_lines = []
            while i < len(lines) and lines[i].strip():
                if lines[i].isdigit() or ' --> ' in lines[i]:
                    break
                text_lines.append(lines[i])
                i += 1
            current_entry.source_text = '\n'.join(text_lines)
        else:
            i += 1
    
    # 处理最后一条字幕
    if current_entry and current_entry.source_text:
        if current_entry.start_time and current_entry.end_time:
            entries.append(current_entry)
    
    return entries

def clean_text(text: str) -> str:
    """清理文本，移除数字前缀和多余标点"""
    if not text:
        return ""
    
    # 移除开头的数字和标点
    text = text.strip()
    
    # 匹配开头的数字和可能的分隔符
    number_prefix_pattern = re.compile(r'^\d+[.。,，、\s]*')
    text = number_prefix_pattern.sub('', text).strip()
    
    return text

async def translate_subtitles(
    entries: List[SubtitleEntry],
    translation_mode: str = "single",
    batch_size: int = 50,
    progress_file: Optional[Path] = None
) -> List[SubtitleEntry]:
    """翻译字幕条目"""
    try:
        total = len(entries)
        console.print(f"[info]开始翻译 {total} 条字幕[/info]")

        if translation_mode == "batch":
            # 计算批次数
            batch_count = (total + batch_size - 1) // batch_size
            
            for i in range(0, total, batch_size):
                current_batch = i // batch_size + 1
                batch = entries[i:i+batch_size]
                batch_size_actual = len(batch)
                
                console.print(f"[progress]▶ 翻译批次 {current_batch}/{batch_count} ({i+1}-{min(i+batch_size_actual, total)}/{total})[/progress]")
                
                texts = [clean_text(e.source_text) for e in batch]
                translations = await translate_batch(texts)
                
                for entry, trans in zip(batch, translations):
                    entry.target_text = trans.strip()
        
        else:  # single mode
            for i, entry in enumerate(entries, 1):
                console.print(f"[progress]▶ 翻译进度 {i}/{total}[/progress]", end="\r")
                
                clean_source = clean_text(entry.source_text)
                trans = await translate_single(clean_source)
                entry.target_text = trans.strip()
            
            console.print() # 换行
        
        console.print("[success]✓ 翻译完成[/success]")
        return entries
        
    except Exception as e:
        log_detail(f"翻译过程发生错误: {str(e)}")
        raise

def save_srt(entries: List[SubtitleEntry], output_path: str, chinese_only: bool = False) -> None:
    """保存为SRT格式字幕文件"""
    if not entries:
        raise ValueError("没有可用的字幕条目")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(entries, 1):
            f.write(f"{i}\n")
            f.write(f"{entry.start_time} --> {entry.end_time}\n")
            f.write(f"{entry.target_text}\n")
            if not chinese_only:
                f.write(f"{entry.source_text}\n")
            f.write("\n")

def save_lrcx(entries: List[SubtitleEntry], output_path: str, chinese_only: bool = False) -> None:
    """保存为LRCX格式歌词文件"""
    if not entries:
        raise ValueError("没有可用的歌词条目")
    
    output_path = str(Path(output_path).with_suffix('.lrcx'))
    
    def format_time(time_str: str) -> str:
        """将SRT时间格式转换为LRC时间标签"""
        try:
            h, m, s = time_str.split(':')
            s, ms = s.split(',')
            total_seconds = int(h) * 3600 + int(m) * 60 + int(s)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"[{minutes:02d}:{seconds:02d}.{ms[:2]}]"
        except:
            return time_str
    
    def clean_text(text: str) -> str:
        """清理文本，移除数字前缀和多余标点"""
        if not text:
            return ""
        text = text.strip()
        if text[0].isdigit():
            parts = text.split('.', 1) if '.' in text else text.split('。', 1)
            if len(parts) > 1 and parts[0].strip().isdigit():
                text = parts[1].strip()
        return text.strip('。，！？,.!?')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[ver:1.0]\n")
        f.write("[offset:0]\n")
        
        for entry in entries:
            time_tag = format_time(entry.start_time)
            source_text = clean_text(entry.source_text)
            target_text = clean_text(entry.target_text)
            
            if not source_text:  # 只检查原文是否为空
                continue
                
            # 写入原文
            f.write(f"{time_tag}{source_text}\n")
            # 写入翻译（如果不是仅中文模式）
            if not chinese_only:
                f.write(f"{time_tag}[tr:zh-Hans]{target_text}\n")

def parse_lrcx(file_path: str) -> List[SubtitleEntry]:
    """解析LRCX歌词文件"""
    entries = []
    index = 1
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        # 跳过空行和元数据行
        if not line or line.startswith('[ver:') or line.startswith('[offset:'):
            continue
            
        # 跳过翻译行
        if '[tr:' in line:
            continue
            
        # 解析时间标签和文本
        if line.startswith('['):
            try:
                time_tag = line[1:line.find(']')]
                text = line[line.find(']')+1:].strip()
                
                # 转换时间格式 [mm:ss.xx] -> HH:MM:SS,mmm
                minutes, seconds = time_tag.split(':')
                seconds, ms = seconds.split('.')
                time_str = f"00:{int(minutes):02d}:{int(seconds):02d},{int(ms+'0'):03d}"
                
                if text:  # 只添加有文本的行
                    entries.append(SubtitleEntry(
                        index=index,
                        start_time=time_str,
                        end_time=time_str,  # LRCX格式没有结束时间
                        source_text=text
                    ))
                    index += 1
            except Exception as e:
                logger.warning(f"解析LRCX行失败: {line} -> {str(e)}")
                
    return entries
