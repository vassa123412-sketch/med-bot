"""
MedgeClaw-style Research Dashboard
Real-time web dashboard for symptom analysis tracking and medical research
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

logger = logging.getLogger(__name__)

# State management
class TaskState:
    def __init__(self, task_id: str, title: str):
        self.task_id = task_id
        self.title = title
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.progress = 0
        self.status = "running"  # running, done, error
        self.steps: List[dict] = []
        self.outputs: List[dict] = []

    def add_step(self, step_id: str, desc: str, code: str = "", code_file: str = ""):
        self.steps.append({
            "step_id": step_id,
            "desc": desc,
            "code": code,
            "code_file": code_file,
            "outputs": [],
            "status": "pending",
        })
        self.save()

    def complete_step(self, step_id: str, outputs: List[dict] = None):
        for step in self.steps:
            if step["step_id"] == step_id:
                step["status"] = "done"
                if outputs:
                    step["outputs"] = outputs
                break
        self._update_progress()
        self.save()

    def error_step(self, step_id: str, error: str):
        for step in self.steps:
            if step["step_id"] == step_id:
                step["status"] = f"error: {error}"
                break
        self.save()

    def _update_progress(self):
        if not self.steps:
            self.progress = 0
            return
        done = sum(1 for s in self.steps if s["status"] == "done")
        self.progress = int((done / len(self.steps)) * 100)
        if self.progress >= 100:
            self.status = "done"

    def save(self):
        self.updated_at = datetime.now().isoformat()
        # Save to JSON for dashboard to read
        state_path = DASHBOARD_DIR / f"{self.task_id}.json"
        state_path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))

    def to_dict(self):
        return {
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress": self.progress,
            "status": self.status,
            "panels": self._build_panels(),
        }

    def _build_panels(self):
        panels = []
        # Progress panel
        panels.append({
            "type": "progress",
            "content": self.progress,
        })
        # Analysis plan
        if self.steps:
            panels.append({
                "type": "list",
                "label": "АНАЛИТИЧЕСКИЙ ПЛАН",
                "content": [
                    f"{'✅' if s['status']=='done' else '⏳'} {s['desc']}"
                    for s in self.steps
                ],
            })
        # Step panels
        for step in self.steps:
            panel = {
                "type": "step",
                "label": f"ШАГ: {step['desc']}",
                "content": {
                    "desc": step["desc"],
                    "code": step["code"],
                    "code_file": step["code_file"],
                    "outputs": step["outputs"],
                }
            }
            panels.append(panel)
        # Files panel
        if self.outputs:
            panels.append({
                "type": "files",
                "label": "ПРОДУКТЫ АНАЛИЗА",
                "content": self.outputs,
            })
        return panels


# Global state store
tasks: dict[str, TaskState] = {}
DASHBOARD_DIR = Path("data/dashboard")
DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MedgeClaw-style Dashboard")

# Load existing tasks on startup
for f in DASHBOARD_DIR.glob("*.json"):
    task_id = f.stem
    data = json.loads(f.read_text())
    task = TaskState(task_id, data["title"])
    task.created_at = data["created_at"]
    task.updated_at = data["updated_at"]
    task.progress = data["progress"]
    task.status = data["status"]
    tasks[task_id] = task


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(DASHBOARD_HTML)


@app.get("/api/tasks")
async def get_tasks():
    return JSONResponse({tid: t.to_dict() for tid, t in tasks.items()})


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id in tasks:
        return JSONResponse(tasks[task_id].to_dict())
    return JSONResponse({"error": "Task not found"}, status_code=404)


@app.post("/api/tasks")
async def create_task(task: dict):
    task_id = f"task_{len(tasks) + 1}_{date.today().isoformat()}"
    t = TaskState(task_id, task.get("title", "Без названия"))
    tasks[task_id] = t
    t.save()
    return JSONResponse({"task_id": task_id})


class DashboardHTML:
    """Inline HTML dashboard to avoid external file dependencies"""
    pass


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>МедАссистент - Дашборд</title>
<style>
  :root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-card: #161b22;
    --border: #30363d;
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --accent: #648FFF;
    --success: #3fb950;
    --warning: #FE6100;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg-primary); color: var(--text-primary);
    min-height: 100vh;
  }
  .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
  h1 { font-size: 24px; margin-bottom: 20px; }
  
  /* Header */
  #header {
    position: sticky; top: 0; z-index: 100;
    background: var(--bg-card); border-bottom: 1px solid var(--border);
    padding: 14px 24px;
  }
  #header-top { display: flex; align-items: center; justify-content: space-between; }
  #status-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--success); margin-right: 10px;
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
  #task-title { font-size: 15px; font-weight: 600; }
  #progress-label { font-size: 13px; font-weight: 700; color: var(--accent); }
  #progress-bar {
    height: 4px; background: var(--bg-primary);
    margin-top: 10px; border-radius: 2px; overflow: hidden;
  }
  #progress-fill {
    height: 100%; width: 0%; background: linear-gradient(90deg, var(--accent), #785EF0);
    transition: width 1s ease;
  }
  
  /* Panels */
  #panels { display: flex; flex-direction: column; gap: 10px; margin-top: 20px; }
  .panel {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 10px; overflow: hidden;
  }
  .panel-label {
    padding: 10px 16px; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: .06em;
    color: var(--text-secondary); background: var(--bg-secondary);
    cursor: pointer; display: flex; justify-content: space-between;
  }
  .panel-body { padding: 14px 16px; }
  .panel.collapsed .panel-body { display: none; }
  
  /* Step panel */
  .panel-step { border-left: 3px solid #785EF0; }
  .step-desc { font-size: 13px; line-height: 1.7; margin-bottom: 10px; }
  .step-output { margin: 8px 0; }
  .output-text {
    font-size: 13px; padding: 8px 12px; background: rgba(255,176,0,.06);
    border-left: 3px solid var(--warning); border-radius: 6px;
  }
  .output-image img { max-width: 100%; border-radius: 8px; border: 1px solid var(--border); }
  
  /* Code block */
  .code-block {
    font-family: "SF Mono","Consolas",monospace; font-size: 12px;
    background: #010409; padding: 14px; border-radius: 8px;
    white-space: pre-wrap; overflow-x: auto; max-height: 300px; overflow-y: auto;
  }
  
  /* List */
  .panel-list { list-style: none; }
  .panel-list li {
    font-size: 13px; padding: 8px 12px; background: var(--bg-secondary);
    border-radius: 6px; margin-bottom: 6px; border-left: 3px solid var(--border);
  }
  .panel-list li:hover { border-left-color: var(--accent); }
  
  /* Empty state */
  .empty-state {
    text-align: center; margin-top: 80px; color: var(--text-secondary);
    font-size: 13px; line-height: 2;
  }
  .empty-state .logo { font-size: 32px; opacity: .5; margin-bottom: 8px; }
</style>
</head>
<body>
<div id="header">
  <div id="header-top">
    <div style="display:flex;align-items:center">
      <span id="status-dot"></span>
      <span id="task-title">Ожидание задачи...</span>
    </div>
    <span id="progress-label">0%</span>
  </div>
  <div id="progress-bar"><div id="progress-fill"></div></div>
</div>
<div class="container">
  <div id="panels">
    <div class="empty-state">
      <div class="logo">🧬🏥</div>
      МедАссистент - Дашборд<br>
      Запустите анализ симптомов, чтобы увидеть прогресс
    </div>
  </div>
</div>
<script>
let lastJson = '';
const taskState = {};
const API_BASE = window.location.origin;

async function fetchState() {
  try {
    const res = await fetch(API_BASE + '/api/tasks/' + (taskState.id || ''));
    if (!res.ok) return;
    const text = await res.text();
    if (text === lastJson) return;
    lastJson = text;
    render(JSON.parse(text));
  } catch (e) {}
}

function render(data) {
  if (!data.title) return;
  document.getElementById('task-title').textContent = data.title;
  const pct = data.progress || 0;
  document.getElementById('progress-label').textContent = pct + '%';
  document.getElementById('progress-fill').style.width = pct + '%';
  
  const container = document.getElementById('panels');
  if (!data.panels || data.panels.length === 0) return;
  
  container.innerHTML = data.panels.map((p, i) => renderPanel(p, i)).join('');
}

function renderPanel(panel, idx) {
  const id = 'panel-' + idx;
  let body = '';
  switch (panel.type) {
    case 'progress': return '';
    case 'list':
      body = '<ul class="panel-list">' +
        panel.content.map(item => '<li>' + esc(item) + '</li>').join('') +
        '</ul>';
      break;
    case 'step':
      body = renderStep(panel.content);
      break;
    case 'files':
      body = '<div class="panel-list">' +
        panel.content.map(f => '<li>📄 ' + esc(f.name || f) + '</li>').join('') +
        '</div>';
      break;
    default:
      body = '<pre>' + esc(JSON.stringify(panel.content)) + '</pre>';
  }
  return `<div class="panel panel-step" id="${id}">
    <div class="panel-label" onclick="this.parentElement.classList.toggle('collapsed')">
      <span>${esc(panel.label || '')}</span><span>▼</span>
    </div>
    <div class="panel-body">${body}</div>
  </div>`;
}

function renderStep(content) {
  let html = '';
  if (content.desc) html += `<div class="step-desc">${esc(content.desc)}</div>`;
  if (content.code) {
    html += `<details><summary style="cursor:pointer;font-size:11px;color:var(--text-secondary);margin:8px 0">💻 Код</summary>
      <div class="code-block">${esc(content.code)}</div></details>`;
  }
  if (content.outputs && content.outputs.length) {
    html += '<div style="font-size:10px;font-weight:700;text-transform:uppercase;color:var(--text-secondary);margin:12px 0 6px">📦 Продукты</div>';
    content.outputs.forEach(o => {
      if (o.kind === 'text') {
        html += `<div class="step-output"><div class="output-text">${esc(o.value)}</div></div>`;
      } else if (o.kind === 'image') {
        html += `<div class="step-output output-image"><img src="${esc(o.src)}" loading="lazy"></div>`;
      }
    });
  }
  return html;
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Auto-refresh
setInterval(fetchState, 2000);
fetchState();
</script>
</body>
</html>"""


def run_dashboard(host="127.0.0.1", port=7788):
    """Run the dashboard server"""
    logger.info(f"Starting dashboard on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_dashboard()
