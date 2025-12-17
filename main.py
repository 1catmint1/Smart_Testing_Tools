import os
import sys


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


def main() -> int:
	_load_dotenv_if_present()
	_prepend_tools_to_path()
	_ensure_src_on_path()
	from qt_test_ai.app import run_app

	return run_app()


if __name__ == "__main__":
	raise SystemExit(main())