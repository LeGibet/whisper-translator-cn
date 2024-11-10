from dataclasses import dataclass
from typing import List
from pathlib import Path
import re
from .logger import logger, console
from .translate import translate_single, translate_batch

@dataclass
class SubtitleEntry:
    """字幕条目"""
    index: int
    start_time: str
    end_time: str
    source_text: str = ""
    target_text: str = ""

class TimeFormat:
    """时间格式处理"""
    @staticmethod
    def srt_to_lrc(time_str: str) -> str:
        """SRT时间格式转LRC时间标签"""
        try:
            h, m, s = time_str.split(':')
            s, ms = s.split(',')
            total_seconds = int(h) * 3600 + int(m) * 60 + int(s)
            return f"[{total_seconds//60:02d}:{total_seconds%60:02d}.{ms[:2]}]"
        except:
            logger.warning(f"时间格式转换失败: {time_str}")
            return time_str
    
    @staticmethod
    def lrc_to_srt(time_tag: str) -> str:
        """LRC时间标签转SRT时间格式"""
        try:
            time_str = time_tag.strip('[]')
            m, s = time_str.split(':')
            s, ms = s.split('.')
            total_seconds = int(m) * 60 + int(s)
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            s = total_seconds % 60
            return f"{h:02d}:{m:02d}:{s:02d},{ms.ljust(3, '0')}"
        except:
            logger.warning(f"时间格式转换失败: {time_tag}")
            return time_tag

def clean_text(text: str) -> str:
    """清理字幕文本"""
    if not text:
        return ""
    return re.sub(r'^\d+[.。,，、\s]*', '', text.strip())

def parse_srt(file_path: str) -> List[SubtitleEntry]:
    """解析SRT字幕文件"""
    entries = []
    current_entry = None
    text_lines = []
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            
            if not line:
                if current_entry and text_lines:
                    current_entry.source_text = '\n'.join(text_lines)
                    entries.append(current_entry)
                    current_entry = None
                    text_lines = []
                continue
            
            if line.isdigit():
                current_entry = SubtitleEntry(int(line), "", "")
                continue
                
            if current_entry and ' --> ' in line:
                start, end = line.split(' --> ')
                current_entry.start_time = start.strip()
                current_entry.end_time = end.strip()
                continue
                
            if current_entry:
                text_lines.append(line)
    
    # 处理最后一个条目
    if current_entry and text_lines:
        current_entry.source_text = '\n'.join(text_lines)
        entries.append(current_entry)
    
    return entries

def parse_lrcx(file_path: str) -> List[SubtitleEntry]:
    """解析LRCX歌词文件"""
    entries = []
    index = 1
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(('[ver:', '[offset:', '[tr:')):
                continue
            
            if line.startswith('['):
                try:
                    time_end = line.find(']')
                    if time_end == -1:
                        continue
                    
                    time_tag = line[1:time_end]
                    text = line[time_end+1:].strip()
                    
                    if text:
                        time_str = TimeFormat.lrc_to_srt(time_tag)
                        entries.append(SubtitleEntry(
                            index=index,
                            start_time=time_str,
                            end_time=time_str,
                            source_text=text
                        ))
                        index += 1
                except Exception as e:
                    logger.warning(f"解析LRCX行失败: {line} -> {str(e)}")
    
    return entries

async def translate_subtitles(
    entries: List[SubtitleEntry],
    translation_mode: str = "batch",
    batch_size: int = 50
) -> List[SubtitleEntry]:
    """翻译字幕"""
    total = len(entries)
    console.print(f"[info]开始翻译 {total} 条字幕[/info]")
    
    try:
        if translation_mode == "batch":
            # 批量翻译
            texts = [clean_text(e.source_text) for e in entries]
            translations = await translate_batch(texts, batch_size=batch_size)
            
            for entry, trans in zip(entries, translations):
                entry.target_text = trans
        else:
            # 单条翻译
            for i, entry in enumerate(entries, 1):
                console.print(f"[progress]▶ 翻译进度 {i}/{total}[/progress]", end="\r")
                entry.target_text = await translate_single(clean_text(entry.source_text))
            console.print()
            
        console.print("[success]✓ 翻译完成[/success]")
        return entries
        
    except Exception as e:
        logger.error(f"翻译过程发生错误: {str(e)}")
        raise

def save_subtitle(
    entries: List[SubtitleEntry],
    output_path: str,
    chinese_only: bool = False,
    format_type: str = "srt"
) -> None:
    """保存字幕文件"""
    if not entries:
        raise ValueError("没有可用的字幕条目")
    
    output_path = Path(output_path)
    
    if format_type.lower() == "lrcx":
        output_path = output_path.with_suffix('.lrcx')
        save_lrcx(entries, output_path, chinese_only)
    else:
        save_srt(entries, output_path, chinese_only)

def save_srt(entries: List[SubtitleEntry], output_path: Path, chinese_only: bool) -> None:
    """保存SRT格式字幕"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(entries, 1):
            f.write(f"{i}\n{entry.start_time} --> {entry.end_time}\n")
            if entry.target_text:
                f.write(f"{entry.target_text}\n")
            if not chinese_only and entry.source_text:
                f.write(f"{entry.source_text}\n")
            f.write("\n")

def save_lrcx(entries: List[SubtitleEntry], output_path: Path, chinese_only: bool) -> None:
    """保存LRCX格式字幕"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("[ver:1.0]\n[offset:0]\n")
        
        for entry in entries:
            if not entry.source_text.strip():
                continue
            
            time_tag = TimeFormat.srt_to_lrc(entry.start_time)
            source_text = clean_text(entry.source_text)
            target_text = clean_text(entry.target_text)
            
            f.write(f"{time_tag}{source_text}\n")
            if not chinese_only and target_text:
                f.write(f"{time_tag}[tr:zh-Hans]{target_text}\n")
