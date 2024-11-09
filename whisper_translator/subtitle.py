from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path
from .logger import get_logger, console, log_detail
import re
from .translate import translate_single, translate_batch

TIME_PATTERN = re.compile(r'^\d{2}:\d{2}:\d{2},\d{3}$')
NUMBER_PREFIX_PATTERN = re.compile(r'^\d+[.。,，、\s]*')

@dataclass
class SubtitleEntry:
    """字幕条目"""
    index: int
    start_time: str
    end_time: str
    source_text: str
    target_text: str = ""

    def __post_init__(self):
        # 只验证非空时间戳
        if self.start_time and self.end_time:
            for time_str in (self.start_time, self.end_time):
                if not TIME_PATTERN.match(time_str):
                    raise ValueError(f"无效的时间格式: {time_str}")

def parse_time(time_str: str, from_lrc: bool = False) -> str:
    """统一的时间格式转换"""
    if from_lrc:
        try:
            minutes, seconds = time_str.split(':')
            seconds, ms = seconds.split('.')
            return f"00:{int(minutes):02d}:{int(seconds):02d},{int(ms+'0'):03d}"
        except:
            return time_str
    return time_str

def format_time(time_str: str, to_lrc: bool = False) -> str:
    """统一的时间格式输出"""
    if to_lrc:
        try:
            h, m, s = time_str.split(':')
            s, ms = s.split(',')
            total_seconds = int(h) * 3600 + int(m) * 60 + int(s)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"[{minutes:02d}:{seconds:02d}.{ms[:2]}]"
        except:
            return time_str
    return time_str

def clean_text(text: str) -> str:
    """清理文本"""
    if not text:
        return ""
    text = text.strip()
    text = NUMBER_PREFIX_PATTERN.sub('', text)
    return text.strip('。，！？,.!?')

def parse_srt(file_path: str) -> List[SubtitleEntry]:
    """解析SRT字幕文件"""
    entries = []
    current_entry = None
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        lines = [line.strip() for line in f]
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            if current_entry and current_entry.source_text:
                entries.append(current_entry)
            current_entry = None
            i += 1
            continue
        
        if line.isdigit():
            current_entry = SubtitleEntry(
                index=int(line),
                start_time="",
                end_time="",
                source_text=""
            )
            i += 1
            continue
        
        if ' --> ' in line and current_entry:
            start, end = line.split(' --> ')
            current_entry.start_time = start.strip()
            current_entry.end_time = end.strip()
            i += 1
            continue
        
        if current_entry:
            text_lines = []
            while i < len(lines) and lines[i].strip() and not lines[i].isdigit() and ' --> ' not in lines[i]:
                text_lines.append(lines[i])
                i += 1
            current_entry.source_text = '\n'.join(text_lines)
        else:
            i += 1
    
    if current_entry and current_entry.source_text:
        entries.append(current_entry)
    
    return entries

def parse_lrcx(file_path: str) -> List[SubtitleEntry]:
    """解析LRCX歌词文件"""
    entries = []
    index = 1
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('[ver:') or line.startswith('[offset:') or '[tr:' in line:
                continue
                
            if line.startswith('['):
                try:
                    time_tag = line[1:line.find(']')]
                    text = line[line.find(']')+1:].strip()
                    
                    if text:
                        time_str = parse_time(time_tag, from_lrc=True)
                        entries.append(SubtitleEntry(
                            index=index,
                            start_time=time_str,
                            end_time=time_str,
                            source_text=text
                        ))
                        index += 1
                except Exception as e:
                    log_detail(f"解析LRCX行失败: {line} -> {str(e)}")
    
    return entries

async def translate_subtitles(
    entries: List[SubtitleEntry],
    translation_mode: str = "single",
    batch_size: int = 50,
    progress_file: Optional[Path] = None
) -> List[SubtitleEntry]:
    """翻译字幕条目"""
    total = len(entries)
    console.print(f"[info]开始翻译 {total} 条字幕[/info]")

    try:
        if translation_mode == "batch":
            batch_count = (total + batch_size - 1) // batch_size
            for i in range(0, total, batch_size):
                current_batch = i // batch_size + 1
                batch = entries[i:i+batch_size]
                console.print(f"[progress]▶ 翻译批次 {current_batch}/{batch_count} ({i+1}-{min(i+len(batch), total)}/{total})[/progress]")
                
                texts = [clean_text(e.source_text) for e in batch]
                translations = await translate_batch(texts)
                
                for entry, trans in zip(batch, translations):
                    entry.target_text = trans.strip()
        else:
            for i, entry in enumerate(entries, 1):
                console.print(f"[progress]▶ 翻译进度 {i}/{total}[/progress]", end="\r")
                clean_source = clean_text(entry.source_text)
                trans = await translate_single(clean_source)
                entry.target_text = trans.strip()
            console.print()
        
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
            f.write(f"{i}\n{entry.start_time} --> {entry.end_time}\n")
            f.write(f"{entry.target_text}\n")
            if not chinese_only:
                f.write(f"{entry.source_text}\n")
            f.write("\n")

def save_lrcx(entries: List[SubtitleEntry], output_path: str, chinese_only: bool = False) -> None:
    """保存为LRCX格式歌词文件"""
    if not entries:
        raise ValueError("没有可用的歌词条目")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[ver:1.0]\n[offset:0]\n")
        
        for entry in entries:
            if not entry.source_text.strip():
                continue
                
            time_tag = format_time(entry.start_time, to_lrc=True)
            source_text = clean_text(entry.source_text)
            target_text = clean_text(entry.target_text)
            
            f.write(f"{time_tag}{source_text}\n")
            if not chinese_only:
                f.write(f"{time_tag}[tr:zh-Hans]{target_text}\n")
