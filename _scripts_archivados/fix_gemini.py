with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """def chat_ia(mensajes, contexto=""):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        system = "Eres SportAI Pro, experto en apuestas de futbol. Responde en espanol, conciso y directo."
        if contexto:
            system += "\\n\\n" + contexto
        msgs = [{"role": m["role"], "content": m["text"]} for m in mensajes if m.get("role") in ("user", "assistant")]
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=system,
            messages=msgs
        )
        return response.content[0].text, None
    except Exception as e:
        return None, str(e)"""

new = """def chat_ia(mensajes, contexto=""):
    try:
        import requests as req
        GEMINI_KEY = "AIzaSyAxDd-z422LCwUytJpS2TusLYs3frNAdXU"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
        system = "Eres SportAI Pro, experto en apuestas de futbol. Responde en espanol, conciso y directo."
        if contexto:
            system += "\\n\\n" + contexto
        parts = [{"text": system}]
        for m in mensajes:
            role = "user" if m.get("role") == "user" else "model"
            parts_msg = [{"text": m.get("text", "")}]
            parts.append({"role": role, "parts": parts_msg})
        # Gemini usa formato distinto
        contents = []
        for m in mensajes:
            role = "user" if m.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.get("text", "")}]})
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 400, "temperature": 0.7}
        }
        resp = req.post(url, json=payload, timeout=30)
        data = resp.json()
        texto = data["candidates"][0]["content"]["parts"][0]["text"]
        return texto, None
    except Exception as e:
        return None, str(e)"""

if old in content:
    content = content.replace(old, new, 1)
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK")
else:
    print("ERROR: no encontrado")
