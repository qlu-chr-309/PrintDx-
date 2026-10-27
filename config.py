# 本机只放代码；模型 / 向量库 / 图谱数据都在服务器
"""全局连接配置：指向 10.172.38.126 上的服务。"""

from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent

# Ollama（聊天 + 向量化）
OLLAMA_BASE_URL = "http://10.172.38.126:11434"
# 向量模型
EMBED_MODEL = "bge-m3"
# 默认聊天模型
CHAT_MODEL = "qwen2.5:7b"

# Chroma HTTP 服务（服务器上 chroma run）
CHROMA_HOST = "10.172.38.126"
CHROMA_PORT = 8000
# 集合名（与服务器入库时一致）
CHROMA_COLLECTION = "print_defect_kb"

# 知识图谱 JSON（仅服务器；本机不落盘业务数据）
KG_URL = "http://10.172.38.126:8001/graph.json"

# 可观测性：本机 JSONL trace 目录（运行日志，非业务知识库）
TRACE_DIR = PROJECT_ROOT / "logs"

# Gradio
GRADIO_SERVER_NAME = "127.0.0.1"
GRADIO_SERVER_PORT = 7860

# 缺陷类型（多模态入口下拉）
DEFECT_CHOICES = [
    "（自动识别/不指定）",
    "墨斑",
    "糊版",
    "针孔",
    "套印不准",
    "色差",
    "重影",
    "背面蹭脏",
    "拉毛",
    "附着力不良",
    "条杠",
    "蹭脏",
    "水杠",
]
