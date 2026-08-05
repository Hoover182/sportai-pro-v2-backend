with open("app/services/football_model.py", encoding="utf-8") as f:
    contenido = f.read()

cp1252_map = {}
for byte_val in range(0x80, 0x100):
    try:
        char = bytes([byte_val]).decode("cp1252")
        cp1252_map[char] = byte_val
    except Exception:
        pass

def reconstruir_bytes(patron_corrupto):
    bytes_reales = []
    for c in patron_corrupto:
        if c in cp1252_map:
            bytes_reales.append(cp1252_map[c])
        elif ord(c) < 0x100:
            bytes_reales.append(ord(c))
        else:
            return None
    return bytes(bytes_reales)

patron = "\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u20ac"
b = reconstruir_bytes(patron)
print("Bytes reconstruidos:", b.hex() if b else "ERROR")

if b:
    try:
        resultado = b.decode("utf-8")
        print("Decodificado:", repr(resultado))
    except Exception as e:
        print("Error decodificando UTF-8:", e)
