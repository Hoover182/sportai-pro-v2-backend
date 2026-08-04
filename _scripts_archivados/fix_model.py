with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = 'model="claude-sonnet-4-20250514"'
new = 'model="claude-haiku-4-5-20251001"'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK")
else:
    print("ERROR: no encontrado")
