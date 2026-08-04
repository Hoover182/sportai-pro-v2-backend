with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(648, 705):
    print(str(i+1).rjust(4) + ": " + lines[i], end="")
