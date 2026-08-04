with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = "        if clasico:\n            multiplicador_tarjetas += 0.20"
new = "        # NOTA: peso de clasico calibrado para futbol sudamericano (mas fisico).\n        # Si se agregan ligas europeas, este peso deberia ser mas bajo alli,\n        # ya que los derbis europeos tienden a menos tarjetas que los sudamericanos.\n        if clasico:\n            multiplicador_tarjetas += 0.35"

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: peso de clasico subido a 35% con nota sobre diferencia regional")
else:
    print("ERROR: no encontrado")
