import json
p=r'C:\Users\lenovo\Desktop\Diagramscene_ultima-main\coverage.json'
obj=json.load(open(p))
files=obj.get('files') or []
print('len', len(files))
if files:
    first=files[0]
    import pprint
    pprint.pprint(first)
    print('lines type', type(first.get('lines')))
    print('lines repr', repr(first.get('lines'))[:1000])
