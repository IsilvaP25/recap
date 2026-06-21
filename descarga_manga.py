import os
import sys
from modules import database
from modules.flows import downloader_flow, pdf_flow

def main():
    database.inicializar_db()
    
    while True:
        print("\n" + "="*50)
        print("      --- MÓDULO DE ADQUISICIÓN DE MANGA ---")
        print("="*50)
        print("1. BUSCAR Y DESCARGAR MANGA (WebP)")
        print("2. CONVERTIR DESCARGAS A PDF (Post-Limpieza)")
        print("3. Salir")
        
        op = input("\nSelecciona una opción: ")
        
        if op == "1":
            downloader_flow.iniciar_flujo()
        elif op == "2":
            pdf_flow.iniciar_flujo()
        elif op == "3":
            print("Saliendo del cargador...")
            break
        else:
            print("Opción no válida.")

if __name__ == "__main__":
    main()
