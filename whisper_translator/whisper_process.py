import asyncio
from pathlib import Path
from typing import Tuple
from pydub import AudioSegment
from faster_whisper import WhisperModel
from .logger import logger, console, log_subprocess
import re

async def convert_to_wav(input_path: Path, output_dir: Path) -> Path:
    """将输入音频转换为WAV格式"""
    wav_path = output_dir / f"{input_path.stem}.wav"
    
    try:
        audio = await asyncio.to_thread(
            AudioSegment.from_file, 
            input_path, 
            format=input_path.suffix[1:]
        )
        
        await asyncio.to_thread(
            audio.set_frame_rate(16000).set_channels(1).export,
            wav_path,
            format="wav",
            parameters=["-c:a", "pcm_s16le"]
        )
        return wav_path
        
    except Exception as e:
        if wav_path.exists():
            wav_path.unlink()
        raise RuntimeError(f"音频转换失败: {str(e)}")

def format_timestamp(seconds: float) -> str:
    """格式化时间戳为SRT格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds * 1000) % 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"

async def run_whisper_cpp(
    wav_path: Path,
    output_dir: Path,
    binary_path: Path,
    model_path: Path
) -> Tuple[Path, str]:
    """运行whisper.cpp引擎"""
    # 获取whisper.cpp目录和main执行文件路径
    whisper_dir = binary_path
    main_executable = whisper_dir / "main"

    # 验证路径
    if not whisper_dir.exists():
        raise FileNotFoundError(f"whisper.cpp目录不存在: {whisper_dir}")
    if not main_executable.exists():
        raise FileNotFoundError(f"whisper.cpp执行文件不存在: {main_executable}")
    if not model_path.exists():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")
    
    # 设置命令
    cmd = [
        str(main_executable),
        "-m", str(model_path),
        "-f", str(wav_path.absolute()),
        "-osrt",
        "-of", wav_path.stem,
        "-l", "auto",
        "-bs", "8",
        "-bo", "8",
    ]
    
    # 执行命令
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=output_dir
    )
    stdout, stderr = await process.communicate()
    
    # 记录输出到日志
    if stdout:
        log_subprocess(stdout)
    if stderr:
        log_subprocess(stderr)
    
    # 检查输出
    expected_output = output_dir / f"{wav_path.stem}.srt"
    if not expected_output.exists():
        error_msg = stderr.decode() if stderr else "未知错误"
        raise RuntimeError(f"Whisper.cpp执行失败: {error_msg}")
    
    # 提取检测到的语言
    stderr_text = stderr.decode() if stderr else ""
    lang_match = re.search(r"auto-detected language: (\w+)", stderr_text)
    detected_lang = lang_match.group(1) if lang_match else "auto"
    
    return expected_output, detected_lang

async def run_faster_whisper(
    input_path: Path,
    output_dir: Path,
    model_config: dict
) -> Tuple[Path, str]:
    """运行faster-whisper引擎"""
    # 初始化模型
    model = WhisperModel(
        model_size_or_path=model_config["model"],
        device="auto",
        compute_type=model_config.get("compute_type", "float16"),
        cpu_threads=model_config.get("cpu_threads", 4)
    )
    
    # 转写音频
    segments, info = await asyncio.to_thread(
        model.transcribe,
        str(input_path),
        language=None,
        task="transcribe",
        callback=lambda progress: logger.debug(f"转录进度: {progress:.1%}")
    )
    
    # 生成SRT文件
    output_srt = output_dir / f"{input_path.stem}.srt"
    with open(output_srt, "w", encoding="utf-8") as srt:
        for i, segment in enumerate(segments, start=1):
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            text = segment.text.strip()
            content = f"{i}\n{start} --> {end}\n{text}\n\n"
            srt.write(content)
            logger.debug(content.rstrip())
    
    return output_srt, info.language

async def process_media(input_path: Path, output_dir: Path, config: dict) -> Tuple[Path, str]:
    """处理媒体文件，返回(字幕路径, 检测到的语言)"""
    output_dir.mkdir(exist_ok=True)
    
    try:
        # 音频预处理
        if config["engine"] == "whisper-cpp":
            wav_path = await convert_to_wav(input_path, output_dir)
            try:
                # 运行whisper.cpp
                console.print(f"[info]使用模型: {Path(config['whisper_cpp']['model_path']).name}[/info]")
                return await run_whisper_cpp(
                    wav_path,
                    output_dir,
                    Path(config["whisper_cpp"]["binary_path"]),
                    Path(config["whisper_cpp"]["model_path"])
                )
            finally:
                # 清理临时文件
                if wav_path.exists():
                    wav_path.unlink()
        else:
            # 运行faster-whisper
            console.print(f"[info]使用模型: {config['faster_whisper']['model']}[/info]")
            return await run_faster_whisper(
                input_path,
                output_dir,
                config["faster_whisper"]
            )
    
    except Exception as e:
        logger.error(str(e))
        raise
