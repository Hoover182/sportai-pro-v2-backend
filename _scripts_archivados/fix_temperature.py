with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '            model="claude-haiku-4-5-20251001",\n            max_tokens=400,'
new = '            model="claude-haiku-4-5-20251001",\n            max_tokens=800,\n            temperature=0.2,'

if old in content:
    content = content.replace(old, new, 1)
    print("OK: temperature bajada a 0.2")
else:
    print("ERROR: patron no encontrado")
    idx = content.find('model="claude-haiku')
    print(repr(content[idx:idx+150]))

with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
