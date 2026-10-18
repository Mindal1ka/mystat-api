import json

with open('openapi.json', encoding='utf-8') as f:
    spec = json.load(f)

schemas = spec.get('components', {}).get('schemas', {})
print('total schemas:', len(schemas))
for name, s in sorted(schemas.items()):
    t = s.get('type')
    props = list((s.get('properties') or {}).keys())
    req = s.get('required', [])
    enums = None
    if 'enum' in s:
        enums = s['enum']
    line = f'{name} ({t})'
    if props:
        line += ': ' + ', '.join(props[:25])
        if len(props) > 25:
            line += f' …+{len(props)-25}'
    if req:
        line += f' | required: {req}'
    print(line)
    if enums:
        print('   enum:', enums)
