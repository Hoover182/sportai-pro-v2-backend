candidatos = [
    {"team": {"id": 1057, "name": "Platense FC", "country": "Honduras"}},
    {"team": {"id": 1064, "name": "Platense", "country": "Argentina"}},
]
pais_esperado = "Argentina"
for c in candidatos:
    print(repr(c["team"]["country"]), "==", repr(pais_esperado), "->", c["team"]["country"] == pais_esperado)
