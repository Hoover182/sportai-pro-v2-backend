with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "def get_partidos_hoy" in line:
        for j in range(i, min(len(lines), i+35)):
            print(str(j+1).rjust(4) + ": " + lines[j], end="")
        break
