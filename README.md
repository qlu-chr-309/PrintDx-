# 印刷缺陷诊断智能体

本机**只放代码**（`F:\agent示例学习`）；模型 / 向量库 / 图谱 / seed **只在服务器** `10.172.38.126`。

| 组件 | 地址 / 路径 |
|------|-------------|
| Ollama | `http://10.172.38.126:11434`（`qwen2.5:7b` / `bge-m3`） |
| Chroma | `http://10.172.38.126:8000` 集合 `print_defect_kb` |
| 知识图谱 | `http://10.172.38.126:8001/graph.json` |
| 服务器数据 | `/mnt/sda2/chr/print-defect-kg`（`kg/`、`kb/`、`data/seed/`） |
| Trace | 本机 `logs/traces.jsonl`（运行日志，非业务数据） |

SSH：`ssh wq@10.172.38.126`（或 `ssh 10.172.38.126` / `ssh dev126`）

## 架构

- **Agent**：LangChain `create_agent`（底层 LangGraph）  
  - `search_knowledge_base` → 远程 Chroma  
  - `query_knowledge_graph` → 远程 `graph.json`
- **评测**：`none` / `kb` / `kb_kg` / `agent`（`eval/run_eval.py`）
- **多模态入口**：Gradio 上传样张 + 缺陷类型 → Agent / trace

## 本机准备

```powershell
cd F:\agent示例学习
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 服务器服务与数据构建

```bash
ssh wq@10.172.38.126
cd /mnt/sda2/chr/print-defect-kg
source .venv/bin/activate
bash scripts/start_remote_services.sh

# 如需重建图谱 / 向量库（在服务器执行）
python scripts/build_kg.py
python scripts/build_kb.py
```

## 本机运行

```powershell
python scripts\check_services.py
python app\diagnose.py "套印不准怎么处理？"
python app\agent_diagnose.py "糊版细网点粘连怎么处理？"
python -m app.ui_gradio
python eval\run_eval.py --limit 3
```

## 本机目录

```
app/           # services / agent / diagnose / Gradio
config.py      # 远端连接（无本地业务数据路径）
eval/          # 题集与对比评测
scripts/       # 健康检查、本机启动
logs/          # traces.jsonl
```
