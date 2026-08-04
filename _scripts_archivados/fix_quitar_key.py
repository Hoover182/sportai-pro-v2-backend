with open("app/services/analisis_ia_diario_completo.py", "r", encoding="utf-8") as f:
    content = f.read()

old = 'API_KEY = "[KEY_REMOVIDA_POR_SEGURIDAD]"'
new = 'import os\nAPI_KEY = os.environ.get("ANTHROPIC_API_KEY", "")'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/analisis_ia_diario_completo.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: key removida del backend")
else:
    print("ERROR: no encontrado")
