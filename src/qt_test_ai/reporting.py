from __future__ import annotations

import html
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .models import TestRun


def write_json(run: TestRun, out_path: Path) -> None:
    payload = {
        "created_at": run.created_at.isoformat(timespec="seconds"),
        "project_root": run.project_root,
        "exe_path": run.exe_path,
        "meta": run.meta,
        "findings": [asdict(f) for f in run.findings],
        "summary": run.summary_counts(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_html(run: TestRun, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    s = run.summary_counts()
    usability = (run.meta or {}).get("usability") or []
    functional_cases = (run.meta or {}).get("functional_cases") or []
    rows = []
    for f in run.findings:
        rows.append(
            "<tr>"
            f"<td>{html.escape(f.category)}</td>"
            f"<td>{html.escape(f.severity)}</td>"
            f"<td>{html.escape(f.title)}</td>"
            f"<td>{html.escape(f.file or '')}</td>"
            f"<td>{html.escape(str(f.line) if f.line else '')}</td>"
            f"<td><pre style='white-space:pre-wrap;margin:0'>{html.escape(f.details)}</pre></td>"
            "</tr>"
        )

    usability_rows = []
    for u in usability:
        usability_rows.append(
            "<tr>"
            f"<td>{html.escape(str(u.get('id','')))}</td>"
            f"<td>{html.escape(str(u.get('title','')))}</td>"
            f"<td>{html.escape(str(u.get('status','')))}</td>"
            f"<td><pre style='white-space:pre-wrap;margin:0'>{html.escape(str(u.get('note','')))}</pre></td>"
            "</tr>"
        )

    functional_rows = []
    for c in functional_cases:
        steps = "\n".join([str(x) for x in (c.get("steps") or []) if str(x)])
        functional_rows.append(
            "<tr>"
            f"<td>{html.escape(str(c.get('id','')))}</td>"
            f"<td>{html.escape(str(c.get('title','')))}</td>"
            f"<td><pre style='white-space:pre-wrap;margin:0'>{html.escape(steps)}</pre></td>"
            f"<td><pre style='white-space:pre-wrap;margin:0'>{html.escape(str(c.get('expected','')))}</pre></td>"
            f"<td><pre style='white-space:pre-wrap;margin:0'>{html.escape(str(c.get('actual','')))}</pre></td>"
            f"<td>{html.escape(str(c.get('status','')))}</td>"
            f"<td>{html.escape(str(c.get('evidence','')))}</td>"
            f"<td><pre style='white-space:pre-wrap;margin:0'>{html.escape(str(c.get('note','')))}</pre></td>"
            "</tr>"
        )

    created = html.escape(run.created_at.isoformat(timespec="seconds"))
    proj = html.escape(run.project_root)
    exe = html.escape(run.exe_path or "")

    llm_summary = ""
    llm_meta = (run.meta or {}).get("llm") or {}
    if isinstance(llm_meta, dict) and llm_meta.get("summary"):
      llm_summary = str(llm_meta.get("summary") or "")

    doc = f"""<!doctype html>
<html lang="zh-cn">
<head>
<meta charset="utf-8" />
<title>Qt 项目测试智能化报告</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; }}
.kv {{ margin: 8px 0; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; background:#eee; margin-right:8px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
th {{ background: #f6f6f6; text-align:left; }}
</style>
</head>
<body>
<h1>Qt 项目测试智能化报告</h1>
<div class="kv"><b>生成时间：</b>{created}</div>
<div class="kv"><b>项目目录：</b><code>{proj}</code></div>
<div class="kv"><b>被测程序：</b><code>{exe}</code></div>
<div class="kv">
  <span class="badge">info: {s.get('info',0)}</span>
  <span class="badge">warning: {s.get('warning',0)}</span>
  <span class="badge">error: {s.get('error',0)}</span>
</div>

<h2>易用性测试清单</h2>
<table>
  <thead>
    <tr><th>ID</th><th>检查项</th><th>结果</th><th>备注</th></tr>
  </thead>
  <tbody>
    {"".join(usability_rows) if usability_rows else "<tr><td colspan='4' style='color:#666'>未记录</td></tr>"}
  </tbody>
</table>

<h2>功能度测试用例</h2>
<table>
  <thead>
    <tr><th>ID</th><th>用例</th><th>步骤</th><th>预期</th><th>实际</th><th>结果</th><th>证据</th><th>备注</th></tr>
  </thead>
  <tbody>
    {"".join(functional_rows) if functional_rows else "<tr><td colspan='8' style='color:#666'>未记录</td></tr>"}
  </tbody>
</table>

<h2>发现项</h2>
<table>
  <thead>
    <tr><th>类别</th><th>级别</th><th>标题</th><th>文件</th><th>行</th><th>详情</th></tr>
  </thead>
  <tbody>
    {"".join(rows)}
  </tbody>
</table>

<h2>LLM 总结（可选）</h2>
<div style="white-space:pre-wrap;border:1px solid #ddd;padding:12px;border-radius:8px;background:#fafafa">
  {html.escape(llm_summary) if llm_summary else "<span style='color:#666'>未生成</span>"}
</div>

<hr />
<div style="color:#666">导出时间：{html.escape(datetime.now().isoformat(timespec='seconds'))}</div>
</body>
</html>"""

    out_path.write_text(doc, encoding="utf-8")
