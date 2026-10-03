"""Gradio interface for Media Scribe."""

from __future__ import annotations

import os

import gradio as gr

from media_scribe import (AUDIO_EXPORTS, AUDIO_EXTENSIONS, CLOUD_MODELS,
                          LANGUAGES, MODELS, VIDEO_EXTENSIONS, process)

BACKEND = os.getenv("MEDIA_SCRIBE_BACKEND", "local").lower()
if BACKEND not in {"local", "groq"}:
    raise RuntimeError("MEDIA_SCRIBE_BACKEND must be 'local' or 'groq'.")
ACTIVE_MODELS = CLOUD_MODELS if BACKEND == "groq" else MODELS
DEFAULT_MODEL = next(iter(ACTIVE_MODELS)) if BACKEND == "groq" else "快速 · base"

CSS = """
.gradio-container {max-width: 1100px !important; margin: 0 auto !important; padding: 1rem !important;}
.app-hero {padding: 2.2rem 1.5rem 1.4rem; border-radius: 24px;
  background: linear-gradient(125deg, #18234c 0%, #3455af 55%, #7b6ad9 100%);
  color: white; margin-bottom: 1.2rem; box-shadow: 0 14px 30px rgba(36,56,120,.15);}
.app-hero .eyebrow {font-size: .75rem; letter-spacing: .18em; opacity: .75; font-weight: 700;}
.app-hero h1 {font-size: clamp(2rem, 5vw, 3.2rem); line-height: 1.12; margin: .55rem 0; color: white;}
.app-hero p {font-size: 1rem; opacity: .9; margin: 0;}
.steps {display: flex; flex-wrap: wrap; gap: .55rem; margin-top: 1.3rem;}
.steps span {background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.25);
  border-radius: 999px; padding: .4rem .8rem; font-size: .85rem;}
.panel {border: 1px solid #e5eaf5; border-radius: 20px; padding: 1rem;
  background: var(--block-background-fill); box-shadow: 0 8px 24px rgba(37,54,94,.06);}
.panel-title {font-weight: 700; font-size: 1.1rem; margin: .1rem 0 .8rem;}
.footer-note {text-align: center; font-size: .82rem; color: #64748b; margin: 1.3rem 0;}
@media (max-width: 760px) {
  .gradio-container {padding: .5rem !important;}
  .app-hero {padding: 1.5rem 1.1rem; border-radius: 18px;}
  .panel {padding: .7rem; border-radius: 16px;}
}
"""


def run(file_path, mode, audio_export, model, language, terms,
        vad_filter, batch_long, word_timestamps, progress=gr.Progress()):
    try:
        return process(
            file_path, mode, model, language,
            lambda message: progress(None, desc=message),
            audio_export=audio_export, vad_filter=vad_filter,
            batch_long=batch_long, word_timestamps=word_timestamps,
            terms=terms, backend=BACKEND,
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc


with gr.Blocks(title="声刻 · 音视频转文字", css=CSS,
               theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate")) as demo:
    gr.HTML("""<div class="app-hero">
      <div class="eyebrow">MEDIA SCRIBE · 声刻</div>
      <h1>把声音，变成可用的文字</h1>
      <p>提取音轨、生成逐段字幕与文字稿，设置清晰，结果可直接下载。</p>
      <div class="steps"><span>① 上传文件</span><span>② 选择任务</span><span>③ 下载结果</span></div>
    </div>""")
    with gr.Row(equal_height=False):
        with gr.Column(scale=1, min_width=320, elem_classes="panel"):
            gr.HTML('<div class="panel-title">开始处理</div>')
            source = gr.File(
                label="音频或视频文件", type="filepath",
                file_types=sorted(VIDEO_EXTENSIONS | AUDIO_EXTENSIONS),
            )
            mode = gr.Radio(
                ["视频转音频", "视频转文字", "音频转文字"],
                value="视频转文字", label="处理任务",
            )
            audio_export = gr.Dropdown(
                list(AUDIO_EXPORTS), value="原音轨 · 不转码", label="音频格式",
                info="原音轨不重新压缩，最快且保留原始音质；不兼容时自动转为 FLAC。",
                visible=False,
            )
            with gr.Accordion("转写设置 · 按需调整", open=True, visible=True) as settings:
                model = gr.Dropdown(
                    list(ACTIVE_MODELS), value=DEFAULT_MODEL, label="速度与精度",
                    info="极速/快速更省时；均衡/准确更适合重要内容。",
                )
                language = gr.Dropdown(
                    list(LANGUAGES), value="自动检测", label="语音语言",
                    info="知道语言时明确选择，通常更稳定。",
                )
                terms = gr.Textbox(
                    label="专有名词提示 · 可选", lines=2,
                    placeholder="例如：声刻、产品名、人名、地名",
                    info="帮助模型识别特殊词语；提示不能保证结果准确。",
                )
                vad_filter = gr.Checkbox(
                    value=True, label="跳过静音",
                    info="开：减少无声片段与幻觉；关：尽量保留很轻的声音。",
                    visible=BACKEND == "local",
                )
                batch_long = gr.Checkbox(
                    value=True, label="长文件批量加速",
                    info="开：60 秒以上自动加速；关：占用更少内存。",
                    visible=BACKEND == "local",
                )
                word_timestamps = gr.Checkbox(
                    value=False, label="逐词时间戳",
                    info="开：JSON 包含每个词的时间；关：处理更快。",
                )
            with gr.Row():
                button = gr.Button("开始处理", variant="primary", scale=3)
                clear = gr.Button("清空", scale=1)
        with gr.Column(scale=1, min_width=320, elem_classes="panel"):
            gr.HTML('<div class="panel-title">处理结果</div>')
            status = gr.Textbox(label="状态", interactive=False,
                                value="上传文件后点击「开始处理」。")
            transcript = gr.Textbox(label="文字预览", lines=14,
                                    show_copy_button=True, interactive=False)
            downloads = gr.File(label="下载文件", file_count="multiple")

    mode.change(
        lambda choice: (gr.update(visible=choice == "视频转音频"),
                        gr.update(visible=choice != "视频转音频")),
        inputs=mode, outputs=[audio_export, settings],
    )
    button.click(
        run,
        inputs=[source, mode, audio_export, model, language, terms,
                vad_filter, batch_long, word_timestamps],
        outputs=[status, transcript, downloads],
    )
    clear.click(lambda: (None, "上传文件后点击「开始处理」。", "", None),
                outputs=[source, status, transcript, downloads], queue=False)
    footer = ("云端模式：文件会上传到本站服务器并交由 Groq 识别；请人工核对重要内容"
              if BACKEND == "groq" else
              "本地模式：文件仅保存在当前电脑；请人工核对重要内容")
    gr.HTML(f'<div class="footer-note">{footer}</div>')


if __name__ == "__main__":
    host = os.getenv("MEDIA_SCRIBE_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "7860"))
    password = os.getenv("MEDIA_SCRIBE_PASSWORD")
    if BACKEND == "groq" and not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("云端模式需要在服务端设置 GROQ_API_KEY。")
    if host != "127.0.0.1" and not password:
        raise RuntimeError("公网服务需要设置 MEDIA_SCRIBE_PASSWORD。")
    demo.queue().launch(server_name=host, server_port=port,
                        inbrowser=host == "127.0.0.1", max_file_size="100mb",
                        auth=("owner", password) if password else None)
