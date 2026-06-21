import os
import time
from modules import api_config, token_monitor

def generar_metadatos_youtube(m_titulo, guion_completo, ruta_guardado):
    """
    Toma el guion generado del manga y usa Gemini para crear el Titulo, Descripcion
    y Etiquetas optimas para YouTube, gurdandolo en un archivo de texto.
    """
    print("\n[ Marketing ] Generando metadatos SEO para YouTube...")
    
    prompt_marketing = (
        f"Acabo de crear un resumen narrado en video para el manga/anime '{m_titulo}'. "
        "A continuacion te presento el guion completo del video. Tu tarea es actuar como un "
        "experto en crecimiento de YouTube y SEO, y generar los metadatos perfectos para maximizar "
        "la retencion y el CTR (Click-Through Rate).\n\n"
        "DEVUELVE EXACTAMENTE EL SIGUIENTE FORMATO (sin markdown adicional):\n"
        "TITULO: [Un titulo muy clickbait pero real, intrigante, de menos de 65 caracteres, en español]\n"
        "DESCRIPCION: [Una descripcion SEO de 2 o 3 parrafos cortos invitando a suscribirse, resumiendo la premisa sin spoilers]\n"
        "ETIQUETAS: [15 etiquetas separadas por comas, ej: #manga, #resumen anime, #shonen]\n\n"
        f"--- GUION DEL VIDEO ---\n{guion_completo}\n--- FIN DEL GUION ---"
    )

    intentos = 0
    provider = api_config.obtener_ia_provider()
    while intentos < 5:
        modelo = api_config.nombre_modelo_ia()
        
        try:
            texto_resultado = ""
            if provider == "ollama":
                import ollama
                response = ollama.generate(
                    model=modelo,
                    prompt=prompt_marketing,
                    stream=False
                )
                texto_resultado = response['response']
                print(f"[+] Metadatos SEO generados con Ollama ({modelo}).")
            else:
                client = api_config.obtener_cliente_gemini()
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt_marketing
                )
                texto_resultado = response.text
                print(f"[+] Metadatos SEO generados con Gemini ({modelo}).")
            
            # Guardamos el resultado en un archivo txt al lado del video
            with open(ruta_guardado, "w", encoding="utf-8") as f:
                f.write(texto_resultado)
                
            print(f"[+] Metadatos SEO guardados en: {ruta_guardado}")
            return True
            
        except Exception as e:
            error_str = str(e)
            if provider == "gemini" and ("429" in error_str or "RESOURCE_EXHAUSTED" in error_str):
                print(f"[!] Cuota agotada en {modelo} durante generacion SEO. Buscando proxima key...")
                if token_monitor.validar_acceso_gemini():
                    intentos += 1
                    time.sleep(1)
                    continue
                else:
                    print("\n[ADVERTENCIA] No quedan cuotas para generar el archivo de Metadatos SEO. Saltando paso.")
                    return False
            else:
                 print(f"Error generando metadatos SEO ({provider}): {e}")
                 return False
                 
    return False
