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
whisper-translator-cn init
```

2. 编辑配置文件：
配置文件位于 `~/.config/whisper-translator-cn/config.yaml`，需要设置：
- OpenAI API密钥和基础URL
- 翻译模型和相关参数
- Whisper引擎配置

你可以通过环境变量覆盖一些配置：
- `WHISPER_TRANSLATOR_CN_CONFIG`: 自定义配置文件路径
- `OPENAI_API_KEY`: OpenAI API密钥
- `OPENAI_API_BASE`: OpenAI API基础URL

3. 使用命令行工具：

```bash
# 处理视频/音频文件（生成字幕并翻译）
whisper-translator-cn run video.mp4

# 指定输出文件
whisper-translator-cn run video.mp4 -o output.srt

# 仅生成字幕不翻译
whisper-translator-cn run video.mp4 -m subtitle

# 翻译已有字幕文件
whisper-translator-cn run subtitle.srt -m translate

# 批量翻译模式
whisper-translator-cn run video.mp4 -t batch -b 50

# 仅输出中文字幕
whisper-translator-cn run video.mp4 -c

# 指定输出格式（auto/srt/lrcx）
whisper-translator-cn run audio.mp3 -f lrcx

# 启用日志文件
whisper-translator-cn run video.mp4 -l
```

4. 作为Python包使用：

```python
from whisper_translator import process_file, init_config

# 初始化配置（如果还没有配置文件）
config_path = init_config()

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

## 配置文件说明

配置文件采用YAML格式，主要包含以下部分：

```yaml
# OpenAI API配置
api_key: "your-api-key"
api_base: "https://api.openai.com/v1"
model: "gpt-4o-mini"

# 翻译相关配置
translation:
  temperature: 0.3
  max_retries: 3
  retry_delay: 1
  prompts:
    single: "将以下文本翻译为中文："
    batch: "将以下编号文本翻译为中文，保持相同的编号格式："

# Whisper引擎配置
whisper:
  # 选择使用的引擎: "faster-whisper" 或 "whisper-cpp"
  engine: "faster-whisper"
  
  # Faster Whisper配置
  faster_whisper:
    model: "large-v3"
    compute_type: "float16"
    cpu_threads: 4
  
  # Whisper.cpp配置
  whisper_cpp:
    binary_path: "/path/to/whisper.cpp"
    model_path: "/path/to/model.bin"
```

## 使用建议

1. 为获得最好的识别效果，建议使用清晰的音频输入
2. 对于较长的视频，建议使用批量翻译模式（-t batch）
3. 使用 `whisper-translator-cn run -h` 查看所有可用选项
4. Whisper 生成的字幕可能存在错误或幻觉，建议自行检查并校正字幕内容

## 许可证

MIT License
