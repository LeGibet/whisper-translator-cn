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
        if temp_path.exists():
            temp_path.unlink()
            log_detail("已删除临时WAV文件")

async def convert_to_wav(input_path: Path, wav_path: Path) -> None:
    """将输入音频转换为WAV格式"""
    logger = get_logger()
    log_detail("开始音频格式转换...")
    log_detail(f"源文件: {input_path}")
    log_detail(f"目标文件: {wav_path}")
    
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

def validate_paths(input_path: Path, output_dir: Path) -> None:
    """验证输入输出路径"""
    errors = []
    
    if not input_path.exists():
        errors.append(f"输入文件不存在: {input_path}")
    if not input_path.is_file():
        errors.append(f"输入路径不是文件: {input_path}")
        
    try:
        output_dir.mkdir(exist_ok=True, parents=True)
    except Exception as e:
        errors.append(f"无法创建输出目录 {output_dir}: {str(e)}")
        
    if errors:
        raise WhisperProcessError("\n".join(errors))

async def process_whisper_cpp(input_path: Path, output_dir: Path, config: dict) -> Tuple[Path, str]:
    """使用 whisper.cpp 处理音频文件"""
    logger = get_logger()
    try:
        validate_paths(input_path, output_dir)
        log_detail("验证路径完成")
        
        # 检查 whisper.cpp 相关路径
        cpp_config = config["whisper_cpp"]
        whisper_path = Path(cpp_config["binary_path"])
        model_path = Path(cpp_config["model_path"])
        
        console.print(f"[info]使用模型: {model_path.name}[/info]")
        
        log_detail(f"Whisper.cpp 配置:")
        log_detail(f"- 程序路径: {whisper_path}")
        log_detail(f"- 模型路径: {model_path}")
        
        for path, desc in [(whisper_path, "whisper.cpp"), (model_path, "模型文件")]:
            if not path.exists():
                raise WhisperProcessError(f"{desc}不存在: {path}")

        with temp_wav_file(output_dir) as wav_path:
            await convert_to_wav(input_path, wav_path)
            
            # 设置命令
            cmd = [
                str(whisper_path / "main"),
                "-m", str(model_path),
                "-f", str(wav_path.absolute()),
                "-osrt",  # 启用 srt 输出
                "-of", wav_path.stem,  # 只提供基本文件名
                "-l", "auto",
                "-bs", "8",
                "-bo", "8",
            ]
            log_detail(f"执行命令: {' '.join(cmd)}")
            
            # 在输出目录中执行命令
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=output_dir
            )
            stdout, stderr = await process.communicate()
            
            # 检查输出文件
            expected_output = output_dir / f"{wav_path.stem}.srt"
            if not expected_output.exists():
                error_msg = stderr.decode() if stderr else "未知错误"
                raise WhisperProcessError(f"Whisper.cpp 执行失败: {error_msg}")
            
            # 记录输出
            if stdout:
                log_detail(f"Whisper.cpp 输出:\n{stdout.decode()}")
            if stderr:
                stderr_text = stderr.decode()
                # 过滤出真正的错误信息
                error_lines = []
                info_lines = []
                for line in stderr_text.splitlines():
                    if any(x in line.lower() for x in ['error', 'exception', 'failed']):
                        error_lines.append(line)
                    else:
                        info_lines.append(line)
                if info_lines:
                    log_detail("Whisper.cpp 状态信息:\n" + "\n".join(info_lines))
                if error_lines:
                    log_detail("Whisper.cpp 错误信息:\n" + "\n".join(error_lines))
            
            # 从输出中提取检测到的语言
            detected_lang = "auto"
            stderr_text = stderr.decode() if stderr else ""
            lang_match = re.search(r"auto-detected language: (\w+)", stderr_text)
            if lang_match:
                detected_lang = lang_match.group(1)
                
            # 重命名输出文件
            final_output = output_dir / f"{input_path.stem}.srt"
            expected_output.rename(final_output)
            
            return final_output, detected_lang
        
    except Exception as e:
        if isinstance(e, WhisperProcessError):
            raise
        raise WhisperProcessError(f"WhisperCpp处理失败: {str(e)}")

async def process_faster_whisper(input_path: Path, output_dir: Path, config: dict) -> Tuple[Path, str]:
    """使用 faster-whisper 处理音频文件"""
    logger = get_logger()
    try:
        validate_paths(input_path, output_dir)
        
        fw_config = config["faster_whisper"]
        
        log_detail(f"Faster Whisper 配置:")
        log_detail(f"- 模型: {fw_config['model']}")
        log_detail(f"- 计算类型: {fw_config['compute_type']}")
        
        console.print(f"[info]使用模型: {fw_config['model']}[/info]")
        
        # 初始化模型
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
        
        # 生成 SRT 文件
        output_srt = output_dir / f"{input_path.stem}.srt"
        with open(output_srt, "w", encoding="utf-8") as srt_file:
            for i, segment in enumerate(segments, start=1):
                # 格式化时间戳
                start = f"{int(segment.start // 3600):02d}:{int(segment.start % 3600 // 60):02d}:{int(segment.start % 60):02d},{int(segment.start * 1000 % 1000):03d}"
                end = f"{int(segment.end // 3600):02d}:{int(segment.end % 3600 // 60):02d}:{int(segment.end % 60):02d},{int(segment.end * 1000 % 1000):03d}"
                
                srt_file.write(f"{i}\n{start} --> {end}\n{segment.text.strip()}\n\n")
                log_detail(f"转写段落 {i}: {segment.text.strip()}")
        
        log_detail(f"检测到语言: {info.language}")
        return output_srt, info.language
        
    except Exception as e:
        if isinstance(e, WhisperProcessError):
            raise
        raise WhisperProcessError(f"FasterWhisper处理失败: {str(e)}")

async def process_media(input_path: Path, output_dir: Path, config: dict) -> Tuple[Path, str]:
    """处理媒体文件，返回(字幕路径, 检测到的语言)"""
    output_dir.mkdir(exist_ok=True)
    
    try:
        if config["engine"] == "whisper-cpp":
            return await process_whisper_cpp(input_path, output_dir, config)
        else:
            return await process_faster_whisper(input_path, output_dir, config)
    except Exception as e:
        if not isinstance(e, WhisperProcessError):
            e = WhisperProcessError(str(e))
        raise e
