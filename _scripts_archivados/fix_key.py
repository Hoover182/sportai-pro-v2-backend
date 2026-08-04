with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = 'client = anthropic.Anthropic(api_key="[KEY_REMOVIDA_POR_SEGURIDAD]")'
new = 'client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))'

if old in content:
    content = "import os\n" + content if "import os" not in content else content
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK")
else:
    print("ERROR: no encontrado")
