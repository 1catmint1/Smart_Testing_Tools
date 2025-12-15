from __future__ import annotations

import os

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from . import db as dbmod
from .doc_checks import run_doc_checks
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

            self.progress.emit("准备动态测试…")
            exe, f_pick, m_pick = pick_exe(self.opts.project_root, self.opts.exe_path)
            findings.extend(f_pick)
            meta["dynamic_pick"] = m_pick

            if exe is not None:
                self.progress.emit("运行动态烟测…")
                f_smoke, m_smoke = run_smoke_test(exe, workdir=self.opts.project_root)
                findings.extend(f_smoke)
                meta["dynamic_smoke"] = m_smoke

                if self.opts.enable_ui_probe:
                    self.progress.emit("运行 Windows UI 探测…")
                    f_ui, m_ui = run_windows_ui_probe(exe)
                    findings.extend(f_ui)
                    meta["dynamic_ui"] = m_ui

            # 自动化：生成测试用例 / 运行测试 / 覆盖率（可选）
            if _env_flag("QT_TEST_AI_ENABLE_AUTOMATION"):
                try:
                    from .test_automation import generate_qttest_via_llm, run_coverage_command, run_test_command

                    self.progress.emit("自动化：LLM 生成 QtTest 用例…")
                    f_gen, m_gen = generate_qttest_via_llm(self.opts.project_root)
                    findings.extend(f_gen)
                    meta["testgen"] = m_gen

                    self.progress.emit("自动化：运行测试命令…")
                    f_test, m_test = run_test_command(self.opts.project_root)
                    findings.extend(f_test)
                    meta["tests"] = m_test

                    self.progress.emit("自动化：运行覆盖率命令…")
                    f_cov, m_cov = run_coverage_command(self.opts.project_root)
                    findings.extend(f_cov)
                    meta["coverage"] = m_cov
                except Exception as e:
                    findings.append(
                        Finding(
                            category="automation",
                            severity="warning",
                            title="自动化测试/覆盖率阶段失败",
                            details=str(e),
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
        self.functional_reset_btn = QtWidgets.QPushButton("重置为默认用例")
        self.functional_load_btn.setProperty("kind", "secondary")
        self.functional_save_btn.setProperty("kind", "secondary")
        self.functional_reset_btn.setProperty("kind", "secondary")

        self.functional_add_btn = QtWidgets.QPushButton("新增用例")
        self.functional_del_btn = QtWidgets.QPushButton("删除选中")
        self.functional_add_btn.setProperty("kind", "secondary")
        self.functional_del_btn.setProperty("kind", "secondary")
        self.functional_llm_btn = QtWidgets.QPushButton("LLM 生成用例")
        self.functional_llm_btn.setProperty("kind", "secondary")
        self._init_functional_table(default_case_library())

        self.llm_summary_btn = QtWidgets.QPushButton("LLM 总结本次结果")
        self.llm_summary_btn.setProperty("kind", "secondary")
        self.llm_summary_btn.setEnabled(False)

        self.history = QtWidgets.QListWidget()
        self.history.setAlternatingRowColors(True)
        self.refresh_history_btn = QtWidgets.QPushButton("刷新历史")
        self.load_history_btn = QtWidgets.QPushButton("加载选中记录")
        self.refresh_history_btn.setProperty("kind", "secondary")
        self.load_history_btn.setProperty("kind", "secondary")

        # --- Layout (with groups) ---
        header = QtWidgets.QLabel("Qt 项目测试智能化工具")
        header.setProperty("role", "header")
        header.setWordWrap(True)
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        sub = QtWidgets.QLabel("静态/动态/文档检查 + 自动化生成测试/覆盖率 + 报告导出")
        sub.setProperty("role", "subheader")
        sub.setWordWrap(True)
        sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        project_group = QtWidgets.QGroupBox("项目与运行")
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
        nav_bar.setSpacing(8)
        nav_bar.setContentsMargins(0, 4, 0, 4)

        def _nav_btn(text: str) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(text)
            b.setCheckable(True)
            b.setProperty("kind", "nav")
            b.setMinimumHeight(34)
            return b

        btn_proj = _nav_btn("项目与运行")
        btn_auto = _nav_btn("自动化测试/覆盖率")
        btn_fun = _nav_btn("功能测试用例")
        btn_fnd = _nav_btn("发现项")
        btn_log = _nav_btn("日志")

        for b in (btn_proj, btn_auto, btn_fun, btn_fnd, btn_log):
            nav_bar.addWidget(b)
        nav_bar.addStretch(1)

        stack = QtWidgets.QStackedWidget()

        page_proj = QtWidgets.QWidget()
        lp = QtWidgets.QVBoxLayout(page_proj)
        lp.setContentsMargins(8, 8, 8, 8)
        lp.setSpacing(10)
        lp.addWidget(project_group)

        page_auto = QtWidgets.QWidget()
        la = QtWidgets.QVBoxLayout(page_auto)
        la.setContentsMargins(8, 8, 8, 8)
        la.setSpacing(10)
        la.addWidget(self.automation_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        la.addWidget(
            QtWidgets.QLabel(
                "自动化阶段默认不会自动运行。\n"
                "如需在“一键运行”中启用，请设置环境变量：QT_TEST_AI_ENABLE_AUTOMATION=1。\n\n"
                "可选：\n"
                "- QT_TEST_AI_TEST_CMD：运行测试的命令（在项目根目录执行）\n"
                "- QT_TEST_AI_COVERAGE_CMD：运行覆盖率的命令（在项目根目录执行）\n\n"
                "说明：本工具不会替你改动工程构建；仅负责调度命令并采集输出。"
            )
        )

        page_fun = QtWidgets.QWidget()
        lf = QtWidgets.QVBoxLayout(page_fun)
        lf.setContentsMargins(8, 8, 8, 8)
        lf.setSpacing(10)
        lf.addWidget(self.functional_table)
        func_btns = QtWidgets.QHBoxLayout()
        func_btns.addWidget(self.functional_add_btn)
        func_btns.addWidget(self.functional_del_btn)
        func_btns.addWidget(self.functional_load_btn)
        func_btns.addWidget(self.functional_save_btn)
        func_btns.addWidget(self.functional_reset_btn)
        func_btns.addWidget(self.functional_llm_btn)
        func_btns.addStretch(1)
        lf.addLayout(func_btns)

        page_fnd = QtWidgets.QWidget()
        lfi = QtWidgets.QVBoxLayout(page_fnd)
        lfi.setContentsMargins(8, 8, 8, 8)
        lfi.setSpacing(10)
        lfi.addWidget(self.table)
        lfi.addWidget(self.llm_summary_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)

        page_log = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(page_log)
        ll.setContentsMargins(8, 8, 8, 8)
        ll.setSpacing(10)
        ll.addWidget(self.log)

        for p in (page_proj, page_auto, page_fun, page_fnd, page_log):
            stack.addWidget(p)

        def switch_to(idx: int):
            stack.setCurrentIndex(idx)
            for i, b in enumerate((btn_proj, btn_auto, btn_fun, btn_fnd, btn_log)):
                b.setChecked(i == idx)

        btn_proj.clicked.connect(lambda: switch_to(0))
        btn_auto.clicked.connect(lambda: switch_to(1))
        btn_fun.clicked.connect(lambda: switch_to(2))
        btn_fnd.clicked.connect(lambda: switch_to(3))
        btn_log.clicked.connect(lambda: switch_to(4))
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

        right_widget = QtWidgets.QWidget()
        right = QtWidgets.QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(10)
        right.addWidget(history_group, 1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
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
        self.functional_reset_btn.clicked.connect(self._reset_functional_library)
        self.functional_add_btn.clicked.connect(self._add_functional_row)
        self.functional_del_btn.clicked.connect(lambda: self._delete_selected_rows(self.functional_table))
        self.functional_llm_btn.clicked.connect(self._llm_generate_functional)
        self.llm_summary_btn.clicked.connect(self._llm_summarize_last_run)
        self.refresh_history_btn.clicked.connect(self._refresh_history)
        self.load_history_btn.clicked.connect(self._load_selected_history)

        self._refresh_history()
        self._log(f"数据库：{self._db_path}")

        self._llm_cfg = load_llm_config_from_env()
        self._llm_system_prompt = load_llm_system_prompt_from_env()
        self._apply_llm_button_state()

        self._apply_visual_polish()
        self._apply_card_shadows([project_group, self.functional_table, self.table, self.log, history_group])

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
            font.setPointSize(10)
        else:
            font.setPointSize(max(font.pointSize(), 10))
        self.setFont(font)

        for t in (self.functional_table, self.table):
            t.setSortingEnabled(False)
            t.setWordWrap(True)
            t.setCornerButtonEnabled(False)
            t.horizontalHeader().setHighlightSections(False)
            t.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            t.verticalHeader().setDefaultSectionSize(36)
            t.setTextElideMode(QtCore.Qt.TextElideMode.ElideNone)
            t.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)

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
        self.functional_table.verticalHeader().setDefaultSectionSize(40)

        self.log.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth)
        # Use a readable monospace if available; fallback to default.
        self.log.setFont(QtGui.QFont("Consolas", max(self.font().pointSize(), 10)))

    def _apply_card_shadows(self, widgets: list[QtWidgets.QWidget]) -> None:
        for w in widgets:
            effect = QtWidgets.QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(18)
            effect.setXOffset(0)
            effect.setYOffset(4)
            effect.setColor(QtGui.QColor(0, 0, 0, 35))
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
        messages = [
            {
                "role": "system",
                "content": sys_prompt,
            },
            {
                "role": "user",
                "content": (
                    "请生成一份 Qt 桌面应用的功能测试用例库，输出 JSON 数组。"
                    "每项包含字段：id,title,steps(字符串数组),expected。"
                    + ("\n" + proj_hint if proj_hint else "")
                ),
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

        self._llm_run_async(title="LLM 生成功能用例", messages=messages, on_ok=on_ok)

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
        for f in run.findings:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(f.category))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(f.severity))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(f.title))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(f.file or ""))

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
    # 高分屏自适应
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication([])

    # Theme: Fusion + palette-driven QSS (better across Windows themes)
    app.setStyle(QtWidgets.QStyleFactory.create("Fusion"))

    app.setStyleSheet(
        """
        QMainWindow { background: palette(window); }
        QLabel[role='header'] { font-size: 19px; font-weight: 700; color: palette(window-text); padding: 2px 0; }
        QLabel[role='subheader'] { color: palette(mid); padding-bottom: 8px; }

        QGroupBox {
            background: palette(base);
            border: 1px solid palette(midlight);
            border-radius: 12px;
            margin-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 6px;
            color: palette(window-text);
            font-weight: 600;
        }

        QLineEdit, QComboBox, QPlainTextEdit, QListWidget, QTableWidget {
            background: palette(base);
            border: 1px solid palette(midlight);
            border-radius: 10px;
            padding: 10px 12px;
        }
        QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus, QTableWidget:focus {
            border: 1px solid palette(highlight);
        }
        QPlainTextEdit { font-family: Consolas, 'Segoe UI'; }

        QHeaderView::section {
            background: palette(alternate-base);
            color: palette(window-text);
            border: none;
            border-right: 1px solid palette(midlight);
            border-bottom: 1px solid palette(midlight);
            padding: 10px 8px;
            font-weight: 600;
        }
        QTableWidget::item { padding: 8px; }
        QTableWidget { gridline-color: palette(midlight); }
        QTableWidget::item:selected { background: palette(highlight); color: palette(highlighted-text); }
        QTableWidget::item:hover { background: palette(alternate-base); }

        QPushButton {
            border: 1px solid palette(midlight);
            background: palette(button);
            border-radius: 10px;
            padding: 8px 14px;
        }
        QPushButton:hover { background: palette(alternate-base); }
        QPushButton:pressed { background: palette(midlight); }
        QPushButton:disabled { color: palette(mid); }

        QPushButton[kind='primary'] {
            background: palette(highlight);
            border: 1px solid palette(highlight);
            color: palette(highlighted-text);
            font-weight: 600;
        }
        QPushButton[kind='primary']:hover { background: palette(highlight); }
        QPushButton[kind='primary']:pressed { background: palette(dark); border-color: palette(dark); }

        QPushButton[kind='secondary'] {
            background: palette(button);
            border: 1px solid palette(midlight);
            color: palette(button-text);
        }

        QSplitter::handle { background: transparent; }

        QPushButton[kind='nav'] {
            background: palette(alternate-base);
            border: 1px solid palette(midlight);
            color: palette(button-text);
            border-radius: 10px;
            padding: 8px 14px;
            font-weight: 600;
        }
        QPushButton[kind='nav']:checked {
            background: palette(base);
            border: 1px solid palette(highlight);
            color: palette(highlight);
        }
        QPushButton[kind='nav']:hover { background: palette(midlight); }
        """
    )
    w = MainWindow()
    w.show()
    return app.exec()
