with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if '"prob_local": round(sim' in line:
        start = max(0, i-15)
        print("--- linea", i+1, "---")
        for j in range(start, min(len(lines), i+10)):
            print(str(j+1).rjust(4) + ": " + lines[j], end="")
        break
