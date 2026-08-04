with open("app/services/data_loader.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "def obtener_partidos_hoy_futbol" in line:
        for j in range(i, min(len(lines), i+35)):
            print(str(j+1).rjust(4) + ": " + lines[j], end="")
        break
