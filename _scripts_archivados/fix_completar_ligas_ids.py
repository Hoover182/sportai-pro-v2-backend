with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '    "Liga Pro Ecuador": (242, 2026),\n}'

new = '''    "Liga Pro Ecuador": (242, 2026),
    "Primera Division Chile": (265, 2026),
    "Primera Division Uruguay": (268, 2026),
    "Primera Division Peru": (281, 2026),
    "Primera Division Venezuela": (337, 2026),
    "Primera Division Bolivia": (344, 2026),
    "Division Profesional Paraguay": (250, 2026),
    "Liga MX": (262, None),
    "MLS": (253, 2026),
    "Copa Argentina": (130, 2026),
    "Copa Chile": (267, 2026),
    "Copa Colombia": (241, 2026),
    "Copa Uruguay": (270, 2026),
    "Copa do Brasil": (73, 2026),
    "Recopa Sudamericana": (12, 2026),
    "Mundial 2026": (1, 2026),
}'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: LIGAS_IDS completado con todas las ligas")
else:
    print("ERROR: no encontrado")
