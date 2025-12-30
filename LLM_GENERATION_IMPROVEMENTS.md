# LLM Test Generation Improvements

## Overview
The `LLMTestGenerator` has been upgraded to ensure that future test generations produce high-coverage, robust C++ tests.

## Key Changes

### 1. Source Code Context Injection
The generator now automatically reads the relevant source files (`.h` and `.cpp`) for the requested task and injects them into the prompt. This allows the LLM to:
- See the exact class structure, methods, and member variables.
- Understand the logic it needs to test.
- Identify edge cases based on the actual implementation.

### 2. High Coverage Instructions
A set of "CRITICAL INSTRUCTIONS" is now appended to every prompt, demanding:
- **Branch Coverage**: Explicit instruction to cover all if/else and switch cases.
- **Edge Cases**: Mandatory checks for null pointers, empty lists, and boundaries.
- **State Verification**: Requirement to use `QVERIFY`/`QCOMPARE` instead of just calling methods.
- **Real Environment**: Instruction to use real `QGraphicsScene` for item tests.
- **Qt Specifics**: Checks for `type()`, `itemChange()`, `paint()`, etc.

### 3. Enhanced Test Wrapper
The generated test files now automatically include:
- `<QGraphicsScene>`
- `<QGraphicsView>`
- `<QGraphicsItem>`
This ensures that tests involving graphics items compile correctly without manual intervention.

## How to Use
Simply run the generation command as before:
```bash
python main.py --task phase1_diagram_item --llm-service auto
```
The system will now produce significantly better tests.

## Verified Files
- `src/qt_test_ai/llm_test_generator.py`: Modified to implement the above logic.
