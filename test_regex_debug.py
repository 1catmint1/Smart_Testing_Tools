import re

def test_regex():
    lines = [
        "QCOMPARE(item->brushColor(), newColor);",
        "QCOMPARE(item->border(), 5); // Check border",
        "item->setBorder(10);",
        "QCOMPARE(item->minSize(), QSizeF(40, 40));",
        "item->setMinSize(QSizeF(50, 50));",
        "QCOMPARE(item->grapSize(), QSizeF(150, 100));"
    ]

    bad_methods = ["border", "grapSize", "minSize", "setBorder", "brushColor", "color"]
    
    print("Testing regex logic:")
    for line in lines:
        fixed_line = line
        for bm in bad_methods:
            # Match ->bm( or .bm(
            pattern = r"(->|\.)\s*" + bm + r"\s*\("
            if re.search(pattern, fixed_line):
                 if "//" not in fixed_line:
                    fixed_line = "// " + fixed_line + f" // FIXED: Non-existent method {bm}"
        
        print(f"Original: {line}")
        print(f"Fixed:    {fixed_line}")
        print("-" * 20)

test_regex()
