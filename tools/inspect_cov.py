import json
p=r'C:\Users\lenovo\Desktop\Diagramscene_ultima-main\coverage.json'
obj=json.load(open(p))
print('keys:', list(obj.keys()))
files=obj.get('files') or obj.get('data') or []
print('len files', len(files))
if files:
    first=files[0]
    print('first type', type(first))
    if isinstance(first, dict):
        print('first keys', list(first.keys()))
        print('lines field type', type(first.get('lines')))
    else:
        print('first repr', repr(first)[:400])
