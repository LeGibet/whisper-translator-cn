from setuptools import setup, find_packages

setup(
    name="whisper_translator_cn",
    version="0.1.0",
    description="视频字幕生成与翻译工具",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        "openai>=1.12.0",
        "rich>=13.7.0",
        "pyyaml>=6.0.1",
        "pydub>=0.25.1",
    ],
    extras_require={
        "faster-whisper": ["faster-whisper"],
    },
    entry_points={
        "console_scripts": [
            "whisper-translator-cn=whisper_translator_cn.cli:run",
        ],
    },
    package_data={
        "whisper_translator_cn": ["config.yaml.template"],
    },
)
