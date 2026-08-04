with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
inicio = None
for i, line in enumerate(lines):
    if "LIGAS_IDS = {" in line:
        inicio = i
    if inicio is not None and line.strip() == "}":
        print("Bloque LIGAS_IDS: linea", inicio+1, "a", i+1)
        for j in range(max(inicio, i-5), i+1):
            print(str(j+1).rjust(4) + ": " + lines[j], end="")
        break
