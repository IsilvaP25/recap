import os
import edge_tts
from modules import utils

# Definimos que usemos siempre la voz 'Alvaro' neuronal de España
VOZ_PREDETERMINADA = "es-ES-AlvaroNeural"

async def generar_audio(texto, ruta_salida):
    """
    Genera un archivo de audio MP3 narrado a partir de texto utilizando edge-tts.
    """
    try:
        # Iniciamos el objeto que hablara el texto
        comunicador = edge_tts.Communicate(texto, VOZ_PREDETERMINADA)
        
        # Guardamos a ruta asincronamente
        await comunicador.save(ruta_salida)
        return True
    except Exception as e:
        print(f"\n[ERROR] Generador de audio fallo: {e}")
        return False
