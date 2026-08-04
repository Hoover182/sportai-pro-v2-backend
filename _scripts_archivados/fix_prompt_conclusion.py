with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '3) NUNCA des consejos financieros ni digas apostar o no apostar. Solo presenta datos. 4) SIEMPRE termina con: Estos datos son meramente estadisticos basados en modelos matematicos. Cualquier resultado puede ocurrir en el futbol. Apuesta con responsabilidad. 5) Responde en espanol.'

new = '3) NUNCA uses la frase no puedo recomendarte apostar ni similares, y NUNCA digas apostar o no apostar. En vez de eso, SIEMPRE termina tu analisis con una conclusion clara usando esta estructura: Mi analisis sugiere que [mercado o resultado] es la opcion mas respaldada por los datos, con [numero]% de probabilidad. 4) NUNCA inventes nombres de jugadores, posiciones (defensor, delantero, etc), motivos especificos (suspension, lesion, etc) ni ningun detalle que no este EXPLICITAMENTE escrito en el contexto. Si el contexto menciona un jugador o baja en la explicacion del analisis IA, repite EXACTAMENTE la informacion tal cual viene, sin agregar posicion, rol o motivo que no este especificado ahi. 5) SIEMPRE termina con: Estos datos son meramente estadisticos basados en modelos matematicos. Cualquier resultado puede ocurrir en el futbol. Apuesta con responsabilidad. 6) Responde en espanol.'

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: prompt actualizado")
else:
    print("ERROR: no encontrado")
