with open("app/services/football_model.py", encoding="utf-8") as f:
    contenido = f.read()

patron_corrupto = "\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u20ac"
total = contenido.count(patron_corrupto)
contenido = contenido.replace(patron_corrupto, "\u2014")

restante = contenido.count("\u00c3") + contenido.count("\u00e2")

with open("app/services/football_model.py", "w", encoding="utf-8", newline="") as f:
    f.write(contenido)

print("Reemplazos:", total)
print("Restante:", restante)
