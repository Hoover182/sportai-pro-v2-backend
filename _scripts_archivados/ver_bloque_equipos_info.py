with open("app/services/player_model.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "equipos_info.append" in line:
        start = max(0, i-3)
        for j in range(start, min(len(lines), i+3)):
            print(str(j+1).rjust(4) + ": " + repr(lines[j]))
