from __future__ import annotations

import os
import json

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from . import db as dbmod
from .doc_checks import run_doc_checks, run_llm_doc_checks
from .dynamic_checks import pick_exe, run_smoke_test, run_windows_ui_probe
from .models import Finding, TestRun
from .reporting import write_html, write_json
from .static_checks import run_static_checks
from .utils import looks_like_qt_pro
from .functional_cases import (
    FunctionalCase,
    default_case_library,
    load_case_library,
    save_case_library,
)
from .llm import chat_completion_text, load_llm_config_from_env, load_llm_system_prompt_from_env
from .qt_project import build_project_context


def _env_flag(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


@dataclass
class RunOptions:
    project_root: Path
    exe_path: Path | None
    enable_ui_probe: bool
    functional_entries: list[dict]


class Worker(QtCore.QObject):
    progress = QtCore.Signal(str)
    finished = QtCore.Signal(object)  # TestRun

    def __init__(self, opts: RunOptions):
        super().__init__()
        self.opts = opts

    @QtCore.Slot()
    def run(self) -> None:
        findings: list[Finding] = []
        meta: dict = {"looks_like_qt_pro": looks_like_qt_pro(self.opts.project_root)}

        try:
            meta["functional_cases"] = self.opts.functional_entries
            for c in self.opts.functional_entries:
                if c.get("status") == "fail":
                    findings.append(
                        Finding(
                            category="functional",
                            severity="error",
                            title=f"功能用例失败：{c.get('id','')} {c.get('title','')}",
                            details=str(c.get("actual") or ""),
                            rule_id=str(c.get("id") or ""),
                        )
                    )

            self.progress.emit("运行静态检查…")
            f_static, m_static = run_static_checks(self.opts.project_root)
            findings.extend(f_static)
            meta["static"] = m_static

            self.progress.emit("运行用户文档检查…")
            f_docs, m_docs = run_doc_checks(self.opts.project_root)
            findings.extend(f_docs)
            meta["docs"] = m_docs
            
            # LLM 文档一致性检查（如果配置了 LLM）
            llm_cfg = load_llm_config_from_env()
            if llm_cfg and m_docs.get("doc_files"):
                self.progress.emit("运行 LLM 文档一致性检查…")
                try:
                    # 读取文档内容
                    from .utils import read_text_best_effort
                    doc_content = ""
                    for dp in m_docs.get("doc_files", [])[:3]:  # 限制数量
                        if Path(dp).exists() and Path(dp).suffix in [".md", ".txt"]:
                            doc_content += f"\n=== {Path(dp).name} ===\n"
                            doc_content += read_text_best_effort(Path(dp))[:3000]
                    
                    # 获取项目上下文
                    ctx = build_project_context(self.opts.project_root)
                    project_context = ctx.prompt_text if ctx else ""
                    
                    # 运行 LLM 文档检查
                    f_llm_docs = run_llm_doc_checks(
                        self.opts.project_root, 
                        llm_cfg, 
                        doc_content, 
                        project_context
                    )
                    findings.extend(f_llm_docs)
                    meta["docs"]["llm_checks"] = len(f_llm_docs)
                except Exception as e:
                    self.progress.emit(f"LLM 文档检查出错: {e}")

            self.progress.emit("准备动态测试…")
            exe, f_pick, m_pick = pick_exe(self.opts.project_root, self.opts.exe_path)
            findings.extend(f_pick)
            meta["dynamic_pick"] = m_pick

            if exe is not None:
                self.progress.emit("运行动态检测…")
                f_smoke, m_smoke = run_smoke_test(exe, workdir=self.opts.project_root)
                findings.extend(f_smoke)
                meta["dynamic_smoke"] = m_smoke

                if self.opts.enable_ui_probe:
                    self.progress.emit("运行 Windows UI 探测…")
                    f_ui, m_ui = run_windows_ui_probe(exe)
                    findings.extend(f_ui)
                    meta["dynamic_ui"] = m_ui
                    
                # 自动保存动态测试报告
                try:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # Always save to tool's reports/dynamic directory, as requested
                    tool_root = Path(__file__).resolve().parents[2]
                    dyn_dir = tool_root / "reports" / "dynamic"
                    
                    dyn_dir.mkdir(parents=True, exist_ok=True)
                    dyn_out = dyn_dir / f"smoke_test_{ts}.json"
                    
                    # 构造简单报告内容
                    dyn_report = {
                        "exe_path": str(exe),
                        "timestamp": datetime.now().isoformat(),
                        "smoke_test": meta.get("dynamic_smoke"),
                        "ui_probe": meta.get("dynamic_ui"),
                        "findings": [
                            {"title": f.title, "severity": f.severity, "details": f.details}
                            for f in findings if f.category == "dynamic"
                        ]
                    }
                    dyn_out.write_text(json.dumps(dyn_report, ensure_ascii=False, indent=2), encoding="utf-8")
                    self.progress.emit(f"动态测试报告已保存：{dyn_out}")
                except Exception as e:
                    self.progress.emit(f"⚠️ 保存动态测试报告失败：{e}")

            # 自动化：生成测试用例 / 运行测试 / 覆盖率（可选）
            if _env_flag("QT_TEST_AI_ENABLE_AUTOMATION"):
                try:
                    from .test_automation import (
                        generate_qttest_via_llm,
                        run_coverage_command,
                        run_test_command,
                        save_stage_report,
                    )

                    # 统一本次 run 的阶段报告目录时间戳
                    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    meta.setdefault("stage_reports", {})

                    # ----------------------------
                    # A) 生成 QtTest 用例
                    # ----------------------------
                    self.progress.emit("自动化：LLM 生成 QtTest 用例…")
                    f_gen, m_gen = generate_qttest_via_llm(self.opts.project_root)
                    findings.extend(f_gen)
                    meta["testgen"] = m_gen

                    # 终端打印 + UI 日志
                    out_dir = (m_gen or {}).get("out_dir")
                    files = (m_gen or {}).get("files") or []
                    print("[testgen] out_dir:", out_dir)
                    print("[testgen] files:")
                    for p in files:
                        print("  -", p)

                    self.progress.emit(f"[testgen] out_dir: {out_dir or ''}")
                    if files:
                        self.progress.emit("[testgen] files:\n" + "\n".join([f"  - {p}" for p in files]))

                    rep_gen = save_stage_report(
                        project_root=self.opts.project_root,
                        stage="testgen",
                        findings=f_gen,
                        meta=m_gen,
                        run_ts=run_ts,
                    )
                    meta["stage_reports"]["testgen"] = rep_gen
                    self.progress.emit(f"testgen 报告已保存：{rep_gen.get('out_dir')}")

                    # ----------------------------
                    # B) 运行测试命令
                    # ----------------------------
                    self.progress.emit("自动化：运行测试命令…")
                    f_test, m_test = run_test_command(self.opts.project_root)
                    findings.extend(f_test)
                    meta["tests"] = m_test

                    print("[tests] returncode:", (m_test or {}).get("returncode"))
                    if (m_test or {}).get("timed_out"):
                        print("[tests] timed out:", (m_test or {}).get("timeout_s"))
                    print("[tests] cwd:", (m_test or {}).get("cwd"))
                    print("[tests] cmd:", (m_test or {}).get("cmd"))

                    self.progress.emit(
                        f"[tests] returncode={(m_test or {}).get('returncode')} "
                        + ("(timed out)" if (m_test or {}).get("timed_out") else "")
                    )

                    rep_test = save_stage_report(
                        project_root=self.opts.project_root,
                        stage="tests",
                        findings=f_test,
                        meta=m_test,
                        run_ts=run_ts,
                    )
                    meta["stage_reports"]["tests"] = rep_test
                    self.progress.emit(f"tests 报告已保存：{rep_test.get('out_dir')}")

                    # ----------------------------
                    # C) 运行覆盖率命令
                    # ----------------------------
                    self.progress.emit("自动化：运行覆盖率命令…")
                    f_cov, m_cov = run_coverage_command(self.opts.project_root)
                    findings.extend(f_cov)
                    meta["coverage"] = m_cov

                    print("[coverage] returncode:", (m_cov or {}).get("returncode"))
                    if (m_cov or {}).get("summary"):
                        print("[coverage] summary:", (m_cov or {}).get("summary"))
                    print("[coverage] cmd:", (m_cov or {}).get("cmd"))

                    self.progress.emit(
                        f"[coverage] returncode={(m_cov or {}).get('returncode')} "
                        + (f"summary={(m_cov or {}).get('summary')}" if (m_cov or {}).get("summary") else "")
                    )

                    rep_cov = save_stage_report(
                        project_root=self.opts.project_root,
                        stage="coverage",
                        findings=f_cov,
                        meta=m_cov,
                        run_ts=run_ts,
                    )
                    meta["stage_reports"]["coverage"] = rep_cov
                    self.progress.emit(f"coverage 报告已保存：{rep_cov.get('out_dir')}")

                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    print(f"[AUTOMATION ERROR] {e}")
                    print(error_trace)
                    findings.append(
                        Finding(
                            category="automation",
                            severity="warning",
                            title="自动化测试/覆盖率阶段失败",
                            details=f"{str(e)}\n\nTraceback:\n{error_trace}",
                        )
                    )
            else:
                meta["automation"] = {"enabled": False, "hint_env": "QT_TEST_AI_ENABLE_AUTOMATION=1"}

            run = TestRun(
                project_root=str(self.opts.project_root),
                exe_path=str(exe) if exe else None,
                created_at=datetime.now(),
                findings=findings,
                meta=meta,
            )
            self.finished.emit(run)
        except Exception as e:
            meta["internal_error"] = str(e)
            findings.append(
                Finding(
                    category="internal",
                    severity="error",
                    title="运行过程中发生未处理异常",
                    details=str(e),
                )
            )
            run = TestRun(
                project_root=str(self.opts.project_root),
                exe_path=str(self.opts.exe_path) if self.opts.exe_path else None,
                created_at=datetime.now(),
                findings=findings,
                meta=meta,
            )
            self.finished.emit(run)


class SummaryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(16)

        self.cards = []
        # Create 4 summary cards
        for title, color in [("总发现项", "#3B82F6"), ("错误 (Error)", "#EF4444"), ("警告 (Warn)", "#F59E0B"), ("通过率", "#10B981")]:
            card = QtWidgets.QFrame()
            card.setObjectName("SummaryCard")
            card.setStyleSheet(f"""
                QFrame#SummaryCard {{
                    background: white;
                    border: 1px solid #E2E8F0;
                    border-radius: 12px;
                    border-left: 5px solid {color};
                }}
            """)
            cl = QtWidgets.QVBoxLayout(card)
            cl.setContentsMargins(16, 16, 16, 16)
            
            lbl_val = QtWidgets.QLabel("-")
            lbl_val.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {color}; border: none;")
            lbl_val.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            
            lbl_title = QtWidgets.QLabel(title)
            lbl_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #64748B; border: none;")

            cl.addWidget(lbl_val)
            cl.addWidget(lbl_title)
            self.layout.addWidget(card)
            self.cards.append(lbl_val)

    def update_stats(self, total: int, err: int, warn: int, pass_rate: str):
        self.cards[0].setText(str(total))
        self.cards[1].setText(str(err))
        self.cards[2].setText(str(warn))
        self.cards[3].setText(pass_rate)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Qt 项目测试智能化工具")
        self.resize(1100, 760)

        self._db_path = Path.home() / ".qt_test_ai" / "runs.sqlite3"
        self._conn = dbmod.open_db(self._db_path)

        # UI
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        self.project_edit = QtWidgets.QLineEdit()
        self.project_edit.setPlaceholderText("选择 Qt 项目根目录（包含 .pro 的目录）")
        self.project_edit.setMinimumHeight(36)
        self.project_btn = QtWidgets.QPushButton("选择项目目录")
        self.project_btn.setMinimumHeight(34)
        self.exe_edit = QtWidgets.QLineEdit()
        self.exe_edit.setPlaceholderText("可选：选择被测程序 .exe（不选则自动搜索）")
        self.exe_edit.setMinimumHeight(36)
        self.exe_btn = QtWidgets.QPushButton("选择 exe（可选）")
        self.exe_btn.setMinimumHeight(34)
        self.ui_probe_chk = QtWidgets.QCheckBox("启用 Windows UI 探测（pywinauto）")
        self.ui_probe_chk.setChecked(True)

        self.run_btn = QtWidgets.QPushButton("一键运行（静态/动态/文档/自动化）")
        self.run_btn.setProperty("kind", "primary")
        self.run_btn.setMinimumHeight(38)
        self.export_btn = QtWidgets.QPushButton("导出报告")
        self.export_btn.setProperty("kind", "secondary")
        self.export_btn.setEnabled(False)
        self.export_btn.setMinimumHeight(34)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["类别", "级别", "标题", "文件"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._show_selected_finding_details)

        self.automation_btn = QtWidgets.QPushButton("运行自动化：生成测试/执行/覆盖率")
        self.automation_btn.setProperty("kind", "secondary")
        self.automation_btn.setToolTip(
            "需要开启 QT_TEST_AI_ENABLE_AUTOMATION=1，并可选配置 QT_TEST_AI_TEST_CMD / QT_TEST_AI_COVERAGE_CMD"
        )

        self.functional_table = QtWidgets.QTableWidget(0, 8)
        self.functional_table.setHorizontalHeaderLabels(["ID", "用例", "步骤", "预期", "实际", "结果", "证据", "备注"])
        self.functional_table.horizontalHeader().setStretchLastSection(True)
        self.functional_table.verticalHeader().setVisible(False)
        self.functional_table.setAlternatingRowColors(True)
        self.functional_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.functional_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked)

        self.functional_load_btn = QtWidgets.QPushButton("加载用例库(JSON)")
        self.functional_save_btn = QtWidgets.QPushButton("保存用例库(JSON)")
        self.functional_reset_btn = QtWidgets.QPushButton("重置")
        self.functional_load_btn.setProperty("kind", "secondary")
        self.functional_save_btn.setProperty("kind", "secondary")
        self.functional_reset_btn.setProperty("kind", "secondary")
        self.functional_reset_btn.clicked.connect(self._reset_functional_table)

        self.functional_add_btn = QtWidgets.QPushButton("新增用例")
        self.functional_del_btn = QtWidgets.QPushButton("删除选中")
        self.functional_add_btn.setProperty("kind", "secondary")
        self.functional_del_btn.setProperty("kind", "secondary")
        self.functional_llm_btn = QtWidgets.QPushButton("LLM 生成用例")
        self.functional_llm_btn.setProperty("kind", "secondary")
        self.functional_llm_btn.setProperty("kind", "primary")
        self.functional_llm_btn.clicked.connect(self._llm_generate_functional)
        
        self.functional_sync_btn = QtWidgets.QPushButton("从 QTest 导入")
        self.functional_sync_btn.setToolTip("扫描 tests 目录下的 C++ 代码，尝试提取功能用例")
        self.functional_sync_btn.clicked.connect(self._llm_sync_from_qtest)
        self._init_functional_table(default_case_library())

        self.llm_summary_btn = QtWidgets.QPushButton("LLM 生成测试总结报告")
        self.llm_summary_btn.setProperty("kind", "secondary")
        self.llm_summary_btn.setProperty("kind", "primary")
        self.llm_summary_btn.setEnabled(False)
        self.llm_summary_btn.clicked.connect(self._llm_summarize_last_run)

        self.history = QtWidgets.QListWidget()
        self.history.setAlternatingRowColors(True)
        self.refresh_history_btn = QtWidgets.QPushButton("刷新历史")
        self.load_history_btn = QtWidgets.QPushButton("加载选中记录")
        self.delete_history_btn = QtWidgets.QPushButton("删除选中记录")
        self.refresh_history_btn.setProperty("kind", "secondary")
        self.load_history_btn.setProperty("kind", "secondary")
        self.delete_history_btn.setProperty("kind", "secondary")

        # --- Layout (with groups) ---
        header = QtWidgets.QLabel("Qt 项目测试智能化工具")
        header.setProperty("role", "header")
        header.setWordWrap(True)
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        sub = QtWidgets.QLabel("静态/动态/文档检查 + 自动化生成测试/覆盖率 + 报告导出")
        sub.setProperty("role", "subheader")
        sub.setWordWrap(True)
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        project_group = QtWidgets.QGroupBox("🚀 项目与运行")
        form = QtWidgets.QFormLayout(project_group)
        form.setContentsMargins(14, 16, 14, 14)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        h1 = QtWidgets.QHBoxLayout(); h1.addWidget(self.project_edit); h1.addWidget(self.project_btn)
        h2 = QtWidgets.QHBoxLayout(); h2.addWidget(self.exe_edit); h2.addWidget(self.exe_btn)
        form.addRow("项目目录", h1)
        form.addRow("被测程序", h2)
        form.addRow("选项", self.ui_probe_chk)

        top_btns = QtWidgets.QHBoxLayout()
        top_btns.addWidget(self.run_btn)
        top_btns.addWidget(self.export_btn)
        top_btns.addStretch(1)
        form.addRow("操作", top_btns)

        # 页面导航 + 堆叠页面
        nav_bar = QtWidgets.QHBoxLayout()
        nav_bar.setSpacing(6)
        nav_bar.setContentsMargins(0, 8, 0, 0)

        def _nav_btn(text: str) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(text)
            b.setCheckable(True)
            b.setProperty("kind", "nav")
            b.setMinimumHeight(38)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            return b

        btn_home = _nav_btn("欢迎页")
        btn_proj = _nav_btn("项目配置")
        btn_auto = _nav_btn("自动化测试")
        btn_fun = _nav_btn("功能测试")
        btn_doc = _nav_btn("文档检查")
        btn_fnd = _nav_btn("分析结果")
        btn_log = _nav_btn("运行日志")

        for b in (btn_home, btn_proj, btn_auto, btn_fun, btn_doc, btn_fnd, btn_log):
            nav_bar.addWidget(b)
        nav_bar.addStretch(1)

        stack = QtWidgets.QStackedWidget()
        
        # --- Page 0: Home ---
        page_home = QtWidgets.QWidget()
        lh = QtWidgets.QVBoxLayout(page_home)
        lh.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lh.setSpacing(20)
        
        lbl_hero = QtWidgets.QLabel("Qt Test AI Agent")
        lbl_hero.setStyleSheet("font-size: 36px; font-weight: 800; color: #1E293B;")
        lbl_desc = QtWidgets.QLabel("智能感知 · 自动化生成 · 深度检测 · 专业的 Qt 项目测试一站式解决方案")
        lbl_desc.setStyleSheet("font-size: 16px; color: #64748B; margin-bottom: 20px;")
        
        btn_start = QtWidgets.QPushButton("开始新项目")
        btn_start.setProperty("kind", "primary")
        btn_start.setMinimumSize(160, 48)
        btn_start.setStyleSheet("font-size: 16px; border-radius: 24px;")
        btn_start.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        lh.addWidget(lbl_hero, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        lh.addWidget(lbl_desc, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
        lh.addWidget(btn_start, 0, QtCore.Qt.AlignmentFlag.AlignCenter)

        # --- Page 1: Project ---
        page_proj = QtWidgets.QWidget()
        lp = QtWidgets.QVBoxLayout(page_proj)
        lp.setContentsMargins(8, 8, 8, 8)
        lp.setSpacing(10)
        lp.addWidget(project_group)
        
        # === Configuration Group ===
        self.config_group = QtWidgets.QGroupBox("⚙️ 高级配置")
        cg_layout = QtWidgets.QFormLayout(self.config_group)
        cg_layout.setContentsMargins(12, 16, 12, 12)
        cg_layout.setSpacing(10)
        
        self.cfg_llm_base = QtWidgets.QLineEdit()
        self.cfg_llm_base.setPlaceholderText("https://api.openai.com/v1")
        self.cfg_llm_model = QtWidgets.QLineEdit()
        self.cfg_llm_model.setPlaceholderText("gpt-3.5-turbo")
        self.cfg_llm_key = QtWidgets.QLineEdit()
        self.cfg_llm_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        
        self.cfg_auto_enable = QtWidgets.QCheckBox("启用自动化测试 (QtTest / 覆盖率)")
        
        # Generation Limits
        self.cfg_limit_files = QtWidgets.QSpinBox()
        self.cfg_limit_files.setRange(1, 20)
        self.cfg_limit_files.setValue(2)
        self.cfg_limit_cases = QtWidgets.QSpinBox()
        self.cfg_limit_cases.setRange(1, 100)
        self.cfg_limit_cases.setValue(10)
        
        cg_layout.addRow("LLM API Base:", self.cfg_llm_base)
        cg_layout.addRow("LLM Model:", self.cfg_llm_model)
        cg_layout.addRow("LLM API Key:", self.cfg_llm_key)
        cg_layout.addRow("", self.cfg_auto_enable)
        cg_layout.addRow("生成文件数限制:", self.cfg_limit_files)
        cg_layout.addRow("生成用例数限制:", self.cfg_limit_cases)
        
        btn_save_cfg = QtWidgets.QPushButton("保存配置")
        btn_save_cfg.setProperty("kind", "primary")
        btn_save_cfg.clicked.connect(self._save_config_from_ui)
        cg_layout.addRow("", btn_save_cfg)
        
        lp.addWidget(self.config_group)
        lp.addStretch(1) # Stretch to push items up

        # Initialize config UI with current env vars
        self._load_config_to_ui()

        # Initialize config UI with current env vars
        self._load_config_to_ui()

        # --- Page 2: Automation ---
        page_auto = QtWidgets.QWidget()
        la = QtWidgets.QVBoxLayout(page_auto)
        la.setContentsMargins(8, 8, 8, 8)
        la.setSpacing(16)
        
        # Action button
        la.addWidget(self.automation_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        
        # Info card with styled sections
        info_card = QtWidgets.QGroupBox("📋 自动化测试说明")
        info_layout = QtWidgets.QVBoxLayout(info_card)
        info_layout.setSpacing(12)
        info_layout.setContentsMargins(16, 20, 16, 16)
        
        # Section 1: Overview
        lbl_overview = QtWidgets.QLabel(
            "<p style='color: #64748B; line-height: 1.6;'>"
            "自动化阶段默认<b>不会自动运行</b>。如需在\"一键运行\"中启用，请在\"项目配置\"页面勾选 "
            "<span style='background: #F1F5F9; color: #0F172A; padding: 2px 6px; border-radius: 4px;'>启用自动化测试</span>。"
            "</p>"
        )
        lbl_overview.setWordWrap(True)
        lbl_overview.setTextFormat(QtCore.Qt.TextFormat.RichText)
        info_layout.addWidget(lbl_overview)
        
        # Section 2: Note
        lbl_note = QtWidgets.QLabel(
            "<p style='background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 10px; border-radius: 6px; color: #92400E; line-height: 1.6;'>"
            "<b>💡 注意：</b>本工具<b>不会</b>替你改动工程构建配置，仅负责调度命令并采集输出。"
            "</p>"
        )
        lbl_note.setWordWrap(True)
        lbl_note.setTextFormat(QtCore.Qt.TextFormat.RichText)
        info_layout.addWidget(lbl_note)
        
        la.addWidget(info_card)
        
        # Configuration card
        config_card = QtWidgets.QGroupBox("🔧 命令配置")
        config_layout = QtWidgets.QFormLayout(config_card)
        config_layout.setSpacing(10)
        config_layout.setContentsMargins(16, 20, 16, 16)
        
        self.auto_test_cmd = QtWidgets.QLineEdit()
        self.auto_test_cmd.setPlaceholderText("例：make test 或 ctest --output-on-failure")
        
        self.auto_coverage_cmd = QtWidgets.QLineEdit()
        self.auto_coverage_cmd.setPlaceholderText("例：gcovr --xml coverage.xml")
        
        config_layout.addRow("测试命令:", self.auto_test_cmd)
        config_layout.addRow("覆盖率命令:", self.auto_coverage_cmd)
        
        btn_save_auto = QtWidgets.QPushButton("💾 保存命令配置")
        btn_save_auto.setProperty("kind", "primary")
        btn_save_auto.clicked.connect(self._save_automation_config)
        config_layout.addRow("", btn_save_auto)
        
        la.addWidget(config_card)
        
        # Load current values
        self.auto_test_cmd.setText(os.getenv("QT_TEST_AI_TEST_CMD", ""))
        self.auto_coverage_cmd.setText(os.getenv("QT_TEST_AI_COVERAGE_CMD", ""))
        
        la.addStretch(1)

        # --- Page 3: Functional ---
        page_fun = QtWidgets.QWidget()
        lf = QtWidgets.QVBoxLayout(page_fun)
        lf.setContentsMargins(8, 8, 8, 8)
        lf.setSpacing(12)
        
        # Add intro section
        func_intro = QtWidgets.QLabel(
            "<p style='color: #64748B; font-size: 13px; margin-bottom: 8px;'>"
            "📝 <b>功能测试用例管理</b> — 定义、执行和跟踪黑盒功能测试用例"
            "</p>"
        )
        func_intro.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lf.addWidget(func_intro)
        
        lf.addWidget(self.functional_table)
        func_btns = QtWidgets.QHBoxLayout()
        func_btns.addWidget(self.functional_add_btn)
        func_btns.addWidget(self.functional_del_btn)
        func_btns.addWidget(self.functional_load_btn)
        func_btns.addWidget(self.functional_save_btn)
        func_btns.addWidget(self.functional_reset_btn)
        func_btns.addWidget(self.functional_llm_btn)
        func_btns.addWidget(self.functional_sync_btn)
        func_btns.addStretch(1)
        lf.addLayout(func_btns)

        # --- Page 4: Findings (Dashboard) ---
        page_fnd = QtWidgets.QWidget()
        lfi = QtWidgets.QVBoxLayout(page_fnd)
        lfi.setContentsMargins(8, 8, 8, 8)
        lfi.setSpacing(16)
        
        # Add header
        fnd_header = QtWidgets.QLabel(
            "<p style='color: #1E293B; font-size: 15px; font-weight: 600; margin-bottom: 4px;'>"
            "📊 测试分析仪表板"
            "</p>"
        )
        fnd_header.setTextFormat(QtCore.Qt.TextFormat.RichText)
        lfi.addWidget(fnd_header)
        
        self.summary_widget = SummaryWidget()
        lfi.addWidget(self.summary_widget)
        lfi.addWidget(self.table)
        lfi.addWidget(self.llm_summary_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)

        # --- Page 5: Document Check ---
        page_doc = QtWidgets.QWidget()
        ldoc = QtWidgets.QVBoxLayout(page_doc)
        ldoc.setContentsMargins(8, 8, 8, 8)
        ldoc.setSpacing(12)
        
        doc_header = QtWidgets.QLabel(
            "<p style='color: #1E293B; font-size: 15px; font-weight: 600; margin-bottom: 4px;'>"
            "📄 文档检查 — 检测项目文档完整性与一致性"
            "</p>"
        )
        doc_header.setTextFormat(QtCore.Qt.TextFormat.RichText)
        ldoc.addWidget(doc_header)
        
        # Document list
        self.doc_list = QtWidgets.QListWidget()
        self.doc_list.setAlternatingRowColors(True)
        self.doc_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        ldoc.addWidget(self.doc_list, 1)
        
        # Buttons
        doc_btns = QtWidgets.QHBoxLayout()
        self.doc_scan_btn = QtWidgets.QPushButton("🔍 扫描文档")
        self.doc_scan_btn.setProperty("kind", "secondary")
        self.doc_scan_btn.clicked.connect(self._scan_docs)
        
        self.doc_llm_check_btn = QtWidgets.QPushButton("🤖 LLM 一致性检查")
        self.doc_llm_check_btn.setProperty("kind", "primary")
        self.doc_llm_check_btn.clicked.connect(self._run_llm_doc_check)
        
        doc_btns.addWidget(self.doc_scan_btn)
        doc_btns.addWidget(self.doc_llm_check_btn)
        doc_btns.addStretch(1)
        ldoc.addLayout(doc_btns)
        
        # Results table
        doc_results_label = QtWidgets.QLabel("<b>检查结果：</b>")
        ldoc.addWidget(doc_results_label)
        
        self.doc_results_table = QtWidgets.QTableWidget()
        self.doc_results_table.setColumnCount(3)
        self.doc_results_table.setHorizontalHeaderLabels(["严重程度", "问题标题", "详情"])
        self.doc_results_table.horizontalHeader().setStretchLastSection(True)
        self.doc_results_table.setAlternatingRowColors(True)
        ldoc.addWidget(self.doc_results_table, 2)

        # --- Page 6: Log ---
        page_log = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(page_log)
        ll.setContentsMargins(8, 8, 8, 8)
        ll.setSpacing(10)
        ll.addWidget(self.log)

        for p in (page_home, page_proj, page_auto, page_fun, page_doc, page_fnd, page_log):
            stack.addWidget(p)

        def switch_to(idx: int):
            stack.setCurrentIndex(idx)
            for i, b in enumerate((btn_home, btn_proj, btn_auto, btn_fun, btn_doc, btn_fnd, btn_log)):
                b.setChecked(i == idx)

        btn_home.clicked.connect(lambda: switch_to(0))
        btn_proj.clicked.connect(lambda: switch_to(1))
        btn_auto.clicked.connect(lambda: switch_to(2))
        btn_fun.clicked.connect(lambda: switch_to(3))
        btn_doc.clicked.connect(lambda: switch_to(4))
        btn_fnd.clicked.connect(lambda: switch_to(5))
        btn_log.clicked.connect(lambda: switch_to(6))
        
        btn_start.clicked.connect(lambda: switch_to(1))
        
        switch_to(0)

        left_widget = QtWidgets.QWidget()
        left = QtWidgets.QVBoxLayout(left_widget)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(10)
        left.addWidget(header)
        left.addWidget(sub)
        left.addLayout(nav_bar)
        left.addWidget(stack, 1)

        history_group = QtWidgets.QGroupBox("历史记录（SQLite）")
        rg = QtWidgets.QVBoxLayout(history_group)
        rg.setContentsMargins(12, 14, 12, 12)
        rg.setSpacing(8)
        rg.addWidget(self.history, 1)
        rg.addWidget(self.refresh_history_btn)
        rg.addWidget(self.load_history_btn)
        rg.addWidget(self.delete_history_btn)

        right_widget = QtWidgets.QWidget()
        right = QtWidgets.QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)
        right.addWidget(history_group, 1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setHandleWidth(6)

        grid = QtWidgets.QVBoxLayout(central)
        grid.setContentsMargins(22, 22, 22, 22)
        grid.addWidget(splitter, 1)

        # state
        self._last_run: TestRun | None = None

        # signals
        self.project_btn.clicked.connect(self._pick_project)
        self.exe_btn.clicked.connect(self._pick_exe)
        self.run_btn.clicked.connect(self._run_all)
        self.export_btn.clicked.connect(self._export)
        self.automation_btn.clicked.connect(self._run_automation_only)
        self.functional_load_btn.clicked.connect(self._load_functional_library)
        self.functional_save_btn.clicked.connect(self._save_functional_library)
        self.functional_add_btn.clicked.connect(self._add_functional_row)
        self.functional_del_btn.clicked.connect(lambda: self._delete_selected_rows(self.functional_table))
        self.refresh_history_btn.clicked.connect(self._refresh_history)
        self.load_history_btn.clicked.connect(self._load_selected_history)
        self.delete_history_btn.clicked.connect(self._delete_selected_history)

        self._refresh_history()
        self._log(f"数据库：{self._db_path}")

        self._llm_cfg = load_llm_config_from_env()
        self._llm_system_prompt = load_llm_system_prompt_from_env()
        self._apply_llm_button_state()

        self._apply_visual_polish()
        self._apply_card_shadows([project_group, self.functional_table, self.table, self.log, history_group])

    def _load_config_to_ui(self):
        self.cfg_llm_base.setText(os.getenv("QT_TEST_AI_LLM_BASE_URL", ""))
        self.cfg_llm_model.setText(os.getenv("QT_TEST_AI_LLM_MODEL", ""))
        self.cfg_llm_key.setText(os.getenv("QT_TEST_AI_LLM_API_KEY", ""))
        self.cfg_auto_enable.setChecked(_env_flag("QT_TEST_AI_ENABLE_AUTOMATION"))
        
        try:
            self.cfg_limit_files.setValue(int(os.getenv("QT_TEST_AI_TESTGEN_FILE_LIMIT", "2")))
        except:
            self.cfg_limit_files.setValue(2)
            
        try:
            self.cfg_limit_cases.setValue(int(os.getenv("QT_TEST_AI_TESTGEN_CASE_LIMIT", "10")))
        except:
            self.cfg_limit_cases.setValue(10)

    def _save_config_from_ui(self):
        os.environ["QT_TEST_AI_LLM_BASE_URL"] = self.cfg_llm_base.text().strip()
        os.environ["QT_TEST_AI_LLM_MODEL"] = self.cfg_llm_model.text().strip()
        os.environ["QT_TEST_AI_LLM_API_KEY"] = self.cfg_llm_key.text().strip()
        
        if self.cfg_auto_enable.isChecked():
            os.environ["QT_TEST_AI_ENABLE_AUTOMATION"] = "1"
        else:
            if "QT_TEST_AI_ENABLE_AUTOMATION" in os.environ:
                del os.environ["QT_TEST_AI_ENABLE_AUTOMATION"]
                
        os.environ["QT_TEST_AI_TESTGEN_FILE_LIMIT"] = str(self.cfg_limit_files.value())
        os.environ["QT_TEST_AI_TESTGEN_CASE_LIMIT"] = str(self.cfg_limit_cases.value())
        
        QtWidgets.QMessageBox.information(self, "保存成功", "环境变量已更新（当前会话有效）。")

    def _save_automation_config(self):
        os.environ["QT_TEST_AI_TEST_CMD"] = self.auto_test_cmd.text().strip()
        os.environ["QT_TEST_AI_COVERAGE_CMD"] = self.auto_coverage_cmd.text().strip()
        
        QtWidgets.QMessageBox.information(self, "保存成功", "自动化命令配置已更新（当前会话有效）。")


    def _show_selected_finding_details(self) -> None:
        if not self._last_run:
            return
        row = self.table.currentRow()
        if row < 0 or row >= len(self._last_run.findings):
            return
        f = self._last_run.findings[row]
        details = (f.details or "").strip()
        if not details:
            details = "（无详细输出）"
        self._log("=" * 24)
        self._log(f"发现项详情：{f.category} | {f.severity} | {f.title}")
        if f.file:
            self._log(f"文件：{f.file}")
        self._log(details)

    def _apply_llm_button_state(self) -> None:
        enabled = self._llm_cfg is not None
        tip = (
            "未检测到 LLM 配置。请设置环境变量：QT_TEST_AI_LLM_BASE_URL / QT_TEST_AI_LLM_MODEL / (可选)QT_TEST_AI_LLM_API_KEY"
            if not enabled
            else ""
        )
        for b in (self.functional_llm_btn, self.llm_summary_btn):
            b.setEnabled(enabled and (b is not self.llm_summary_btn))
            if tip:
                b.setToolTip(tip)

    def _apply_visual_polish(self) -> None:
        # Prefer system UI font; only bump size slightly for readability.
        font = self.font() or QtGui.QFont()
        if font.pointSize() <= 0:
            font.setPointSize(9)
        else:
            font.setPointSize(max(font.pointSize(), 9))
        self.setFont(font)

        for t in (self.functional_table, self.table):
            t.setSortingEnabled(False)
            t.setWordWrap(True)
            t.setCornerButtonEnabled(False)
            t.horizontalHeader().setHighlightSections(False)
            t.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            # t.verticalHeader().setDefaultSectionSize(36) 
            # Fix: Auto-resize rows to fit wrapped text so it doesn't get cut off
            t.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            t.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
            t.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
            # Revert manual font sizing for table content to keep it standard
            
        # 更大可视空间：功能用例按列权重分配宽度
        fh = self.functional_table.horizontalHeader()
        fh.setStretchLastSection(False)
        fh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        fh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        fh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        fh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        fh.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        fh.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        fh.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Stretch)
        fh.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        fh.setMinimumSectionSize(120)
        
        self.log.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        # Use a readable monospace if available; fallback to default.
        self.log.setFont(QtGui.QFont("Consolas", max(self.font().pointSize(), 9)))

    def _apply_card_shadows(self, widgets: list[QtWidgets.QWidget]) -> None:
        for w in widgets:
            effect = QtWidgets.QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(15)
            effect.setXOffset(0)
            effect.setYOffset(3)
            effect.setColor(QtGui.QColor(0, 0, 0, 30))
            w.setGraphicsEffect(effect)

    def closeEvent(self, event):
        try:
            self._conn.close()
        except Exception:
            pass
        return super().closeEvent(event)

    def _log(self, msg: str) -> None:
        self.log.appendPlainText(msg)

    def _pick_project(self) -> None:
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择 Qt 项目根目录")
        if d:
            self.project_edit.setText(d)

    def _pick_exe(self) -> None:
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择被测 exe（可选）", filter="Executable (*.exe)")
        if f:
            self.exe_edit.setText(f)

    def _run_automation_only(self) -> None:
        if not _env_flag("QT_TEST_AI_ENABLE_AUTOMATION"):
            QtWidgets.QMessageBox.information(
                self,
                "未启用自动化",
                "请先设置环境变量 QT_TEST_AI_ENABLE_AUTOMATION=1，然后再运行。\n\n"
                "可选：配置 QT_TEST_AI_TEST_CMD / QT_TEST_AI_COVERAGE_CMD 来接入你们的测试/覆盖率工具链。",
            )
            return
        self._run_all()

    def _init_functional_table(self, cases: list[FunctionalCase]) -> None:
        self.functional_table.setRowCount(0)
        self.functional_table.setRowCount(len(cases))
        for r, c in enumerate(cases):
            self.functional_table.setItem(r, 0, QtWidgets.QTableWidgetItem(c.case_id))
            self.functional_table.setItem(r, 1, QtWidgets.QTableWidgetItem(c.title))
            self.functional_table.setItem(r, 2, QtWidgets.QTableWidgetItem("\n".join(c.steps)))
            self.functional_table.setItem(r, 3, QtWidgets.QTableWidgetItem(c.expected))
            self.functional_table.setItem(r, 4, QtWidgets.QTableWidgetItem(""))

            combo = QtWidgets.QComboBox()
            combo.addItem("通过", "pass")
            combo.addItem("失败", "fail")
            combo.addItem("阻塞", "blocked")
            combo.addItem("不适用", "na")
            combo.setCurrentIndex(0)
            self.functional_table.setCellWidget(r, 5, combo)

            self.functional_table.setItem(r, 6, QtWidgets.QTableWidgetItem(""))
            self.functional_table.setItem(r, 7, QtWidgets.QTableWidgetItem(""))

        # 让“定义列”更像用例库：ID/用例/步骤/预期可编辑（用于维护用例库）
        # 实际/证据/备注/结果用于每次运行记录

    def _add_functional_row(self) -> None:
        r = self.functional_table.rowCount()
        self.functional_table.insertRow(r)
        for col in (0, 1, 2, 3, 4, 6, 7):
            self.functional_table.setItem(r, col, QtWidgets.QTableWidgetItem(""))

        combo = QtWidgets.QComboBox()
        combo.addItem("通过", "pass")
        combo.addItem("失败", "fail")
        combo.addItem("阻塞", "blocked")
        combo.addItem("不适用", "na")
        combo.setCurrentIndex(0)
        self.functional_table.setCellWidget(r, 5, combo)

    def _delete_selected_rows(self, table: QtWidgets.QTableWidget) -> None:
        rows = sorted({i.row() for i in table.selectionModel().selectedIndexes()}, reverse=True)
        if not rows:
            return
        for r in rows:
            table.removeRow(r)

    def _collect_functional_entries(self) -> list[dict]:
        entries: list[dict] = []
        for r in range(self.functional_table.rowCount()):
            def _txt(col: int) -> str:
                it = self.functional_table.item(r, col)
                return it.text().strip() if it else ""

            cid = _txt(0)
            title = _txt(1)
            steps_raw = _txt(2)
            steps = [s.strip() for s in steps_raw.splitlines() if s.strip()]
            expected = _txt(3)
            actual = _txt(4)

            combo = self.functional_table.cellWidget(r, 5)
            status = "pass"
            if isinstance(combo, QtWidgets.QComboBox):
                status = str(combo.currentData())

            evidence = _txt(6)
            note = _txt(7)

            if not cid and not title:
                continue
            entries.append(
                {
                    "id": cid,
                    "title": title,
                    "steps": steps,
                    "expected": expected,
                    "actual": actual,
                    "status": status,
                    "evidence": evidence,
                    "note": note,
                }
            )
        return entries

    def _collect_functional_library_cases(self) -> list[FunctionalCase]:
        cases: list[FunctionalCase] = []
        for r in range(self.functional_table.rowCount()):
            cid_it = self.functional_table.item(r, 0)
            title_it = self.functional_table.item(r, 1)
            steps_it = self.functional_table.item(r, 2)
            expected_it = self.functional_table.item(r, 3)

            cid = cid_it.text().strip() if cid_it else ""
            title = title_it.text().strip() if title_it else ""
            steps_raw = steps_it.text() if steps_it else ""
            steps = [s.strip() for s in steps_raw.splitlines() if s.strip()]
            expected = expected_it.text().strip() if expected_it else ""

            if cid and title:
                cases.append(FunctionalCase(case_id=cid, title=title, steps=steps, expected=expected))
        return cases

    def _load_functional_library(self) -> None:
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "加载功能用例库(JSON)", filter="JSON (*.json)")
        if not f:
            return
        try:
            cases = load_case_library(Path(f))
            self._init_functional_table(cases)
            self._log(f"已加载用例库：{f}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "加载失败", str(e))

    def _save_functional_library(self) -> None:
        f, _ = QtWidgets.QFileDialog.getSaveFileName(self, "保存功能用例库(JSON)", filter="JSON (*.json)")
        if not f:
            return
        try:
            cases = self._collect_functional_library_cases()
            save_case_library(Path(f), cases)
            self._log(f"已保存用例库：{f}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "保存失败", str(e))

    def _reset_functional_library(self) -> None:
        self._init_functional_table(default_case_library())
        self._log("已重置为默认功能用例")

    def _run_all(self) -> None:
        project = self.project_edit.text().strip()
        if not project:
            QtWidgets.QMessageBox.warning(self, "缺少参数", "请选择项目目录")
            return

        project_root = Path(project)
        if not project_root.exists():
            QtWidgets.QMessageBox.warning(self, "路径无效", "项目目录不存在")
            return

        exe = self.exe_edit.text().strip()
        exe_path = Path(exe) if exe else None

        self.run_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.table.setRowCount(0)
        self._log("开始运行…")
        functional_entries = self._collect_functional_entries()

        opts = RunOptions(
            project_root=project_root,
            exe_path=exe_path,
            enable_ui_probe=self.ui_probe_chk.isChecked(),
            functional_entries=functional_entries,
        )
        self._thread = QtCore.QThread(self)
        self._worker = Worker(opts)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._log)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_finished(self, run: TestRun) -> None:
        self._last_run = run
        rid = dbmod.save_run(self._conn, run)
        self._log(f"完成：已保存记录 id={rid}")
        self._render_findings(run)
        self.export_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        if self._llm_cfg is not None:
            self.llm_summary_btn.setEnabled(True)
        self._refresh_history()

    def _llm_run_async(self, *, title: str, messages: list[dict], on_ok) -> None:
        if self._llm_cfg is None:
            QtWidgets.QMessageBox.information(self, "LLM 未配置", "请先设置环境变量后再使用 LLM 功能。")
            return

        self._log(f"{title}…")

        class _LLMWorker(QtCore.QObject):
            finished = QtCore.Signal(object, object)  # (text, err)

            def __init__(self, cfg):
                super().__init__()
                self.cfg = cfg

            @QtCore.Slot()
            def run(self):
                try:
                    text = chat_completion_text(self.cfg, messages=messages)
                    self.finished.emit(text, None)
                except Exception as e:
                    self.finished.emit(None, e)

        thread = QtCore.QThread(self)
        worker = _LLMWorker(self._llm_cfg)
        worker.moveToThread(thread)

        def _done(text, err):
            thread.quit()
            worker.deleteLater()
            thread.deleteLater()
            if err is not None:
                self._log(f"LLM 调用失败：{err}")
                QtWidgets.QMessageBox.warning(self, "LLM 调用失败", str(err))
                return
            on_ok(str(text))

        thread.started.connect(worker.run)
        worker.finished.connect(_done)
        thread.start()

    def _llm_generate_functional(self) -> None:
        project = self.project_edit.text().strip()
        proj_hint = f"项目目录：{project}" if project else ""
        sys_prompt = self._llm_system_prompt or "你是软件测试助手。只输出严格JSON，不要输出多余文字。"

        # 尝试基于项目文件构建“项目上下文”，让 LLM 生成更贴合实际功能的用例
        ctx = ""
        if project:
            try:
                pr = Path(project)
                if pr.exists():
                    ctx_obj = build_project_context(pr)
                    # build_project_context 返回 ProjectContext（对象），这里转成字符串给 LLM
                    try:
                        ctx = json.dumps(ctx_obj, ensure_ascii=False, indent=2, default=str)
                    except Exception:
                        ctx = str(ctx_obj)
            except Exception as e:
                # 不影响功能；只记录日志
                self._log(f"构建项目上下文失败：{e}")


        user_prompt = (
            "请**基于下面给出的项目源代码上下文**，生成一份 Qt 桌面应用的【功能测试用例库】。"

            "只输出一个 JSON 数组（不要输出多余文字）。数组每项是一个对象，字段必须包含："

            "- id: 用例编号（建议 F001/F002…）"
            "- title: 用例标题（简短清晰）"
            "- steps: 字符串数组，每一步是可执行的用户操作（尽量具体到按钮/菜单/快捷键/输入）"
            "- expected: 预期结果（可验证、可观察）"
            "要求："
            "1) 覆盖主窗口、核心对话框/页面、常用菜单/工具栏、典型输入校验、异常提示、撤销/重做、文件打开/保存等（结合项目实际）。"
            "2) 尽量采用黑盒方式描述控件定位：如“点击 ‘查找’ 按钮”、“在标题为 xxx 的输入框输入…”。"
            "3) 给出 12~25 条高质量用例，避免空泛（如“正常使用”）。"
            "4) 如果上下文里出现 Find/Replace、Diagram/Scene、Open/Save 等关键功能，请务必覆盖。"
            + ("\n" + proj_hint if proj_hint else "")
            + ("\n\n=== 项目上下文（只用于生成用例）===\n" + ctx if ctx else "")
        )
        messages = [
            {
                "role": "system",
                "content": sys_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

        def on_ok(text: str):
            import json

            try:
                items = json.loads(text)
            except Exception:
                QtWidgets.QMessageBox.warning(self, "解析失败", "LLM 返回的不是有效 JSON。")
                return
            if not isinstance(items, list):
                QtWidgets.QMessageBox.warning(self, "解析失败", "LLM 返回的 JSON 不是数组。")
                return

            cases: list[FunctionalCase] = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                cid = str(it.get("id") or "").strip()
                title = str(it.get("title") or "").strip()
                steps_raw = it.get("steps") or []
                steps = [str(x).strip() for x in steps_raw if str(x).strip()]
                expected = str(it.get("expected") or "").strip()
                if cid and title:
                    cases.append(FunctionalCase(case_id=cid, title=title, steps=steps, expected=expected))

            if not cases:
                QtWidgets.QMessageBox.warning(self, "生成结果为空", "LLM 没有生成有效用例。")
                return
            self._init_functional_table(cases)
            self._log("LLM 已生成功能用例库（可继续手动编辑/增删）。")

            # ============================
            # 自动保存功能测试用例库（JSON）
            # ============================
            try:
                if project:
                    out_dir = Path(project) / "test_reports" / "functional_cases"
                else:
                    tool_root = Path(__file__).resolve().parents[2]
                    out_dir = tool_root / "reports" / "functional_cases"
                
                out_dir.mkdir(parents=True, exist_ok=True)

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                project_name = Path(project).name if project else "project"
                out_path = out_dir / f"functional_cases_{project_name}_{ts}.json"

                payload = []
                for c in cases:
                    payload.append(
                        {
                            "id": c.case_id,
                            "title": c.title,
                            "steps": c.steps,
                            "expected": c.expected,
                        }
                    )

                out_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                self._log(f"✅ 功能测试用例已自动保存：{out_path}")

            except Exception as e:
                self._log(f"⚠️ 自动保存功能用例失败：{e}")

        self._llm_run_async(title="LLM 生成功能用例", messages=messages, on_ok=on_ok)

    def _reset_functional_table(self) -> None:
        """
        Reset the functional table to the default case library.
        """
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认重置",
            "确定要重置功能测试用例库吗？\n当前表格中未保存的修改将会丢失。",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._init_functional_table(default_case_library())
            self._log("已重置功能测试用例库为默认状态。")

    def _llm_sync_from_qtest(self) -> None:
        """
        Scan [project]/tests directory for .cpp files, read them, 
        and ask LLM to reverse-engineer functional test cases.
        """
        project = self.project_edit.text().strip()
        if not project:
            QtWidgets.QMessageBox.warning(self, "错误", "请先在项目配置页设置有效路径")
            return
        
        proj_root = Path(project)
        if not proj_root.exists():
            QtWidgets.QMessageBox.warning(self, "错误", "项目路径不存在")
            return
        
        # Scan for C++ test files
        # Look in tests/auto, tests/ or just tests
        candidates = []
        for p in proj_root.glob("tests/**/*.cpp"):
            if "build" in p.parts: continue
            candidates.append(p)
            
        if not candidates:
            QtWidgets.QMessageBox.information(self, "未找到测试代码", "在 tests/ 目录下未找到 .cpp 文件，无法导入。")
            return
        
        # Limit context size
        context_str = ""
        used_files = []
        for p in candidates[:5]: # limit to first 5 files to avoid token overflow
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                context_str += f"\n=== File: {p.relative_to(proj_root)} ===\n{content}\n"
                used_files.append(p.name)
            except Exception:
                pass
                
        if not context_str:
            return

        sys_prompt = self._llm_system_prompt or "你是软件测试助手。只输出严格JSON，不要输出多余文字。"
        user_prompt = (
            "请阅读下面的 QTest/C++ 单元测试代码，尝试将其“反向工程”为自然语言的功能测试用例。\n"
            "只输出一个 JSON 数组，每项包含：\n"
            "- id: 建议编号(如 AUTO-001)\n"
            "- title: 用例标题\n"
            "- steps: 操作步骤列表(根据代码逻辑推断)\n"
            "- expected: 预期结果(根据 QVERIFY/QCOMPARE 推断)\n"
            "代码上下文：\n"
            f"{context_str}"
        )
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        def on_ok(text: str):
            import json
            try:
                items = json.loads(text)
                if not isinstance(items, list): raise ValueError("Not a list")
                
                cases = []
                for it in items:
                    if not isinstance(it, dict): continue
                    cases.append(FunctionalCase(
                        case_id=str(it.get("id") or "AUTO-?"),
                        title=str(it.get("title") or "未命名自动用例"),
                        steps=[str(s) for s in it.get("steps") or []],
                        expected=str(it.get("expected") or "")
                    ))
                
                if cases:
                    self._init_functional_table(cases)
                    self._log(f"✅ 已从 QTest 代码导入 {len(cases)} 条功能用例。")
                    QtWidgets.QMessageBox.information(self, "导入成功", f"已导入 {len(cases)} 条用例。请别忘了点击‘保存’。")
                else:
                    self._log("LLM 未返回有效用例。")
            except Exception as e:
                self._log(f"解析失败: {e}")
                QtWidgets.QMessageBox.warning(self, "解析失败", f"LLM 返回无法解析: {e}")

        self._llm_run_async(title="从 QTest 代码导入", messages=messages, on_ok=on_ok)

    def _llm_summarize_last_run(self) -> None:
        if not self._last_run:
            return

        run = self._last_run
        if run.meta is None:
            run.meta = {}
        # 控制长度：只发摘要和前若干条发现项
        findings = []
        for f in run.findings[:25]:
            findings.append(
                {
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "file": f.file,
                    "line": f.line,
                }
            )

        payload = {
            "summary": run.summary_counts(),
            "project_root": run.project_root,
            "exe_path": run.exe_path,
            "functional_cases": (run.meta or {}).get("functional_cases") or [],
            "automation": (run.meta or {}).get("automation") or {},
            "testgen": (run.meta or {}).get("testgen") or {},
            "tests": (run.meta or {}).get("tests") or {},
            "coverage": (run.meta or {}).get("coverage") or {},
            "top_findings": findings,
        }

        import json

        sys_prompt = self._llm_system_prompt or "你是软件测试助手。请用中文输出：结论、主要风险、建议修复优先级、建议回归点。"
        messages = [
            {
                "role": "system",
                "content": sys_prompt,
            },
            {
                "role": "user",
                "content": "请基于以下测试结果 JSON 生成一段可直接放入测试报告的总结：\n" + json.dumps(payload, ensure_ascii=False),
            },
        ]

        def on_ok(text: str):
            (run.meta or {}).setdefault("llm", {})
            run.meta["llm"]["summary"] = text
            self._log("LLM 总结：\n" + text)
            self._log("（已写入本次运行 meta，导出报告会包含）")

        self._llm_run_async(title="LLM 生成测试总结", messages=messages, on_ok=on_ok)

    def _render_findings(self, run: TestRun) -> None:
        self.table.setRowCount(0)
        
        # Stats for dashboard
        total = len(run.findings)
        err = 0
        warn = 0
        
        for f in run.findings:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(f.category))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(f.severity))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(f.title))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(f.file or ""))
            
            if f.severity == "error":
                err += 1
            elif f.severity == "warning":
                warn += 1
        
        # Calculate functional pass rate (if functional tests exist)
        pass_rate = "N/A"
        functional = (run.meta or {}).get("functional_cases") or []
        if functional:
            passed = sum(1 for c in functional if c.get("status") == "pass")
            total_cases = len(functional)
            if total_cases > 0:
                pass_rate = f"{int(passed / total_cases * 100)}%"
        
        self.summary_widget.update_stats(total, err, warn, pass_rate)

    def _export(self) -> None:
        if not self._last_run:
            return
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "选择导出目录")
        if not out_dir:
            return
        out = Path(out_dir)
        ts = self._last_run.created_at.strftime("%Y%m%d_%H%M%S")
        html_path = out / f"qt_test_report_{ts}.html"
        json_path = out / f"qt_test_report_{ts}.json"
        write_html(self._last_run, html_path)
        write_json(self._last_run, json_path)
        self._log(f"已导出：{html_path}")
        self._log(f"已导出：{json_path}")

    def _refresh_history(self) -> None:
        self.history.clear()
        for rid, created_at, project_root, exe_path in dbmod.list_runs(self._conn, limit=50):
            self.history.addItem(f"#{rid} {created_at.strftime('%Y-%m-%d %H:%M:%S')} | {project_root} | {exe_path or ''}")

    def _load_selected_history(self) -> None:
        item = self.history.currentItem()
        if not item:
            return
        m = item.text().split(" ", 1)[0]
        if not m.startswith("#"):
            return
        rid = int(m[1:])
        run = dbmod.load_run(self._conn, rid)
        self._last_run = run
        self._render_findings(run)
        self._restore_functional_from_run(run)
        self.export_btn.setEnabled(True)
        self._log(f"已加载历史记录 id={rid}")

    def _delete_selected_history(self) -> None:
        item = self.history.currentItem()
        if not item:
            QtWidgets.QMessageBox.warning(self, "提示", "请先选择一条历史记录")
            return
        m = item.text().split(" ", 1)[0]
        if not m.startswith("#"):
            return
        rid = int(m[1:])
        
        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self, "确认删除",
            f"确定要删除历史记录 #{rid} 吗？此操作不可撤销。",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            if dbmod.delete_run(self._conn, rid):
                self._log(f"已删除历史记录 id={rid}")
                self._refresh_history()
            else:
                self._log(f"删除失败：未找到记录 id={rid}")

    def _scan_docs(self) -> None:
        """Scan project directory for documentation files."""
        project = self.project_edit.text().strip()
        if not project:
            QtWidgets.QMessageBox.warning(self, "错误", "请先在项目配置页设置有效路径")
            return
        
        proj_root = Path(project)
        if not proj_root.exists():
            QtWidgets.QMessageBox.warning(self, "错误", "项目路径不存在")
            return
        
        self.doc_list.clear()
        doc_paths = []
        
        # Check standard doc names
        for name in ("README.md", "readme.md", "README.txt", "使用说明.md", "用户手册.md"):
            p = proj_root / name
            if p.exists():
                doc_paths.append(p)
        
        # Check docs/ directory
        docs_dir = proj_root / "docs"
        if docs_dir.exists() and docs_dir.is_dir():
            for p in docs_dir.rglob("*.md"):
                doc_paths.append(p)
            for p in docs_dir.rglob("*.txt"):
                doc_paths.append(p)
        
        # Check for .doc/.docx files with "文档" in name
        for p in proj_root.rglob("*.doc*"):
            if "文档" in p.name and p.is_file():
                doc_paths.append(p)
        
        # Also check root level .doc files
        for p in proj_root.glob("*.doc*"):
            if p.is_file() and p not in doc_paths:
                doc_paths.append(p)
        
        # Deduplicate and sort
        doc_paths = sorted(set(doc_paths), key=lambda x: str(x).lower())
        
        for p in doc_paths:
            try:
                rel = p.relative_to(proj_root)
            except ValueError:
                rel = p.name
            self.doc_list.addItem(f"{rel}")
        
        self._log(f"扫描到 {len(doc_paths)} 个文档文件")
        self._cached_doc_paths = doc_paths  # Cache for LLM check

    def _run_llm_doc_check(self) -> None:
        """Run LLM consistency check on project documentation."""
        project = self.project_edit.text().strip()
        if not project:
            QtWidgets.QMessageBox.warning(self, "错误", "请先在项目配置页设置有效路径")
            return
        
        if not hasattr(self, '_cached_doc_paths') or not self._cached_doc_paths:
            QtWidgets.QMessageBox.warning(self, "提示", "请先点击'扫描文档'按钮")
            return
        
        if not self._llm_cfg:
            QtWidgets.QMessageBox.warning(self, "错误", "未配置 LLM，请在项目配置中设置 LLM 参数")
            return
        
        proj_root = Path(project)
        
        # Read document content
        from .utils import read_text_best_effort
        doc_content = ""
        for dp in self._cached_doc_paths[:3]:  # Limit
            if dp.suffix in [".md", ".txt"]:
                doc_content += f"\n=== {dp.name} ===\n"
                doc_content += read_text_best_effort(dp)[:3000]
        
        if not doc_content.strip():
            QtWidgets.QMessageBox.warning(self, "提示", "未能读取文档内容（仅支持 .md/.txt 文件）")
            return
        
        # Get project context
        ctx = build_project_context(proj_root)
        project_context = ctx.prompt_text if ctx else ""
        
        self._log("正在运行 LLM 文档一致性检查...")
        
        # Run LLM check
        findings = run_llm_doc_checks(proj_root, self._llm_cfg, doc_content, project_context)
        
        # Display results
        self.doc_results_table.setRowCount(len(findings))
        for i, f in enumerate(findings):
            self.doc_results_table.setItem(i, 0, QtWidgets.QTableWidgetItem(f.severity))
            self.doc_results_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f.title))
            self.doc_results_table.setItem(i, 2, QtWidgets.QTableWidgetItem(f.details or ""))
        
        self.doc_results_table.resizeColumnsToContents()
        
        if findings:
            self._log(f"✅ LLM 文档检查完成，发现 {len(findings)} 个问题")
        else:
            self._log("✅ LLM 文档检查完成，未发现一致性问题")

    def _restore_functional_from_run(self, run: TestRun) -> None:
        functional = (run.meta or {}).get("functional_cases") or []
        if not functional:
            return
        if self.functional_table.rowCount() != len(functional):
            # 以历史记录为准重建行
            cases = []
            for c in functional:
                cases.append(
                    FunctionalCase(
                        case_id=str(c.get("id") or ""),
                        title=str(c.get("title") or ""),
                        steps=[str(x) for x in (c.get("steps") or [])],
                        expected=str(c.get("expected") or ""),
                    )
                )
            self._init_functional_table(cases)

        for r, c in enumerate(functional[: self.functional_table.rowCount()]):
            # 定义列
            self.functional_table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(c.get("id") or "")))
            self.functional_table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(c.get("title") or "")))
            self.functional_table.setItem(
                r,
                2,
                QtWidgets.QTableWidgetItem("\n".join([str(x) for x in (c.get("steps") or [])])),
            )
            self.functional_table.setItem(r, 3, QtWidgets.QTableWidgetItem(str(c.get("expected") or "")))
            # 运行记录列
            self.functional_table.setItem(r, 4, QtWidgets.QTableWidgetItem(str(c.get("actual") or "")))
            combo = self.functional_table.cellWidget(r, 5)
            if isinstance(combo, QtWidgets.QComboBox):
                status = c.get("status")
                for i in range(combo.count()):
                    if combo.itemData(i) == status:
                        combo.setCurrentIndex(i)
                        break
            self.functional_table.setItem(r, 6, QtWidgets.QTableWidgetItem(str(c.get("evidence") or "")))
            self.functional_table.setItem(r, 7, QtWidgets.QTableWidgetItem(str(c.get("note") or "")))



def run_app() -> int:
    # High DPI scaling
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication([])

    # Use Fusion as base
    app.setStyle(QtWidgets.QStyleFactory.create("Fusion"))

    # Custom modern palette (Light/Professional Theme)
    # Using a "Stripe-like" or "Tailwind-like" color system: Slate/Blue/White.
    p = app.palette()
    p.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor("#F8FAFC"))       # Slate-50
    p.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor("#0F172A"))   # Slate-900
    p.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor("#FFFFFF"))
    p.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#F1F5F9")) # Slate-100
    p.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor("#1E293B"))
    p.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor("#F8FAFC"))
    p.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor("#0F172A"))
    p.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor("#FFFFFF"))
    p.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor("#0F172A"))
    p.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor("#EF4444"))   # Red-500
    p.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor("#2563EB"))         # Blue-600
    p.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor("#2563EB"))
    p.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#FFFFFF"))
    app.setPalette(p)

    # Global Font
    font = QtGui.QFont("Segoe UI", 9) # Reduced from 10
    font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # Modern Premium QSS - Compact Version
    app.setStyleSheet(
        """
        /* --- GLOBAL --- */
        QWidget {
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            color: #334155;
            selection-background-color: #3B82F6;
            selection-color: #ffffff;
            font-size: 13px; /* Reduced from 14px */
        }
        
        QMainWindow {
            background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0 #F8FAFC, stop:1 #E2E8F0);
        }
        QWidget#HeroSection {
            background-color: rgba(255, 255, 255, 0.6);
            border-radius: 20px;
        }
        QLabel[role='header'] { font-size: 19px; font-weight: 700; color: palette(window-text); padding: 2px 0; background: transparent; }
        QLabel[role='subheader'] { color: palette(mid); padding-bottom: 8px; background: transparent; }

        QGroupBox {
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid palette(midlight);
            border-radius: 12px;
            margin-top: 12px;
            padding-top: 6px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: #0F172A;
            font-weight: 700;
            font-size: 12px;
        }

        /* --- INPUTS --- */
        QLineEdit, QComboBox, QPlainTextEdit, QListWidget {
            background: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 6px 10px; /* Reduced padding */
            color: #1E293B;
        }
        QLineEdit:hover, QComboBox:hover, QPlainTextEdit:hover {
            border: 1px solid #94A3B8;
        }
        QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus {
            border: 2px solid #3B82F6;
            outline: none;
        }
        QPlainTextEdit {
            font-family: 'Consolas', 'Cascadia Code', monospace;
            background: #F8FAFC; 
            line-height: 1.3;
        }

        /* --- TABLES --- */
        QTableWidget {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 6px;
            gridline-color: transparent;
            outline: none;
        }
        QTableWidget::item {
            padding: 4px 6px; /* Reduced from 6px 10px */
            border-bottom: 1px solid #F1F5F9;
        }
        QTableWidget::item:selected {
            background-color: #EFF6FF;
            color: #1E40AF;
        }
        QTableWidget::item:hover {
            background-color: #F8FAFC;
        }
        QHeaderView::section {
            background-color: #FFFFFF;
            color: #64758B;
            text-transform: uppercase;
            font-weight: 700;
            font-size: 11px;
            border: none;
            border-bottom: 2px solid #E2E8F0;
            padding: 6px;
        }
        QTableWidget QComboBox {
             margin: 0px;
             padding: 2px;
             border: none;
             background: transparent;
        }

        /* --- BUTTONS --- */
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            color: #334155;
            padding: 6px 12px; /* Reduced */
            border-radius: 6px;
            font-weight: 600;
            min-width: 60px;
        }
        QPushButton:hover {
            background-color: #F8FAFC;
            border-color: #94A3B8;
            color: #0F172A;
        }
        QPushButton:pressed {
            background-color: #E2E8F0;
            padding-top: 8px;
            padding-bottom: 4px;
        }
        
        QPushButton[kind='primary'] {
            background-color: #3B82F6;
            border: 1px solid #2563EB;
            color: #FFFFFF;
        }
        QPushButton[kind='primary']:hover {
            background-color: #2563EB;
            border-color: #1D4ED8;
        }
        QPushButton[kind='primary']:pressed {
            background-color: #1D4ED8;
            border-color: #1E3A8A;
        }

        /* --- NAVIGATION SIDEBAR --- */
        QPushButton[kind='nav'] {
            background: transparent;
            border: 1px solid transparent;
            text-align: left;
            padding: 8px 12px;
            color: #64748B;
            font-weight: 500;
            border-radius: 6px;
            margin-bottom: 2px;
            font-size: 13px;
        }
        QPushButton[kind='nav']:hover {
            background-color: #F1F5F9;
            color: #334155;
        }
        QPushButton[kind='nav']:checked {
            background-color: #EFF6FF;
            color: #2563EB;
            font-weight: 700;
            border: 1px solid #DBEAFE;
        }
        
        /* --- SCROLLBARS --- */
        QScrollBar:vertical {
            border: none;
            background: transparent;
            width: 8px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #CBD5E1;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #94A3B8;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        
        QSplitter::handle {
            background: #E2E8F0;
            width: 1px;
        }
        """
    )
    w = MainWindow()
    w.show()
    return app.exec()
