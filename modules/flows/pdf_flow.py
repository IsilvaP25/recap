import os
from modules import pdf_converter

def iniciar_flujo():
    print("\n--- FASE 2: CONVERSIÓN A PDF (POST-LIMPIEZA) ---")
    
    # Ruta absoluta al proyecto
    base_proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raw_dir = os.path.join(base_proj, "raw_downloads")
    
    if not os.path.exists(raw_dir):
        print("No se encontró la carpeta raw_downloads.")
        return

    mangas_en_raw = sorted([d for d in os.listdir(raw_dir) if os.path.isdir(os.path.join(raw_dir, d))])
    
    if not mangas_en_raw:
        print("No hay descargas para convertir.")
        return

    print("Mangas con descargas disponibles:")
    for i, m in enumerate(mangas_en_raw, 1):
        print(f"{i}. {m.replace('_', ' ')}")
    print(f"{len(mangas_en_raw) + 1}. PROCESAR TODO")
    
    sel = input("\nSelecciona el manga a convertir (o número para todo): ")
    
    if not sel.isdigit(): return
    idx = int(sel)
    
    if idx == len(mangas_en_raw) + 1:
        print("\nConvirtiendo todos los mangas...")
        nuevos = pdf_converter.convert_webp_to_pdf()
        print(f"\n✅ Se crearon {nuevos} archivos PDF nuevos en total.")
    elif 0 < idx <= len(mangas_en_raw):
        manga_name = mangas_en_raw[idx-1]
        print(f"\nConvirtiendo {manga_name}...")
        nuevos = pdf_converter.convert_webp_to_pdf(manga_name)
        print(f"\n✅ Se crearon {nuevos} archivos PDF nuevos para {manga_name}.")
    else:
        print("Selección no válida.")
