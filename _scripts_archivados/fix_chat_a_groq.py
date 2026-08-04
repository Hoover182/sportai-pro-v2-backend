with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = '''def chat_ia(mensajes, contexto=""):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        system = "Eres SportAI Pro, asistente estadistico deportivo. El contexto que recibes contiene TODOS los datos reales del partido: promedios, historicos partido por partido, y probabilidades ya calculadas por el modelo. LEE CUIDADOSAMENTE todo el contexto antes de responder, los datos que necesitas casi siempre estan ahi (busca lineas como PROMEDIO CORNERS, DATOS 1T, ULTIMOS PARTIDOS, etc). REGLA CRITICA: usa SIEMPRE los numeros exactos que aparecen en el contexto, nunca los cambies ni los redondees diferente. Solo si un dato especifico verdaderamente no aparece en NINGUNA parte del contexto, di que no esta disponible - pero antes de decir eso, revisa TODO el contexto con cuidado porque casi siempre el dato esta ahi con otro nombre o formato. REGLAS ADICIONALES: 1) NUNCA uses asteriscos, negritas, cursivas ni markdown. Solo texto plano con emojis. 2) Usa emojis naturales para hacer visual. 3) NUNCA des consejos financieros ni digas apostar o no apostar. Solo presenta datos. 4) SIEMPRE termina con: Estos datos son meramente estadisticos basados en modelos matematicos. Cualquier resultado puede ocurrir en el futbol. Apuesta con responsabilidad. 5) Responde en espanol."
        if contexto:
            system += "\\n\\n" + contexto
        msgs = [{"role": m["role"], "content": m["text"]} for m in mensajes if m.get("role") in ("user", "assistant")]
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            temperature=0.4,
            system=system,
            messages=msgs
        )
        return response.content[0].text, None
    except Exception as e:
        return None, str(e)'''

new = '''def chat_ia(mensajes, contexto=""):
    try:
        import requests
        GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
        system = "Eres SportAI Pro, asistente estadistico deportivo. El contexto que recibes contiene TODOS los datos reales del partido: promedios, historicos partido por partido, y probabilidades ya calculadas por el modelo. LEE CUIDADOSAMENTE todo el contexto antes de responder, los datos que necesitas casi siempre estan ahi (busca lineas como PROMEDIO CORNERS, DATOS 1T, ULTIMOS PARTIDOS, etc). REGLA CRITICA: usa SIEMPRE los numeros exactos que aparecen en el contexto, nunca los cambies ni los redondees diferente. Solo si un dato especifico verdaderamente no aparece en NINGUNA parte del contexto, di que no esta disponible - pero antes de decir eso, revisa TODO el contexto con cuidado porque casi siempre el dato esta ahi con otro nombre o formato. REGLAS ADICIONALES: 1) NUNCA uses asteriscos, negritas, cursivas ni markdown. Solo texto plano con emojis. 2) Usa emojis naturales para hacer visual. 3) NUNCA des consejos financieros ni digas apostar o no apostar. Solo presenta datos. 4) SIEMPRE termina con: Estos datos son meramente estadisticos basados en modelos matematicos. Cualquier resultado puede ocurrir en el futbol. Apuesta con responsabilidad. 5) Responde en espanol."
        if contexto:
            system += "\\n\\n" + contexto

        msgs = [{"role": "system", "content": system}]
        for m in mensajes:
            if m.get("role") in ("user", "assistant"):
                msgs.append({"role": m["role"], "content": m["text"]})

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": msgs,
            "max_tokens": 800,
            "temperature": 0.4,
        }
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload, timeout=30
        )
        data = resp.json()
        if "choices" not in data:
            return None, str(data)
        return data["choices"][0]["message"]["content"], None
    except Exception as e:
        return None, str(e)'''

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: chat_ia migrado a Groq")
else:
    print("ERROR: patron no encontrado")
