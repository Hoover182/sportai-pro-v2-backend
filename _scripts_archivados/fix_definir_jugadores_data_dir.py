with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "import os"
new = 'import os\nJUGADORES_DATA_DIR = os.path.join(os.path.dirname(__file__), "jugadores_data")'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: JUGADORES_DATA_DIR definida")
else:
    print("ERROR: no encontrado")
