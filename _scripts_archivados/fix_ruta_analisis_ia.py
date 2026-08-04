with open("app/services/analisis_ia_diario_completo.py", "r", encoding="utf-8") as f:
    content = f.read()

old = 'CSV = "futbol_partidos.csv"'
new = 'import os\nCSV = os.path.join(os.path.dirname(__file__), "futbol_partidos.csv")'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/analisis_ia_diario_completo.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: ruta del CSV corregida a ruta absoluta")
else:
    print("ERROR: no encontrado")
