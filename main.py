import os
import sys
import argparse


def _load_dotenv_if_present() -> None:
	"""Load .env from repo root if available (optional dependency)."""
	here = os.path.abspath(os.path.dirname(__file__))
	env_path = os.path.join(here, ".env")
	if not os.path.exists(env_path):
		return
	try:
		from dotenv import load_dotenv
		load_dotenv(env_path, override=False)
	except Exception:
		# .env is optional; ignore if dotenv isn't installed
		return


def _ensure_src_on_path() -> None:
	here = os.path.abspath(os.path.dirname(__file__))
	src = os.path.join(here, "src")
	if src not in sys.path:
		sys.path.insert(0, src)


def _prepend_tools_to_path() -> None:
	"""Make bundled tools available without global PATH changes."""
	here = os.path.abspath(os.path.dirname(__file__))
	tools_dir = os.path.join(here, "tools")
	if not os.path.isdir(tools_dir):
		return

	paths: list[str] = []

	# Prefer MinGW bin (gcc/g++/etc.)
	mingw_bin = os.path.join(tools_dir, "mingw64", "mingw64", "bin")
	if os.path.isdir(mingw_bin):
		paths.append(mingw_bin)

	# Prefer standalone cppcheck bundle
	cppcheck_dir = os.path.join(tools_dir, "cppcheck")
	if os.path.isdir(cppcheck_dir):
		# Common bundle layout in this repo: tools/cppcheck/PFiles/Cppcheck/cppcheck.exe
		cand = os.path.join(cppcheck_dir, "PFiles", "Cppcheck")
		if os.path.isfile(os.path.join(cand, "cppcheck.exe")):
			paths.append(cand)

	# Prepend to PATH (avoid duplicates)
	cur = os.environ.get("PATH", "")
	cur_parts = [p for p in cur.split(os.pathsep) if p]
	for p in reversed(paths):
		if p not in cur_parts:
			cur_parts.insert(0, p)
	os.environ["PATH"] = os.pathsep.join(cur_parts)


def _get_project_root() -> str:
	"""Get the Qt project root (DiagramScene)."""
	here = os.path.abspath(os.path.dirname(__file__))
	# Assuming it's a sibling: ../Diagramscene_ultima-syz
	parent = os.path.dirname(here)
	diagram_dirs = [
		os.path.join(parent, "Diagramscene_ultima-syz"),
		os.path.join(here, "..", "Diagramscene_ultima-syz"),
	]
	
	for d in diagram_dirs:
		if os.path.isdir(d) and os.path.isfile(os.path.join(d, "diagramscene.pro")):
			return d
	
	# Fallback
	return parent


def cmd_generate_tests(args) -> int:
	"""LLM 驱动的测试生成命令"""
	from pathlib import Path
	from qt_test_ai.llm_test_generator import LLMTestGenerator, interactive_llm_test_generation
	
	project_root = Path(_get_project_root())
	
	if args.task and args.llm_service:
		# 直接运行特定任务
		generator = LLMTestGenerator(project_root)
		result = generator.run_full_cycle(args.task, args.llm_service)
		
		if result["status"] == "success":
			print(f"\n✅ 任务成功: {args.task}")
			if result.get("generation", {}).get("tests_generated"):
				print(f"   生成测试数: {result['generation']['tests_generated']}")
			if result.get("compilation", {}).get("passed"):
				print(f"   通过: {result['compilation']['passed']}")
			return 0
		else:
			print(f"\n❌ 任务失败: {args.task}")
			if result.get("generation", {}).get("error"):
				print(f"   {result['generation']['error']}")
			return 1
	else:
		# 交互式模式
		interactive_llm_test_generation(project_root)
		return 0


def cmd_full_cycle(args) -> int:
	"""完整周期: 生成 -> 编译 -> 测试 -> 报告"""
	from pathlib import Path
	from qt_test_ai.llm_test_generator import LLMTestGenerator
	
	project_root = Path(_get_project_root())
	generator = LLMTestGenerator(project_root)
	
	print("\n" + "="*60)
	print("🚀 完整测试生成周期")
	print("="*60)
	
	# 使用默认任务
	task = args.task or "phase1_diagram_item"
	result = generator.run_full_cycle(task, args.llm_service or "auto")
	
	if result["status"] == "success":
		print(f"\n✅ 周期完成！")
		print(f"   任务: {task}")
		print(f"   生成测试数: {result.get('generation', {}).get('tests_generated', 0)}")
		print(f"   通过: {result.get('compilation', {}).get('passed', 0)}")
		print(f"   失败: {result.get('compilation', {}).get('failed', 0)}")
		return 0
	else:
		print(f"\n❌ 周期失败")
		import json
		print(json.dumps(result, indent=2, default=str))
		return 1


def cmd_normal_mode(args) -> int:
	"""正常模式: 启动GUI应用"""
	from qt_test_ai.app import run_app
	return run_app()


def main() -> int:
	_load_dotenv_if_present()
	_prepend_tools_to_path()
	_ensure_src_on_path()
	
	# 如果没有参数，使用交互式菜单
	if len(sys.argv) == 1:
		return _interactive_main_menu()
	
	# 使用参数解析
	parser = argparse.ArgumentParser(
		prog="Smart Testing Tools",
		description="Qt项目的智能测试工具"
	)
	
	subparsers = parser.add_subparsers(dest="command", help="可用命令")
	
	# generate 命令
	gen_parser = subparsers.add_parser("generate", help="使用LLM生成测试")
	gen_parser.add_argument(
		"-t", "--task",
		help="任务名称 (phase1_diagram_item, phase1_diagram_path, 等)",
		default=None
	)
	gen_parser.add_argument(
		"-s", "--llm-service",
		help="LLM服务 (openai, claude, auto)",
		default="auto"
	)
	gen_parser.set_defaults(func=cmd_generate_tests)
	
	# full-cycle 命令
	full_parser = subparsers.add_parser("full-cycle", help="完整测试生成周期")
	full_parser.add_argument(
		"-t", "--task",
		help="任务名称",
		default="phase1_diagram_item"
	)
	full_parser.add_argument(
		"-s", "--llm-service",
		help="LLM服务 (openai, claude, auto)",
		default="auto"
	)
	full_parser.set_defaults(func=cmd_full_cycle)
	
	# normal 命令
	normal_parser = subparsers.add_parser("normal", help="启动GUI应用")
	normal_parser.set_defaults(func=cmd_normal_mode)
	
	args = parser.parse_args()
	
	if hasattr(args, "func"):
		return args.func(args)
	else:
		# No command specified, show help and launch interactive
		parser.print_help()
		return _interactive_main_menu()


def _interactive_main_menu() -> int:
	"""交互式主菜单"""
	from qt_test_ai.llm_test_generator import interactive_llm_test_generation
	from pathlib import Path
	
	print("\n" + "="*60)
	print("🧠 Smart Testing Tools - 智能测试工具")
	print("="*60)
	print("\n主菜单:")
	print("  1. 生成测试 (LLM)")
	print("  2. 完整周期 (生成 -> 编译 -> 测试 -> 报告)")
	print("  3. 启动GUI应用")
	print("  0. 退出")
	
	try:
		choice = input("\n请选择 [1-3, 0]: ").strip()
		
		if choice == "1":
			project_root = Path(_get_project_root())
			interactive_llm_test_generation(project_root)
			return 0
		elif choice == "2":
			args = argparse.Namespace(task="phase1_diagram_item", llm_service="auto")
			return cmd_full_cycle(args)
		elif choice == "3":
			from qt_test_ai.app import run_app
			return run_app()
		elif choice == "0":
			print("\n👋 再见!")
			return 0
		else:
			print("\n❌ 无效选择")
			return 1
	
	except KeyboardInterrupt:
		print("\n\n⚠️ 操作已取消")
		return 0
	except Exception as e:
		print(f"\n❌ 发生错误: {e}")
		return 1


if __name__ == "__main__":
	raise SystemExit(main())
