with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '"tarjetas_ou"' in line and "sim" in "".join(lines[max(0,i-2):i+3]):
        # Verificar que es dentro de get_analisis_partido buscando tarjetas_proj cerca
        contexto = "".join(lines[max(0,i-30):i+10])
        if "tarjetas_proj" in contexto:
            start = max(0, i-3)
            print("--- tarjetas_ou en linea", i+1, "---")
            for j in range(start, min(len(lines), i+12)):
                print(str(j+1).rjust(4) + ": " + lines[j], end="")
            break
