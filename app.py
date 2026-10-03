"""Run with `python app.py`. The UI binds to localhost only."""

import gradio as gr

from media_scribe import LANGUAGES, MODELS, process

CSS = """
.gradio-container {max-width: 900px !important; margin: auto !important;}
#hero {text-align: center; padding: 1.5rem 0 .25rem;}
#hero h1 {font-size: 2.1rem; margin-bottom: .3rem;}
#hero p {color: #64748b; margin-top: 0;}
"""


def run(file_path, mode, model, language, progress=gr.Progress()):
    try:
        return process(file_path, mode, model, language,
                       lambda message: progress(None, desc=message))
    except Exception as exc:
        raise gr.Error(str(exc)) from exc


with gr.Blocks(title="声刻 · 音视频转文字", css=CSS, theme=gr.themes.Soft()) as demo:
    gr.HTML("<div id='hero'><h1>声刻</h1><p>音视频一键提取与转写 · 文件在本机处理</p></div>")
    with gr.Row():
        with gr.Column(scale=1):
            source = gr.File(label="上传音频或视频", type="filepath",
                             file_types=["video", "audio"])
            mode = gr.Radio(["视频转音频", "视频转文字", "音频转文字"],
                            value="视频转文字", label="处理方式")
            with gr.Accordion("识别设置", open=False):
                model = gr.Dropdown(list(MODELS), value="均衡 · small", label="模型精度",
                                    info="越准确通常越慢；只提取音频时无需设置")
                language = gr.Dropdown(list(LANGUAGES), value="自动检测", label="语音语言",
                                       info="知道语言时手动选择通常更稳定")
            button = gr.Button("开始处理", variant="primary")
        with gr.Column(scale=1):
            status = gr.Textbox(label="处理状态", interactive=False)
            transcript = gr.Textbox(label="转写结果", lines=12, show_copy_button=True,
                                    interactive=False)
            downloads = gr.File(label="下载文件", file_count="multiple")
    button.click(run, inputs=[source, mode, model, language],
                 outputs=[status, transcript, downloads])
    gr.Markdown("本地运行 · 首次转写需要联网下载模型 · 请核对专有名词和重要数字")

if __name__ == "__main__":
    demo.queue().launch(server_name="127.0.0.1", inbrowser=True)
