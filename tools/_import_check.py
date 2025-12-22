import traceback
try:
    import src.qt_test_ai.test_automation as ta
    print('Imported test_automation OK')
except Exception:
    traceback.print_exc()
