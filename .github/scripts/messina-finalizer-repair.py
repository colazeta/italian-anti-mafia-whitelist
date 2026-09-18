from pathlib import Path

workflow = Path('.github/workflows/messina-integration-finalizer.yml').read_text()
marker = "        run: |\n"
if workflow.count(marker) != 1:
    raise SystemExit('Expected exactly one finalizer run block')
body = workflow.split(marker, 1)[1]
lines = body.splitlines()
script_lines = []
for line in lines:
    if line.startswith('          '):
        script_lines.append(line[10:])
    elif not line.strip():
        script_lines.append('')
    else:
        raise SystemExit(f'Unexpected finalizer indentation: {line!r}')
script = '\n'.join(script_lines) + '\n'

old = """marker = 'milano-applicants,'
i = s.find(marker)
if i < 0:
    raise SystemExit('Milano source-series insertion anchor missing')
s = s[:i] + rows + s[i:]
"""
new = """# Append the two evidence-backed Messina series. Ordering is not a schema invariant;
# uniqueness and authority/page references remain validated by the registry tests.
s = s.rstrip('\\n') + '\\n' + rows
"""
if script.count(old) != 1:
    raise SystemExit(f'Expected one stale Milano source-series anchor, found {script.count(old)}')
script = script.replace(old, new, 1)

old = "obj['authorities']"
new = "obj['prefectures']"
if script.count(old) != 1:
    raise SystemExit(f'Expected one stale national coverage collection key, found {script.count(old)}')
script = script.replace(old, new, 1)

Path('/tmp/messina-finalizer.sh').write_text(script)
