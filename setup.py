from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="whisper-translator-cn",
    version="0.1.0",
    author="Legibet",
    author_email="legibet@example.com",  # 建议添加作者邮箱
    description="视频字幕生成与翻译工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/legibet/whisper-translator-cn",
    project_urls={
        "Bug Tracker": "https://github.com/legibet/whisper-translator-cn/issues",
    },
    packages=find_packages(exclude=["tests*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "openai>=1.12.0",
        "rich>=13.7.0",
        "pyyaml>=6.0.1",
        "pydub>=0.25.1",
    ],
    extras_require={
        "faster-whisper": ["faster-whisper"],
        "dev": [
            "build>=1.0.0",
            "twine>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "whisper-translator-cn=whisper_translator.cli:run",
        ],
    },
    include_package_data=True,
    package_data={
        "whisper_translator": ["config.yaml.template"],
    },
    zip_safe=False,
)
