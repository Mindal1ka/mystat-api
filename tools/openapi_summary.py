import json

with open('openapi.json', encoding='utf-8') as f:
    spec = json.load(f)

print('openapi:', spec.get('openapi'))
info = spec.get('info', {})
print('title:', info.get('title'))
print('version:', info.get('version'))
print('servers:', json.dumps(spec.get('servers'), ensure_ascii=False))
print('security:', json.dumps(spec.get('security'), ensure_ascii=False))
auth = spec.get('components', {}).get('securitySchemes')
if auth:
    print('securitySchemes:', json.dumps(auth, ensure_ascii=False))
print()

paths = spec.get('paths', {})
print('total paths:', len(paths))
ops = 0
tags = {}
for p, item in sorted(paths.items()):
    methods = [m for m in item if m in ('get', 'post', 'put', 'patch', 'delete')]
    ops += len(methods)
    labels = []
    for m in methods:
        o = item[m]
        oid = o.get('operationId') or o.get('summary') or '-'
        tag = (o.get('tags') or ['-'])[0]
        tags[tag] = tags.get(tag, 0) + 1
        labels.append(f'{m.upper()} {oid} [{tag}]')
    print(f'{p}  ::  ' + ' | '.join(labels))

print()
print('total operations:', ops)
print('tags:', json.dumps(tags, ensure_ascii=False, indent=1))
