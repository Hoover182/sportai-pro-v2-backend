with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()
content = content.replace("temperature=0.2,", "temperature=0.4,")
with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
print("OK: temperature a 0.4")
