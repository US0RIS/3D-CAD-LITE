from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else 'v1.1/base').resolve()

def one(s,old,new,label):
    if old not in s:raise SystemExit(f'anchor missing: {label}')
    return s.replace(old,new,1)

p=root/'core.py';s=p.read_text(encoding='utf-8');s=one(s,'import physical_components\n','import physical_components\nimport system_validation\n','system validation import');s=one(s,'def reality_check() -> dict[str,Any]:\n    return physical_components.reality_check(PROJECT)','def reality_check() -> dict[str,Any]:\n    return system_validation.validate_system(PROJECT)','reality system validation');p.write_text(s,encoding='utf-8')

p=root/'server.py';s=p.read_text(encoding='utf-8');anchor='''@app.get("/api/reality-check")\ndef reality_check():return core.reality_check()\n''';replacement=anchor+'''@app.get("/api/system-check")\ndef system_check():return core.reality_check()\n''';s=one(s,anchor,replacement,'system check route');s=s.replace('"reality_check":"/api/reality-check"','"reality_check":"/api/reality-check","system_check":"/api/system-check"');p.write_text(s,encoding='utf-8')
print('integrated system validation')
