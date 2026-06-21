import inspect
import edge_tts.communicate
import os

print("Ubicación de edge_tts.communicate:")
print(edge_tts.communicate.__file__)

# Leer el código de Communicate
with open(edge_tts.communicate.__file__, "r", encoding="utf-8") as f:
    code = f.read()

# Buscar "Boundary"
print("\nBuscando 'Boundary' en communicate.py:")
for line_num, line in enumerate(code.splitlines(), 1):
    if "Boundary" in line or "boundary" in line:
        print(f"Línea {line_num}: {line.strip()}")
