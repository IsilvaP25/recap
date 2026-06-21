import os
import time
from modules import api_config, token_monitor

def generar_prompt_miniatura(titulo_manga, sinopsis):
    """
    Usa Gemini para generar un prompt detallado para un generador de imágenes (DALL-E, Midjourney)
    que sirva para la miniatura de YouTube basada en la historia del manga.
    """
    print(f"\n[ Miniatura ] Creando prompt visual para '{titulo_manga}'...")
    
    prompt_ia = (
        f"Actúa como un director de arte de miniaturas de YouTube. "
        f"Tu objetivo es diseñar la miniatura perfecta para un video de resumen del manga '{titulo_manga}'.\n\n"
        f"SINOPSIS DEL MANGA:\n{sinopsis}\n\n"
        "TU TAREA:\n"
        "Genera un prompt detallado en INGLÉS para un generador de imágenes como Midjourney o DALL-E 3. "
        "El prompt debe describir una escena impactante, con colores vibrantes, estilo anime de alta calidad, "
        "personajes épicos (basados en la sinopsis) y una atmósfera cinematográfica que capte el CTR.\n\n"
        "REGLAS:\n"
        "- Sé visualmente descriptivo (iluminación, composición, expresiones).\n"
        "- No uses palabras genéricas como 'cool' o 'awesome', usa términos técnicos de arte.\n"
        "- El estilo debe ser: 'Vibrant anime art style, high detail, cinematic lighting, 8k'.\n\n"
        "DEVUELVE ÚNICAMENTE EL PROMPT EN INGLÉS, sin introducciones ni etiquetas adicionales."
    )

    intentos = 0
    provider = api_config.obtener_ia_provider()
    while intentos < 5:
        modelo = api_config.nombre_modelo_ia()
        
        try:
            if provider == "ollama":
                import ollama
                response = ollama.generate(
                    model=modelo,
                    prompt=prompt_ia,
                    stream=False
                )
                print(f"[+] Prompt de miniatura generado con Ollama ({modelo}).")
                return response['response'].strip()
            else:
                client = api_config.obtener_cliente_gemini()
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt_ia
                )
                print(f"[+] Prompt de miniatura generado con Gemini ({modelo}).")
                return response.text.strip()
            
        except Exception as e:
            error_str = str(e)
            if provider == "gemini" and ("429" in error_str or "RESOURCE_EXHAUSTED" in error_str):
                if token_monitor.validar_acceso_gemini():
                    intentos += 1
                    time.sleep(1)
                    continue
                else:
                    return "Error: No hay cuotas para generar el prompt."
            else:
                 return f"Error en generación visual ({provider}): {e}"
                 
    return "Error: Máximo de reintentos alcanzado."
