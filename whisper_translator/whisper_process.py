import asyncio
import contextlib
import tempfile
import re
from pathlib import Path
from typing import Tuple
from pydub import AudioSegment
from faster_whisper import WhisperModel
from .logger import get_logger, console, log_detail

class WhisperProcessError(Exception):
    """Whisper处理错误"""
    pass

@contextlib.contextmanager
def temp_wav_file(output_dir: Path):
    """临时WAV文件管理器"""
    temp_path = output_dir / f"temp_{next(tempfile._get_candidate_names())}.wav"
    try:
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)
        log_detail("已清理临时WAV文件")

async def convert_to_wav(input_path: Path, wav_path: Path) -> None:
    """将输入音频转换为WAV格式"""
    log_detail(f"开始音频格式转换: {input_path} -> {wav_path}")
    try:
        audio = await asyncio.to_thread(
            AudioSegment.from_file, 
            input_path, 
            format=input_path.suffix[1:]
        )
        
        audio = audio.set_frame_rate(16000).set_channels(1)
        
        await asyncio.to_thread(
            audio.export,
            wav_path,
            format="wav",
            parameters=["-c:a", "pcm_s16le"]
        )
        log_detail("音频转换成功")
        
    except Exception as e:
        raise WhisperProcessError(f"音频转换失败: {str(e)}")

async def process_whisper_cpp(input_path: Path, output_dir: Path, config: dict) -> Tuple[Path, str]:
    """使用 whisper.cpp 处理音频文件"""
    cpp_config = config["whisper_cpp"]
    whisper_path = Path(cpp_config["binary_path"])
    model_path = Path(cpp_config["model_path"])
    
    console.print(f"[info]使用模型: {model_path.name}[/info]")
    log_detail(f"Whisper.cpp配置: 程序={whisper_path}, 模型={model_path}")
    
    if not whisper_path.exists() or not model_path.exists():
        raise WhisperProcessError(f"程序或模型文件不存在")

    with temp_wav_file(output_dir) as wav_path:
        await convert_to_wav(input_path, wav_path)
        
        cmd = [
            str(whisper_path / "main"),
            "-m", str(model_path),
            "-f", str(wav_path.absolute()),
            "-osrt",
            "-of", wav_path.stem,
            "-l", "auto",
            "-bs", "8",
            "-bo", "8",
        ]
        log_detail(f"执行命令: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=output_dir
        )
        stdout, stderr = await process.communicate()
        
        expected_output = output_dir / f"{wav_path.stem}.srt"
        if not expected_output.exists():
            error_msg = stderr.decode() if stderr else "未知错误"
            raise WhisperProcessError(f"Whisper.cpp执行失败: {error_msg}")
        
        if stdout:
            log_detail(f"程序输出:\n{stdout.decode()}")
            
        stderr_text = stderr.decode() if stderr else ""
        if stderr_text:
            for line in stderr_text.splitlines():
                if any(x in line.lower() for x in ['error', 'exception', 'failed']):
                    log_detail(f"错误: {line}")
                else:
                    log_detail(f"状态: {line}")
        
        detected_lang = "auto"
        lang_match = re.search(r"auto-detected language: (\w+)", stderr_text)
        if lang_match:
            detected_lang = lang_match.group(1)
            
        final_output = output_dir / f"{input_path.stem}.srt"
        expected_output.rename(final_output)
        
        return final_output, detected_lang

async def process_faster_whisper(input_path: Path, output_dir: Path, config: dict) -> Tuple[Path, str]:
    """使用 faster-whisper 处理音频文件"""
    fw_config = config["faster_whisper"]
    
    log_detail(f"Faster Whisper配置: 模型={fw_config['model']}, 计算类型={fw_config.get('compute_type', 'float16')}")
    console.print(f"[info]使用模型: {fw_config['model']}[/info]")
    
    model = WhisperModel(
        model_size_or_path=fw_config["model"], 
        device="auto",
        compute_type=fw_config.get("compute_type", "float16"),
        cpu_threads=fw_config.get("cpu_threads", 4),
    )
    
    segments, info = await asyncio.to_thread(
        model.transcribe, 
        str(input_path),
        language=None,
        task="transcribe"
    )
    
    output_srt = output_dir / f"{input_path.stem}.srt"
    with open(output_srt, "w", encoding="utf-8") as srt_file:
        for i, segment in enumerate(segments, start=1):
            start = f"{int(segment.start // 3600):02d}:{int(segment.start % 3600 // 60):02d}:{int(segment.start % 60):02d},{int(segment.start * 1000 % 1000):03d}"
            end = f"{int(segment.end // 3600):02d}:{int(segment.end % 3600 // 60):02d}:{int(segment.end % 60):02d},{int(segment.end * 1000 % 1000):03d}"
            
            srt_file.write(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n\n")
            log_detail(f"转写段落 {i}: {segment.text.strip()}")
    
    log_detail(f"检测到语言: {info.language}")
    return output_srt, info.language

async def process_media(input_path: Path, output_dir: Path, config: dict) -> Tuple[Path, str]:
    """处理媒体文件，返回(字幕路径, 检测到的语言)"""
    output_dir.mkdir(exist_ok=True)
    
    try:
        process_func = process_whisper_cpp if config["engine"] == "whisper-cpp" else process_faster_whisper
        return await process_func(input_path, output_dir, config)
    except Exception as e:
        if not isinstance(e, WhisperProcessError):
            e = WhisperProcessError(str(e))
        raise e
