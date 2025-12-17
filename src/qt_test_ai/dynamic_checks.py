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

    start = time.time()
    startup_time: float | None = None  # Time to become ready
    
    # 进程可能会非常快地退出：psutil.Process / cpu_percent 会抛 NoSuchProcess
    p: psutil.Process | None = None
    try:
        p = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        p = None

    # 等待窗口/就绪：这里做通用检测（进程存活 + CPU 有活动），更深的 UI 自动化放在可选项
    alive_ok = False
    cpu_samples: list[float] = []
    memory_samples: list[dict] = []  # Memory monitoring: [{rss, vms, percent}]
    
    try:
        if p is not None:
            try:
                p.cpu_percent(interval=None)
            except psutil.NoSuchProcess:
                p = None
        while time.time() - start < timeout_sec:
            if proc.poll() is not None:
                break
            alive_ok = True
            
            # Record startup time when process first becomes alive
            if startup_time is None:
                startup_time = time.time() - start
            
            if p is not None:
                try:
                    cpu_samples.append(p.cpu_percent(interval=0.2))
                    
                    # Memory sampling
                    try:
                        mem_info = p.memory_info()
                        mem_percent = p.memory_percent()
                        memory_samples.append({
                            "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
                            "vms_mb": round(mem_info.vms / (1024 * 1024), 2),
                            "percent": round(mem_percent, 2),
                            "elapsed_s": round(time.time() - start, 2)
                        })
                    except Exception:
                        pass
                        
                except psutil.NoSuchProcess:
                    p = None
                    break
            else:
                # 无法采样（进程可能刚退出），稍等再检查一次
                time.sleep(0.2)
            if len(cpu_samples) >= 5:
                break

        meta["alive"] = alive_ok
        meta["cpu_samples"] = cpu_samples
        meta["memory_samples"] = memory_samples
        meta["returncode"] = proc.poll()
        meta["startup_time_s"] = startup_time

        if alive_ok:
            findings.append(Finding(category="dynamic", severity="info", title="进程启动成功", details=f"pid={proc.pid}"))
            
            # Report startup time
            if startup_time is not None:
                findings.append(Finding(
                    category="dynamic", 
                    severity="info", 
                    title=f"启动响应时间: {startup_time:.2f}秒",
                    details=f"从启动到进程就绪耗时 {startup_time:.2f} 秒"
                ))
            
            # Memory analysis
            if len(memory_samples) >= 2:
                first_mem = memory_samples[0]["rss_mb"]
                last_mem = memory_samples[-1]["rss_mb"]
                mem_growth = last_mem - first_mem
                mem_growth_percent = (mem_growth / first_mem * 100) if first_mem > 0 else 0
                
                meta["memory_analysis"] = {
                    "initial_rss_mb": first_mem,
                    "final_rss_mb": last_mem,
                    "growth_mb": round(mem_growth, 2),
                    "growth_percent": round(mem_growth_percent, 2)
                }
                
                # Report memory usage
                findings.append(Finding(
                    category="dynamic",
                    severity="info",
                    title=f"内存占用: {last_mem:.1f} MB (RSS)",
                    details=f"初始: {first_mem:.1f} MB → 最终: {last_mem:.1f} MB"
                ))
                
                # Warn if significant memory growth (potential leak indicator)
                if mem_growth > 10 and mem_growth_percent > 20:
                    findings.append(Finding(
                        category="dynamic",
                        severity="warning",
                        title=f"检测到内存增长: +{mem_growth:.1f} MB ({mem_growth_percent:.1f}%)",
                        details="短时间内内存增长较大，可能存在内存泄漏风险。建议使用 Valgrind/DrMemory 进一步分析。"
                    ))
        else:
            rc = proc.poll()
            details = ""
            if rc is not None:
                details = f"returncode={rc}（程序可能启动即退出/缺少依赖/资源路径错误）"
            findings.append(Finding(category="dynamic", severity="error", title="进程未稳定运行/快速退出", details=details))

    finally:
        # 尽量温和关闭
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

        try:
            out, err = proc.communicate(timeout=1)
        except Exception:
            out, err = "", ""

        if out.strip():
            findings.append(Finding(category="dynamic", severity="info", title="stdout", details=out.strip()[:5000]))
        if err.strip():
            findings.append(Finding(category="dynamic", severity="warning", title="stderr", details=err.strip()[:5000]))

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
