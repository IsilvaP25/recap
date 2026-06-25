import os
import sys
from dotenv import load_dotenv

# Load env variables from the main project directory
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, '.env'))

from modules import database, token_monitor
from modules import db_manager
from modules.flows import downloader_flow, pdf_flow, production_flow, autopilot_flow, shorts_flow

# Añadir la carpeta raíz al path para importar el módulo 'api'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def menu_principal():
    print("\n" + "="*50)
    print("      --- PROYECTO MANGA RECAP: UNIFICADO ---")
    print("="*50)
    print("0. ABRIR INTERFAZ WEB (Recomendado para buscar)")
    print("1. BUSCAR Y DESCARGAR MANGA (WebP)")
    print("2. CONVERTIR DESCARGAS A PDF (Post-Limpieza)")
    print("3. MOTOR DE PRODUCCIÓN 3.0 (IA + Video)")
    print("4. PRODUCCIÓN AUTOMÁTICA (Todo en uno)")
    print("5. MODO SHORTS")
    print("6. Revisar Cuotas y Estado")
    print("7. LIMPIAR VIDEOS DUPLICADOS EN YOUTUBE (AUTOMÁTICO)")
    print("8. Salir")
    return input("\nSelecciona una opción: ")

def main():
    database.inicializar_db()
    db_manager.init_db()
    
    # Limpiar el pool de API keys agotadas al iniciar una nueva sesión
    session_file = os.path.join(base_dir, "temp", "exhausted_keys.json")
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
            print("  [SISTEMA] Sesión iniciada: Limpiando pool de API keys de Gemini.")
        except Exception as e:
            pass
            
    print("\n" + "="*50)
    print("      --- CONFIGURACIÓN DE SESIÓN ---")
    print("="*50)
    apagar_al_final = input("¿Deseas apagar el PC automáticamente al finalizar la tarea? (s/n): ").lower() == 's'
    if apagar_al_final:
        print("✅ [MODO AUTOMÁTICO] El PC se apagará tras completar el proceso.")
    
    while True:
        op = menu_principal()
        proceso_completado = False
        
        if op == "0":
            print("\nIniciando servidor web... Abriendo el navegador en http://127.0.0.1:5000")
            print("Para detener el servidor y volver a este menú, presiona Ctrl+C.")
            import subprocess
            import webbrowser
            import time
            webbrowser.open("http://127.0.0.1:5000")
            try:
                subprocess.run([sys.executable, "app.py"])
            except KeyboardInterrupt:
                print("\nServidor web detenido.")
        elif op == "1":
            downloader_flow.iniciar_flujo()
            proceso_completado = True
        elif op == "2":
            pdf_flow.iniciar_flujo()
            proceso_completado = True
        elif op == "3":
            production_flow.iniciar_flujo()
            proceso_completado = True
        elif op == "4":
            autopilot_flow.iniciar_flujo()
            proceso_completado = True
        elif op == "5":
            shorts_flow.iniciar_flujo(apagar_al_final)
            proceso_completado = True
        elif op == "6":
            token_monitor.consultar_cuota_actual()
            token_monitor.validar_acceso_gemini()
        elif op == "7":
            shorts_flow.iniciar_limpieza_duplicados()
            proceso_completado = True
        elif op == "8":
            print("Saliendo...")
            break

        else:
            print("Opción no válida.")

        if proceso_completado and apagar_al_final:
            print("\n" + "!"*60)
            print("  >>> TAREA FINALIZADA CON ÉXITO <<<")
            print("  El sistema se apagará en 30 segundos por solicitud previa.")
            print("  Para CANCELAR el apagado, abre CMD o PowerShell y escribe: shutdown /a")
            print("!"*60)
            os.system('shutdown /s /t 30')
            break

if __name__ == "__main__":
    main()
