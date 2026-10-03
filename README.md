# 声刻 · Media Scribe

一个在本机运行的音视频转文字小工具。上传文件，选择处理方式，即可提取 MP3 或生成带时间轴的转写结果。

## 功能

- **视频转音频**：从视频音轨提取高质量 MP3。
- **视频转文字 / 音频转文字**：使用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 在本机识别语音。
- **四种速度与精度档位**：`tiny`（极速）、`base`（快速，默认）、`small`（均衡）、`medium`（较准确）；可自动检测语言，也可指定中文、英文、日文或韩文。
- **多格式导出**：纯文本 TXT、可直接使用的 SRT 字幕、带起止时间的 JSON。
- **本地优先**：界面仅监听 `127.0.0.1`。上传的文件不会发送到云端；首次使用某个模型时，需要联网下载模型文件。

> 语音识别无法保证逐字准确。背景噪声、口音、多人重叠说话以及专有名词会影响结果，请人工核对重要内容。

## 快速开始

需要 Python 3.10 或更新版本。音频提取所需的 FFmpeg 由 `imageio-ffmpeg` 提供，无需单独安装系统 FFmpeg。

```powershell
git clone https://github.com/xinxi2024/media-scribe.git
cd media-scribe
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

macOS / Linux 使用 `source .venv/bin/activate` 激活虚拟环境。未使用 Git 时，也可直接下载仓库 ZIP 后在解压目录中执行后四步。浏览器将自动打开本地界面；如果没有打开，请访问 `http://127.0.0.1:7860`。

## 使用方法

1. 上传视频或音频文件。
2. 选择“视频转音频”“视频转文字”或“音频转文字”。
3. 如需转写，可选择精度和语言；中文内容建议明确选择“中文”。
4. 点击“开始处理”，完成后预览文字并下载生成的文件。

支持视频：MP4、MOV、MKV、WebM、AVI、M4V；支持音频：MP3、WAV、M4A、FLAC、OGG、AAC、WMA。视频必须包含音轨。转写仅识别音轨中的语音，不识别画面文字或已有字幕。

默认的 `base` 适合日常用途。赶时间时可选 `tiny`，但错字可能明显增加；对准确率要求更高时可选 `small` 或 `medium`。“极速”和“快速”档关闭耗时的低置信度重试，“均衡”和“准确”档保留重试以争取更好的识别结果。程序在 CPU 上使用 int8 推理和最多 8 个线程，超过 60 秒的文件会自动批量识别，以加快较长录音的处理；批量识别会占用更多内存。知道语音语言时建议手动指定，以避免自动检测耗时。

当前版本使用 CPU，不要求 NVIDIA 显卡。即使电脑有独立显卡，也只有配置了与 faster-whisper 兼容的 CUDA 运行库后才能使用 GPU；目前界面暂不提供 GPU 模式。若使用旧版 faster-whisper，长文件会自动改用普通转写；按上面的安装步骤更新依赖后才能使用批量加速。

生成文件保存在项目目录的 `outputs/` 中，此目录已被 Git 忽略。请自行清理不再需要的结果，尤其是包含隐私信息的文件。模型文件由 faster-whisper 下载到本机缓存。

## 开发与测试

```powershell
python -m pip install pytest
python -m pytest -q
```

## 许可证

本项目以 [MIT License](LICENSE) 发布。语音识别模型及第三方依赖分别遵循其自身许可证。
