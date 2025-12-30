import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(os.getcwd())

from src.qt_test_ai.llm_test_generator import LLMTestGenerator
from dotenv import load_dotenv

def main():
    load_dotenv()
    # Initialize generator
    # Note: The project root for the generator should be the target project, not the tool project
    target_project_root = Path(r"C:\Users\lenovo\Desktop\Diagramscene_ultima-syz")
    generator = LLMTestGenerator(target_project_root)

    # Define target file
    test_file = target_project_root / "tests" / "generated" / "test_phase_1diagramitem.cpp"
    target_file = "diagramitem.cpp"

    print(f"Testing file: {test_file}")
    print(f"Target coverage file: {target_file}")

    # Run compile and test
    # We need to ensure the file exists
    if not test_file.exists():
        print(f"Error: Test file not found: {test_file}")
        return

    # Force clean build by removing object files
    import shutil
    debug_dir = test_file.parent / "debug"
    if debug_dir.exists():
        for file in debug_dir.glob("*.o"):
            try:
                file.unlink()
            except:
                pass

    result = generator.compile_and_test(test_file, target_file_hint=target_file)

    print("\nResult:")
    print(f"Success: {result['success']}")
    print("--- Output ---")
    print(result['output'])
    if not result['success']:
        print("--- Errors ---")
        print(result['errors'])
    
    if 'coverage' in result:
        print(f"Coverage Data: {result['coverage']}")
        if isinstance(result['coverage'], dict):
             print(f"Line Coverage: {result['coverage'].get('line_coverage')}%")
             print(f"Summary: {result['coverage'].get('summary')}")
    else:
        print("No coverage data found.")

    # Explicitly show per-file coverage for the target file
    print(f"\n--- Detailed Coverage for {target_file} ---")
    import subprocess
    try:
        # We are in the tool root, but we need to run gcovr from the tests/generated directory
        # and point to the project root
        tests_dir = target_project_root / "tests" / "generated"
        
        # Construct gcovr command to filter for the specific file
        # -r ../.. : root is 2 levels up
        # . : search for .gcda files in current dir
        # -f : filter regex
        # Use python -m gcovr to ensure we use the installed module
        cmd = [
            sys.executable, "-m", "gcovr", 
            "-r", "../..", 
            ".", 
            "-f", f".*{target_file.replace('.', r'\.')}"
        ]
        
        # print(f"Running: {' '.join(cmd)}")
        
        proc = subprocess.run(
            cmd,
            cwd=str(tests_dir),
            capture_output=True,
            text=True
        )
        
        print(proc.stdout)
        if proc.stderr:
            print("Errors:", proc.stderr)
            
    except Exception as e:
        print(f"Failed to run specific coverage check: {e}")

if __name__ == "__main__":
    main()
