# Whisper Translator CN
一个基于 Whisper 和 OpenAI API 的音视频字幕/歌词生成与中文翻译工具。(自用小工具，代码和文档使用了AI润色。参考了[subtitle-translator](https://github.com/fanxing333/subtitle-translator)。)

> 可以在 `python-package` 分支查看Python包版本，支持通过pip安装使用。

## 功能特性

- 生成视频字幕 (输出 SRT 格式)
- 生成音频歌词 (输出 LRCX 格式)
- 翻译字幕 (基于 OpenAI API)
- 支持翻译已有的字幕文件（.srt）和歌词文件（.lrc/.lrcx）
- 默认采用逐条翻译，支持批量翻译
- 默认输出双语字幕，支持输出纯中文字幕

## 环境配置

### 基础环境

- Python 3.8+
- ffmpeg （可选，用于 whisper.cpp 音频预处理）
- whisper.cpp / faster-whisper（可选，仅生成字幕/歌词时需要）

### 安装步骤

#### 克隆项目并安装依赖

```bash
git clone https://github.com/LeGibet/whisper-translator-cn.git
cd whisper-translator-cn
# 安装依赖
pip install -r requirements.txt
# 复制配置模板
cp config.yaml.template config.yaml
```

#### 配置 whisper

> 可选，仅生成视频字幕/音频歌词时需要

支持两种引擎，选择其一即可：

1. **whisper.cpp** （Mac上运行更快）
  参考 [whisper.cpp](https://github.com/ggerganov/whisper.cpp) 完成配置，在 `config.yaml` 中填入路径

2. **faster-whisper** （无需额外配置）
  在 `config.yaml` 中填入模型名称，首次使用会自动下载。具体参考 [faster-whisper](https://github.com/SYSTRAN/faster-whisper.git)

```yaml
# config.yaml
whisper:
  engine: "faster-whisper"  # "whisper-cpp" 或 "faster-whisper"

  whisper_cpp:
    binary_path: "/path/to/whisper.cpp"     # whisper.cpp 路径
    model_path: "/path/to/models/model.bin"  # 模型文件路径

  faster_whisper:
    model: "base"          # 模型名称
    compute_type: "float16"   # 可选: float32, float16, int8
```

#### 配置 OpenAI API

> 用于翻译字幕

在 `config.yaml` 中配置：

```yaml
# config.yaml
api_key: "your-api-key"
api_base: "https://api.openai.com/v1"
model: "gpt-4o-mini"
```

API密钥支持两种配置方式（按优先级排序）：

1. 环境变量（推荐）：

```bash
export OPENAI_API_KEY=<你的密钥>
```

2. 配置文件 `config.yaml`

## 使用示例

### 基础用法

```bash
# 一键生成并翻译字幕
python main.py video.mp4

# 仅生成字幕（不翻译）
python main.py video.mp4 --mode subtitle

# 仅翻译已有的 SRT 字幕 / LRCX 歌词（不需要配置 whisper）
python main.py subtitle.srt --mode translate
```

### 进阶用法

```bash
# 批量翻译模式（默认batch-size=50）
python main.py video.mp4 --trans-mode batch --batch-size 80

# 生成纯中文字幕
python main.py video.mp4 --chinese-only

# 自定义输出路径
python main.py video.mp4 -o custom_output.srt

# 自定义输出格式（支持srt字幕和lrcx歌词）
python main.py video.mp4 --format srt
```

## 参数说明

| 参数 | 简写 | 说明 | 默认值 | 示例 |
|------|------|------|--------|------|
| --output | -o | 输出路径 | auto | output.srt |
| --mode | -m | 处理模式 | all | translate |
| --trans-mode | -t | 翻译模式 | single | batch |
| --batch-size | -b | 批量大小 | 50 | 100 |
| --chinese-only | -c | 仅中文 | False | - |
| --log-file | -l | 启用日志文件 | False | - |
| --format | -f | 输出格式 | auto | srt/lrcx |

## 翻译模式对比

### 逐条翻译 (Single Mode)

- ✅ 翻译输出稳定
- ❌ 缺乏上下文
- ❌ API调用频繁

### 批量翻译 (Batch Mode)

- ✅ 理解上下文
- ✅ 总token消耗一般更少
- ✅ 翻译更快
- ❌ 需要更大上下文窗口（可选择减小batch-size）
- ❌ 翻译输出不稳定，有可能出现翻译与原文不对应的情况

## 注意事项

Whisper 生成的字幕可能存在错误或幻觉，建议自行检查并校正字幕内容
