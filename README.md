# 声刻 · Media Scribe

音视频提取与转写工具。支持视频转音频、视频转文字、音频转文字；可导出 TXT、SRT 字幕及带时间轴的 JSON。

| 地址 | 状态 |
| --- | --- |
| GitHub 源码 | [github.com/xinxi2024/media-scribe](https://github.com/xinxi2024/media-scribe) |
| 公网网站 | **尚未上线**。免费服务的端到端速度尚未验证达到要求，验证后会在此填写真实网址。 |
| 开发预览 | [http://127.0.0.1:7860](http://127.0.0.1:7860)，仅在本机启动时可用，**不是公网地址**。 |

> 目标是把计算放在外网服务器，不消耗用户电脑的识别算力；同时保持免费，并尽量使上传、处理、下载的总耗时不慢于本地版。公网部署需要真实网络与账号环境的基准测试，当前尚不能保证这一点。

## 功能

- **视频转音频**：优先支持原音轨直接复制，速度快且不重新压缩；也可导出通用 MP3 或无损 FLAC。不适合直接封装的音轨会自动转成 FLAC。
- **视频/音频转文字**：开发版使用本机 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)；云端配置使用 [Groq Speech to Text](https://console.groq.com/docs/speech-to-text) 的 Whisper Large V3 Turbo 或 Large V3。视频转文字直接读取原始音轨，避免先压缩为 MP3 再识别。
- **提高可读性**：可指定语言、提示人名或术语，导出逐段 SRT。开启逐词时间戳后，JSON 还包含每个词的起止时间。
- **兼容性**：支持 MP4、MOV、MKV、WebM、AVI、M4V、MPEG、MPG、TS、M2TS、3GP、WMV 视频和 MP3、WAV、M4A、FLAC、OGG、AAC、WMA、Opus、AIFF、CAF 音频。识别视频需要视频含音轨；实际解码能力取决于 FFmpeg/PyAV 对文件内部编码的支持。
- **自适应长文件**：本地版在新版 faster-whisper 中对 60 秒以上文件批量识别；旧版自动回退到普通识别。云端版把长文件切成片段并用 FLAC 上传，避免免费接口的单次文件大小限制。

语音识别无法保证逐字正确。背景噪声、口音、多人重叠说话、专有名词与数字都应人工核对。专有名词提示也可能影响模型输出，请只填与录音有关的词。

## 界面设置

| 设置 | 开启或选择后的作用 | 关闭或替代选择后的作用 |
| --- | --- | --- |
| 处理任务 | 选择视频转音频、视频转文字或音频转文字 | 另外两项任务不执行 |
| 音频格式 | 原音轨：直接复制已有音频码流，不重新压缩 | MP3：更通用；FLAC：无损重编码，文件通常更大 |
| 速度与精度 | 本地 `tiny/base/small/medium`，云端 `Turbo/Large V3`；较大模型一般更准但可能更慢 | 可改选快速档，准确率可能下降 |
| 语音语言 | 指定中文、英文、日文或韩文，可减少误判及检测时间 | 自动检测，适合未知语言 |
| 专有名词提示 | 给模型词语的正确写法，可能减少专有词错误 | 不对识别结果施加词语提示 |
| 跳过静音（本地） | 开：减少静音段处理及无声幻觉 | 关：有助于保留很轻的语音，可能变慢 |
| 长文件批量加速（本地） | 开：60 秒以上自动批量处理，通常更快但更占内存 | 关：逐段处理，内存占用较低 |
| 逐词时间戳 | 开：JSON 包含逐词起止时间，处理会更慢 | 关：只保留逐段时间轴 |

点击“开始处理”后等待状态更新；“清空”会清除当前界面的文件和结果，不会删除已经下载的文件。服务器生成的临时结果只用于下载，勿把它当作长期备份。

## 云端架构与免费额度

仓库已提供 `Dockerfile` 和 `requirements-cloud.txt`。云端模式在服务器上用 FFmpeg 提取音轨，再将音频交给 Groq 识别；浏览器仅上传文件、显示和下载结果。`GROQ_API_KEY` 只从服务端环境变量读取，不会写入网页代码。公网启动还要求设置 `MEDIA_SCRIBE_PASSWORD`，供个人登录使用。

Groq 免费计划目前允许单次上传最多 **25 MB**，语音识别也有请求次数与音频时长限额；本站把音轨转成 16 kHz 单声道 FLAC、按约 5 分钟切分，片段过大时再压缩。云端处理意味着录音会交给 Groq，隐私敏感内容应先确认是否适合上传。[文件格式与限制](https://console.groq.com/docs/speech-to-text)、[免费计划速率限制](https://console.groq.com/docs/rate-limits)。

以下服务不应直接被视为“性能不弱于本地”的已验证方案：

- [Render 免费 Web Service](https://render.com/docs/free) 空闲约 15 分钟后休眠，下次请求约需一分钟唤醒；本地磁盘也是临时的。可作为功能试用，但冷启动会拉长总耗时。
- [Hugging Face Spaces](https://huggingface.co/docs/hub/spaces-gpus) 免费 CPU Basic 为 2 vCPU，不能据此保证胜过本机 i7-12700H；当前文档还说明新建运行计算的 Space 需要付费计划。
- [Netlify Functions](https://docs.netlify.com/build/functions/usage-and-billing/) 免费层有固定额度，默认函数内存为 1 GB，不适合直接在函数内装载本地 Whisper 模型。
- [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/platform/pricing/) 有每日免费推理额度，但免费 Worker 的 [CPU 时间限制](https://developers.cloudflare.com/workers/platform/pricing/) 不适合在请求里用 FFmpeg 做视频提取。

**部署门槛**：需要用同一个代表性音频、视频文件分别测本地与公网网站的“上传开始到下载完成”，包括冷启动和热启动；在实际免费额度内确认可用。网络上行速度与服务器所在地区会影响总耗时，因此无法对所有文件保证云端都比本地快。目前没有经过这个验证的公网网址。

仓库里的 `scripts/benchmark.py` 会测一次上传、处理、下载总耗时。部署后可分别运行 `python scripts/benchmark.py http://127.0.0.1:7860 样本.wav` 和 `python scripts/benchmark.py https://你的公网域名 样本.wav --model "快速 · Groq Turbo"` 对照。公网访问密码从 `MEDIA_SCRIBE_PASSWORD` 环境变量读取，不放在命令行里。

## 云端部署准备

可将本仓库的 Docker 镜像部署到支持容器的外网服务。环境变量：

| 名称 | 用途 |
| --- | --- |
| `MEDIA_SCRIBE_BACKEND=groq` | 云端转写后端 |
| `MEDIA_SCRIBE_HOST=0.0.0.0` | 监听容器网络 |
| `PORT=7860` | 服务端口，可由平台覆盖 |
| `GROQ_API_KEY` | Groq API 密钥，仅配置在托管平台的密钥设置中 |
| `MEDIA_SCRIBE_PASSWORD` | 个人访问密码，公网模式必须配置 |

部署前需要有相应托管平台账号和 Groq 账号，并在平台后台设置密钥；**不要把密钥提交到 GitHub**。容器默认使用云端模式。虽然可以在 Render 免费层启动，但它的冷启动不满足目前的性能门槛，本项目暂未将其标记为正式公网部署。

## 本地开发与验证

本地版本用于开发、测试和对照云端速度。需要 Python 3.10+；`imageio-ffmpeg` 自带可执行文件，不需另装 FFmpeg。

```powershell
git clone https://github.com/xinxi2024/media-scribe.git
cd media-scribe
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

macOS / Linux 用 `source .venv/bin/activate`。浏览器将打开 `http://127.0.0.1:7860`。关闭服务时在启动它的终端按 `Ctrl+C`。首次使用某个本地模型需要联网下载；生成文件位于被 Git 忽略的 `outputs/` 中，请按需要清理。

运行测试：

```powershell
python -m pip install pytest
python -m pytest -q
```

## 许可证

项目代码采用 [MIT License](LICENSE)。识别模型和第三方依赖遵循各自许可证。
