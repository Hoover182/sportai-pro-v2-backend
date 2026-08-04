with open("app/services/futbol_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# Encontrar y eliminar la funcion duplicada con TU_API_KEY_AQUI
import re
# Buscar el primer def chat_ia hasta el segundo def chat_ia
partes = content.split("def chat_ia(")
print(f"Encontradas {len(partes)-1} definiciones de chat_ia")
if len(partes) == 3:
    # Quedarse solo con la ultima (la buena con os.environ)
    content = partes[0] + "def chat_ia(" + partes[2]
    with open("app/services/futbol_service.py", "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("OK: duplicado eliminado")
else:
    print("No hay duplicado o hay mas de 2")
