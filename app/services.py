# 共享服务层：健康检查、向量、图谱、知识库、多模式诊断、Trace
"""印刷缺陷诊断核心服务（供 Agent / UI / Eval 复用）。"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 避开本机系统代理：httpx(trust_env=True) 访问内网 Chroma 会 502
_no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
_need = ["10.172.38.126", "localhost", "127.0.0.1"]
_parts = [p.strip() for p in _no_proxy.split(",") if p.strip()]
for _h in _need:
    if _h not in _parts:
        _parts.append(_h)
os.environ["NO_PROXY"] = ",".join(_parts)
os.environ["no_proxy"] = os.environ["NO_PROXY"]

import chromadb
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_ollama import ChatOllama

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    CHAT_MODEL,
    CHROMA_COLLECTION,
    CHROMA_HOST,
    CHROMA_PORT,
    EMBED_MODEL,
    KG_URL,
    OLLAMA_BASE_URL,
    TRACE_DIR,
)

ROOT = Path(__file__).resolve().parents[1]


class ServiceError(RuntimeError):
    """远端服务不可用或调用失败。"""


def _http_json(url: str, payload: dict | None = None, timeout: float = 180.0) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ServiceError(f"无法连接 {url}: {exc}") from exc
    except TimeoutError as exc:
        raise ServiceError(f"请求超时 {url}") from exc


def check_services() -> dict[str, Any]:
    status: dict[str, Any] = {"ok": True, "items": {}}
    # Ollama
    try:
        ver = _http_json(OLLAMA_BASE_URL.rstrip("/") + "/api/version", timeout=8)
        status["items"]["ollama"] = {"ok": True, "detail": ver}
    except Exception as exc:  # noqa: BLE001
        status["ok"] = False
        status["items"]["ollama"] = {"ok": False, "detail": str(exc)}
    # Chroma
    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        hb = client.heartbeat()
        cols = [c.name for c in client.list_collections()]
        status["items"]["chroma"] = {"ok": True, "detail": {"heartbeat": hb, "collections": cols}}
    except Exception as exc:  # noqa: BLE001
        status["ok"] = False
        status["items"]["chroma"] = {"ok": False, "detail": str(exc)}
    # KG（仅远程）
    try:
        g = _http_json(KG_URL, timeout=8)
        status["items"]["kg"] = {
            "ok": True,
            "detail": {
                "source": KG_URL,
                "nodes": len(g.get("nodes", {})),
                "edges": len(g.get("edges", [])),
            },
        }
    except Exception as exc:  # noqa: BLE001
        status["ok"] = False
        status["items"]["kg"] = {"ok": False, "detail": str(exc)}
    return status


def embed_texts(texts: list[str]) -> list[list[float]]:
    result = _http_json(
        OLLAMA_BASE_URL.rstrip("/") + "/api/embed",
        {"model": EMBED_MODEL, "input": texts},
        timeout=180,
    )
    if "embeddings" not in result:
        raise ServiceError(f"向量化失败: {result}")
    return result["embeddings"]


def chat(messages: list[dict], model: str = CHAT_MODEL) -> str:
    result = _http_json(
        OLLAMA_BASE_URL.rstrip("/") + "/v1/chat/completions",
        {"model": model, "messages": messages, "stream": False},
        timeout=300,
    )
    try:
        return result["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(f"聊天接口返回异常: {result}") from exc


def load_graph() -> dict:
    return _http_json(KG_URL, timeout=30)


def list_defect_names(graph: dict | None = None) -> list[str]:
    g = graph or load_graph()
    return sorted(n["name"] for n in g["nodes"].values() if n.get("type") == "Defect")


def match_defect(graph: dict, query: str) -> dict | None:
    q = query.strip()
    best = None
    for node in graph["nodes"].values():
        if node.get("type") != "Defect":
            continue
        names = [node.get("name", "")] + node.get("aliases", [])
        for n in names:
            if n and (n in q or q in n):
                return node
        for n in names:
            if n and n in query:
                best = node
    return best


def kg_context_for_defect(graph: dict, defect: dict) -> str:
    did = defect["id"]
    nodes = graph["nodes"]
    lines = [f"缺陷: {defect['name']} — {defect.get('desc', '')}"]
    for e in graph["edges"]:
        if e["source"] == did:
            tgt = nodes.get(e["target"], {})
            lines.append(
                f"- [{e['relation']}] {tgt.get('type')}:{tgt.get('name')} | {tgt.get('desc', '')}"
            )
        if e["target"] == did and e["relation"] == "Mitigates":
            src = nodes.get(e["source"], {})
            lines.append(
                f"- [MitigatedBy] {src.get('type')}:{src.get('name')} | {src.get('desc', '')}"
            )
    return "\n".join(lines)


def search_kb(query: str, top_k: int = 4) -> list[dict]:
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    col = client.get_or_create_collection(CHROMA_COLLECTION)
    qv = embed_texts([query])[0]
    res = col.query(query_embeddings=[qv], n_results=top_k)
    rows = []
    for doc, meta, dist in zip(
        res["documents"][0],
        res["metadatas"][0],
        res.get("distances", [[None] * top_k])[0],
    ):
        rows.append({"document": doc, "metadata": meta, "distance": dist})
    return rows


def format_kb_rows(rows: list[dict]) -> str:
    if not rows:
        return "知识库无命中结果"
    parts = []
    for i, row in enumerate(rows, 1):
        meta = row["metadata"] or {}
        parts.append(
            f"[{i}] source={meta.get('source')} title={meta.get('title')} dist={row.get('distance')}\n{row['document']}"
        )
    return "\n\n".join(parts)


def write_trace(record: dict) -> Path:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACE_DIR / "traces.jsonl"
    record = {
        **record,
        "ts": datetime.now(timezone.utc).isoformat(),
        "trace_id": record.get("trace_id") or str(uuid.uuid4()),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


@tool
def search_knowledge_base(query: str) -> str:
    """在印刷缺陷文本知识库中做向量语义检索。输入缺陷现象或问题描述，返回最相关的工艺说明段落。"""
    return format_kb_rows(search_kb(query, top_k=4))


@tool
def query_knowledge_graph(defect_name: str) -> str:
    """在印刷缺陷知识图谱中查询实体关系。输入缺陷名称（如糊版、针孔、套印不准），返回关联的原因、措施、工艺、参数。"""
    graph = load_graph()
    hit = match_defect(graph, defect_name)
    if not hit:
        names = list_defect_names(graph)
        return f"未找到缺陷「{defect_name}」。可用缺陷名：{', '.join(names)}"
    return kg_context_for_defect(graph, hit)


def build_agent(model_name: str = CHAT_MODEL):
    llm = ChatOllama(model=model_name, base_url=OLLAMA_BASE_URL, temperature=0)
    return create_agent(
        model=llm,
        tools=[search_knowledge_base, query_knowledge_graph],
        system_prompt=(
            "你是印刷缺陷诊断智能体。"
            "遇到具体缺陷问题：先用 query_knowledge_graph 查图谱关系，"
            "再用 search_knowledge_base 查文本知识库。"
            "若用户提供了缺陷类型标签，优先按该类型查图谱。"
            "综合工具结果给出：缺陷判断、可能原因、处理措施、相关参数、依据。"
            "不要编造工具未返回的内容。"
        ),
    )


def summarize_messages(messages: list) -> dict:
    tool_calls = []
    tool_results = []
    for msg in messages:
        role = type(msg).__name__
        content = getattr(msg, "content", "") or ""
        calls = getattr(msg, "tool_calls", None) or []
        for tc in calls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
            tool_calls.append({"name": name, "args": args})
        if role == "ToolMessage":
            tool_results.append(content[:2000])
    final = ""
    if messages:
        final = getattr(messages[-1], "content", "") or ""
    return {"tool_calls": tool_calls, "tool_results": tool_results, "final": final}


def run_agent(
    query: str,
    *,
    model: str = CHAT_MODEL,
    defect_label: str | None = None,
    image_note: str | None = None,
) -> dict:
    t0 = time.time()
    parts = [query]
    if defect_label:
        parts.insert(0, f"【用户标注缺陷类型】{defect_label}")
    if image_note:
        parts.insert(0, f"【已上传缺陷样张】{image_note}")
    user_text = "\n".join(parts)
    agent = build_agent(model)
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": user_text}]})
    except ServiceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ServiceError(f"Agent 执行失败: {exc}") from exc
    summary = summarize_messages(result["messages"])
    elapsed = round(time.time() - t0, 3)
    trace = {
        "mode": "agent",
        "query": query,
        "defect_label": defect_label,
        "image_note": image_note,
        "model": model,
        "elapsed_sec": elapsed,
        "tool_calls": summary["tool_calls"],
        "tool_results": summary["tool_results"],
        "answer": summary["final"],
    }
    write_trace(trace)
    return {
        "answer": summary["final"],
        "tool_calls": summary["tool_calls"],
        "messages": result["messages"],
        "elapsed_sec": elapsed,
        "trace": trace,
    }


def run_pipeline(
    query: str,
    *,
    mode: str,
    model: str = CHAT_MODEL,
    defect_label: str | None = None,
) -> dict:
    """评测用多模式：none / kb / kb_kg / agent。"""
    t0 = time.time()
    q = query if not defect_label else f"{defect_label}：{query}"
    if mode == "agent":
        out = run_agent(query, model=model, defect_label=defect_label)
        out["mode"] = "agent"
        return out

    ctx_parts = []
    tool_calls = []
    if mode in {"kb", "kb_kg"}:
        rows = search_kb(q, top_k=4)
        ctx_parts.append("【知识库】\n" + format_kb_rows(rows))
        tool_calls.append({"name": "search_knowledge_base", "args": {"query": q}})
    if mode == "kb_kg":
        graph = load_graph()
        hit = match_defect(graph, defect_label or q)
        if hit:
            ctx_parts.append("【知识图谱】\n" + kg_context_for_defect(graph, hit))
            tool_calls.append({"name": "query_knowledge_graph", "args": {"defect_name": hit["name"]}})
        else:
            ctx_parts.append("【知识图谱】未匹配到缺陷节点")
    if mode == "none":
        system = "你是印刷缺陷助手。仅根据自身知识简要回答，并说明可能不确定。"
        user = q
    else:
        system = (
            "你是印刷缺陷诊断助手。仅依据给定检索结果作答，不要编造。"
            "输出：缺陷判断、可能原因、处理措施、相关参数、依据。"
        )
        user = f"问题：{q}\n\n" + "\n\n".join(ctx_parts)

    answer = chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model,
    )
    elapsed = round(time.time() - t0, 3)
    trace = {
        "mode": mode,
        "query": query,
        "defect_label": defect_label,
        "model": model,
        "elapsed_sec": elapsed,
        "tool_calls": tool_calls,
        "answer": answer,
    }
    write_trace(trace)
    return {"mode": mode, "answer": answer, "tool_calls": tool_calls, "elapsed_sec": elapsed, "trace": trace}
