with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()
idx = content.find("ultimos_visitante.append")
if idx >= 0:
    print(repr(content[idx:idx+800]))
else:
    print("No encontrado")
