# Whisper Translator CN

一个视频字幕生成与翻译工具，支持将视频或音频文件转换为字幕，并将字幕翻译为中文。

## 功能特点

- 支持多种视频和音频格式转换为字幕
- 支持使用 OpenAI API 进行准确的翻译
- 支持批量翻译模式，提高效率
- 支持 SRT 和 LRCX 格式的字幕/歌词文件
- 支持 Faster Whisper 和 Whisper.cpp 两种语音识别引擎
- 提供命令行和 Python API 两种使用方式

## 安装

```bash
# 基础安装
pip install .

# 如果需要使用 faster-whisper 引擎
pip install ".[faster-whisper]"
```

## 快速开始

1. 初始化配置文件：
```bash
wtrans init
```

2. 编辑配置文件：
配置文件位于 `~/.config/whisper_translator/config.yaml`，需要设置：
- OpenAI API密钥和基础URL
- 翻译模型和相关参数
- Whisper引擎配置

你可以通过环境变量覆盖一些配置：
- `WHISPER_TRANSLATOR_CONFIG`: 自定义配置文件路径
- `OPENAI_API_KEY`: OpenAI API密钥
- `OPENAI_API_BASE`: OpenAI API基础URL

3. 使用命令行工具：

```bash
# 处理视频/音频文件（生成字幕并翻译）
wtrans run video.mp4

# 指定输出文件
wtrans run video.mp4 -o output.srt

# 仅生成字幕不翻译
wtrans run video.mp4 -m subtitle

# 翻译已有字幕文件
wtrans run subtitle.srt -m translate

# 批量翻译模式
wtrans run video.mp4 -t batch -b 50

# 仅输出中文字幕
wtrans run video.mp4 -c

# 指定输出格式（auto/srt/lrcx）
wtrans run audio.mp3 -f lrcx

# 启用日志文件
wtrans run video.mp4 -l
```

4. 作为Python包使用：

```python
from whisper_translator import process_file, init_config

# 初始化配置（如果还没有配置文件）
config_path = init_config()

# 在配置文件中填入相关配置

# 处理文件
await process_file(
    input_path="video.mp4",
    output="output.srt",
    mode="all",              # "all", "subtitle", "translate"
    translation_mode="batch", # "single" 或 "batch"
    batch_size=50,           # 批量翻译时的批次大小
    chinese_only=False,      # 是否仅输出中文
    format="auto"            # "auto", "srt", "lrcx"
)
```

## 使用建议

1. 对于较长的视频，建议使用批量翻译模式（-t batch）
2. 使用 `wtrans run -h` 查看所有可用选项
3. Whisper 生成的字幕可能存在错误或幻觉，建议自行检查并校正字幕内容

## 许可证

MIT License
