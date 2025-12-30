from __future__ import annotations

import subprocess
import time
from pathlib import Path

import psutil

from .models import Finding
from .utils import guess_exe_candidates


def pick_exe(project_root: Path, user_exe: Path | None) -> tuple[Path | None, list[Finding], dict]:
    findings: list[Finding] = []
    meta: dict = {}

    if user_exe and user_exe.exists() and user_exe.suffix.lower() == ".exe":
        return user_exe, findings, meta

    cands = guess_exe_candidates(project_root)
    meta["exe_candidates"] = [str(c) for c in cands[:50]]
    if not cands:
        findings.append(
            Finding(
                category="dynamic",
                severity="error",
                title="未找到可执行文件 .exe",
                details="请选择被测程序 exe，或确认项目已构建（常见目录 build/debug/release）。",
            )
        )
        return None, findings, meta

    findings.append(
        Finding(
            category="dynamic",
            severity="info",
            title="已自动选择候选 exe",
            details=str(cands[0]),
        )
    )
    return cands[0], findings, meta



def run_smoke_test(exe_path: Path, workdir: Path | None = None, timeout_sec: int = 15) -> tuple[list[Finding], dict]:
    """
    冒烟测试（Smoke Test）：
    - 验证应用是否能正常启动；
    - 监控 CPU、内存使用；
    - 检查是否异常退出；
    - 输出简要性能指标。
    """
    findings: list[Finding] = []
    meta: dict = {"exe": str(exe_path), "timeout_sec": timeout_sec}

    if not exe_path.exists():
        return [Finding(category="dynamic", severity="error", title="exe 不存在", details=str(exe_path))], meta

    try:
        proc = subprocess.Popen(
            [str(exe_path)],
            cwd=str(workdir) if workdir else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as e:
        return [Finding(category="dynamic", severity="error", title="启动失败", details=str(e))], meta

    start_time = time.time()
    alive_ok = False
    startup_time = None
    cpu_samples, mem_samples = [], []

    try:
        p = psutil.Process(proc.pid)
        p.cpu_percent(interval=None)  # 初始化CPU采样
    except psutil.NoSuchProcess:
        p = None

    # 主检测循环（启动+资源采样）
    while time.time() - start_time < timeout_sec:
        if proc.poll() is not None:  # 进程退出
            break
        alive_ok = True
        if startup_time is None:
            startup_time = time.time() - start_time

        if p:
            try:
                cpu = p.cpu_percent(interval=0.2)
                mem = p.memory_info().rss / 1024 / 1024
                cpu_samples.append(cpu)
                mem_samples.append(mem)
            except psutil.NoSuchProcess:
                break
        else:
            time.sleep(0.2)

        if len(cpu_samples) >= 5:  # 收集够样本即可
            break

    # 整理结果
    meta.update({
        "alive": alive_ok,
        "cpu_samples": cpu_samples,
        "memory_samples_mb": mem_samples,
        "returncode": proc.poll(),
        "startup_time_s": round(startup_time or 0, 2),
        "duration_s": round(time.time() - start_time, 2)
    })

    # 分析结果
    if not alive_ok:
        rc = proc.poll()

        # Detect common Windows NT status for entrypoint not found: 0xC0000139
        ENTRYPOINT_NOT_FOUND_DEC = 3221225785
        if rc == ENTRYPOINT_NOT_FOUND_DEC:
            findings.append(Finding(category="dynamic", severity="error",
                                    title="进程启动失败：入口点未找到（0xC0000139）",
                                    details="返回码 0xC0000139，通常表示加载的 DLL 与可执行版本不兼容或缺少运行时/Qt DLL。建议确保 PATH 中包含与构建匹配的 Qt 和 MinGW 运行时目录，或在构建机器上部署所需 DLL。"))

            # Best-effort: try to locate a local Qt installation under common roots and retry once
            try:
                import os
                from pathlib import Path as _Path

                tried = False
                qt_roots = ["C:/Qt", "D:/Qt"]
                for root in qt_roots:
                    p = _Path(root)
                    if not p.exists():
                        continue
                    for ver in p.iterdir():
                        bin_dir = ver / "bin"
                        if bin_dir.exists():
                            # try launching with this bin prepended to PATH
                            env = os.environ.copy()
                            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
                            try:
                                proc2 = subprocess.Popen([str(exe_path)], cwd=str(workdir) if workdir else None,
                                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                                # wait briefly
                                try:
                                    out2, err2 = proc2.communicate(timeout=3)
                                except Exception:
                                    out2, err2 = "", ""
                                rc2 = proc2.poll()
                                findings.append(Finding(category="dynamic", severity="info",
                                                        title="已尝试使用候选 Qt bin 重启可执行文件",
                                                        details=f"使用 {bin_dir}，返回码={rc2}，stdout={out2[:400]}, stderr={err2[:400]}"))
                                tried = True
                                # stop after first attempt
                                break
                            except Exception:
                                continue
                    if tried:
                        break
                if not tried:
                    findings.append(Finding(category="dynamic", severity="info",
                                            title="未找到候选 Qt bin 以重试启动",
                                            details="请手动确认 Qt 安装路径，或在环境变量中设置 QT_BIN 或将 Qt 的 bin 目录加入 PATH。"))
            except Exception:
                pass
        else:
            findings.append(Finding(category="dynamic", severity="error",
                                    title="进程未能稳定运行",
                                    details=f"returncode={rc}（可能启动即退出或缺少依赖）"))
    else:
        findings.append(Finding(category="dynamic", severity="info",
                                title="进程启动成功", details=f"pid={proc.pid}"))
        findings.append(Finding(category="dynamic", severity="info",
                                title=f"启动响应时间 {meta['startup_time_s']} 秒",
                                details="应用成功启动并保持运行"))

        # CPU 警告
        if cpu_samples and max(cpu_samples) > 80:
            findings.append(Finding(category="dynamic", severity="warning",
                                    title="CPU 使用过高", details=f"峰值 {max(cpu_samples):.1f}%"))

        # 内存分析
        if len(mem_samples) >= 2:
            first, last = mem_samples[0], mem_samples[-1]
            growth = last - first
            if growth > 10 and growth / max(first, 1) > 0.2:
                findings.append(Finding(category="dynamic", severity="warning",
                                        title="内存增长过快",
                                        details=f"{first:.1f} → {last:.1f} MB (+{growth:.1f} MB)"))
            else:
                findings.append(Finding(category="dynamic", severity="info",
                                        title=f"内存占用 {last:.1f} MB",
                                        details=f"初始 {first:.1f} → 最终 {last:.1f} MB"))

    # 关闭进程
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=3)
    except Exception:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass

    # 采集输出日志
    try:
        out, err = proc.communicate(timeout=1)
        if out.strip():
            findings.append(Finding(category="dynamic", severity="info", title="stdout", details=out.strip()[:5000]))
        if err.strip():
            findings.append(Finding(category="dynamic", severity="warning", title="stderr", details=err.strip()[:5000]))
    except Exception:
        pass

    # 🧩 新增：总结报告信息
    meta["summary"] = {
        "status": "passed" if not any(f.severity == "error" for f in findings) else "failed",
        "warnings": sum(f.severity == "warning" for f in findings),
        "errors": sum(f.severity == "error" for f in findings)
    }

    return findings, meta



def run_windows_ui_probe(exe_path: Path, timeout_sec: int = 15) -> tuple[list[Finding], dict]:
    """可选：Windows UI Automation 探测（需要 pywinauto）。

    目标：在不改动被测 Qt 工程的前提下，尽量识别主窗口是否出现。
    """

    findings: list[Finding] = []
    meta: dict = {"exe": str(exe_path), "timeout_sec": timeout_sec}

    try:
        from pywinauto.application import Application  # type: ignore
        from pywinauto.timings import TimeoutError  # type: ignore
    except Exception as e:
        findings.append(
            Finding(
                category="dynamic",
                severity="info",
                title="未启用 Windows UI 探测（pywinauto 不可用）",
                details=str(e),
            )
        )
        return findings, meta

    try:
        start_time = time.time()
        app = Application(backend="uia").start(str(exe_path))
        try:
            win = app.top_window()
            win.wait("visible", timeout=timeout_sec)
            window_appear_time = time.time() - start_time
            
            meta["window_title"] = win.window_text()
            meta["window_appear_time_s"] = round(window_appear_time, 2)
            
            findings.append(
                Finding(
                    category="dynamic",
                    severity="info",
                    title="检测到可见窗口",
                    details=win.window_text(),
                )
            )
            
            # Report window appearance timing
            findings.append(
                Finding(
                    category="dynamic",
                    severity="info",
                    title=f"窗口显示时间: {window_appear_time:.2f}秒",
                    details=f"从启动到主窗口可见耗时 {window_appear_time:.2f} 秒"
                )
            )
            
            # Warn if startup is slow
            if window_appear_time > 5:
                findings.append(
                    Finding(
                        category="dynamic",
                        severity="warning",
                        title=f"启动较慢: {window_appear_time:.1f}秒",
                        details="窗口显示超过5秒，可能影响用户体验。建议优化启动性能。"
                    )
                )
        except TimeoutError:
            findings.append(Finding(category="dynamic", severity="warning", title="未在超时内检测到可见窗口"))
        finally:
            try:
                app.kill()
            except Exception:
                pass

    except Exception as e:
        findings.append(Finding(category="dynamic", severity="warning", title="UI 探测失败", details=str(e)))

    return findings, meta
