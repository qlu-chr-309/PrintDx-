# Gradio 演示界面：问题 + 可选图片/缺陷类型 → Agent → 展示工具调用与回答
"""印刷缺陷诊断 Web UI（面试演示）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gradio as gr

from config import CHAT_MODEL, DEFECT_CHOICES, GRADIO_SERVER_NAME, GRADIO_SERVER_PORT
from app.services import ServiceError, check_services, run_agent


def _format_tools(tool_calls: list) -> str:
    if not tool_calls:
        return "（本轮未调用工具）"
    lines = []
    for i, tc in enumerate(tool_calls, 1):
        lines.append(f"{i}. {tc.get('name')}  args={tc.get('args')}")
    return "\n".join(lines)


def diagnose(query: str, defect_label: str, image, model: str):
    query = (query or "").strip()
    if not query and defect_label == DEFECT_CHOICES[0]:
        return "请输入问题或选择缺陷类型。", "", ""
    if not query:
        query = f"{defect_label}如何诊断与处理？"

    health = check_services()
    if not health["ok"]:
        bad = [k for k, v in health["items"].items() if not v.get("ok")]
        return (
            f"远端服务不可用：{', '.join(bad)}。请先在服务器执行 start_remote_services.sh。",
            "",
            str(health),
        )

    label = None if defect_label == DEFECT_CHOICES[0] else defect_label
    image_note = None
    if image is not None:
        image_note = "用户上传了一张疑似缺陷样张（当前版本以标注类型+文字描述驱动诊断，图像用于展示与记录）。"

    try:
        out = run_agent(query, model=model or CHAT_MODEL, defect_label=label, image_note=image_note)
    except ServiceError as exc:
        return f"调用失败：{exc}", "", ""
    except Exception as exc:  # noqa: BLE001
        return f"未知错误：{exc}", "", ""

    tools = _format_tools(out.get("tool_calls") or [])
    meta = f"耗时 {out.get('elapsed_sec')}s | model={model} | trace 已写入 logs/traces.jsonl"
    return out["answer"], tools, meta


def build_ui():
    with gr.Blocks(title="印刷缺陷诊断 Agent") as demo:
        gr.Markdown(
            "## 印刷缺陷诊断智能体\n"
            "LangGraph Agent + 向量知识库（Chroma）+ 知识图谱 | 模型/数据在 GPU 服务器"
        )
        with gr.Row():
            with gr.Column(scale=1):
                image = gr.Image(label="缺陷样张（可选）", type="pil")
                defect = gr.Dropdown(DEFECT_CHOICES, value=DEFECT_CHOICES[0], label="缺陷类型")
                query = gr.Textbox(
                    label="问题描述",
                    lines=4,
                    placeholder="例如：细网点粘连发糊，可能是什么原因？怎么处理？",
                )
                model = gr.Textbox(value=CHAT_MODEL, label="Ollama 模型名")
                btn = gr.Button("开始诊断", variant="primary")
            with gr.Column(scale=1):
                answer = gr.Textbox(label="诊断结果", lines=16)
                tools = gr.Textbox(label="工具调用过程", lines=8)
                meta = gr.Textbox(label="运行信息", lines=2)
        btn.click(diagnose, inputs=[query, defect, image, model], outputs=[answer, tools, meta])
        gr.Examples(
            examples=[
                ["细网点粘连成片，层次丢失", "糊版", None, CHAT_MODEL],
                ["多色套合露白边", "套印不准", None, CHAT_MODEL],
                ["墨层出现细小漏白点", "针孔", None, CHAT_MODEL],
                ["批次颜色不一致，越印越偏", "色差", None, CHAT_MODEL],
            ],
            inputs=[query, defect, image, model],
        )
    return demo


def main():
    demo = build_ui()
    demo.launch(server_name=GRADIO_SERVER_NAME, server_port=GRADIO_SERVER_PORT)


if __name__ == "__main__":
    main()
