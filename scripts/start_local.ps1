# 本机启动 Gradio 演示界面（需已激活 venv，远端服务已开）
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "未找到 .venv，请先: python -m venv .venv && .\.venv\Scripts\pip install -r requirements.txt"
}

Write-Host "检查远端服务..."
& .\.venv\Scripts\python.exe -c "from app.services import check_services; import json; print(json.dumps(check_services(), ensure_ascii=False, indent=2))"

Write-Host "启动 Gradio http://127.0.0.1:7860 ..."
& .\.venv\Scripts\python.exe -m app.ui_gradio
