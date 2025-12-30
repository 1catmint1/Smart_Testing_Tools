import re

def test_regex():
    lines = [
        "DiagramItem item(DiagramItem::Step);",
        "DiagramItem* item = new DiagramItem(DiagramItem::Step);",
        "DiagramItem item(DiagramItem::Step, nullptr);",
        "DiagramItem item(DiagramItem::Step, menu);"
    ]

    for line in lines:
        print(f"Original: {line}")
        try:
            # The regex from the file
            fixed_line = re.sub(r"(DiagramItem\s+[\w*]+\s*)\(([^,)]+)\)", r"\1(\2, nullptr)", line)
            print(f"Fixed 1 : {fixed_line}")
            
            fixed_line_2 = re.sub(r"(new\s+DiagramItem)\(([^,)]+)\)", r"\1(\2, nullptr)", line)
            print(f"Fixed 2 : {fixed_line_2}")
            
        except Exception as e:
            print(f"Error: {e}")
        print("-" * 20)

if __name__ == "__main__":
    test_regex()
