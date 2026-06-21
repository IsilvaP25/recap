import os
import re
import shutil
from PIL import Image
import fitz  # PyMuPDF
import io
from modules import database

def get_natural_key(text):
    """Sort strings with numbers naturally (e.g., 2 before 10)."""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

def parse_chapter_folder(folder_name):
    """
    Parses a chapter folder name to find its base chapter name and float sort value.
    Example:
      "Capitulo_26.1" -> ("Capitulo_26", 26.1)
      "Capitulo_3" -> ("Capitulo_3", 3.0)
      "26.1" -> ("26", 26.1)
    """
    m = re.match(r'^(Capitulo_)?(\d+)(?:\.(\d+))?$', folder_name, re.IGNORECASE)
    if m:
        prefix = m.group(1) or ""
        chap_num = m.group(2)
        part_num = m.group(3)
        base_name = f"{prefix}{chap_num}"
        if part_num:
            val = float(f"{chap_num}.{part_num}")
        else:
            val = float(chap_num)
        return base_name, val
    
    # Generic fallback to find any numbers
    m_num = re.search(r'(\d+)(?:\.(\d+))?', folder_name)
    if m_num:
        chap_num = m_num.group(1)
        part_num = m_num.group(2)
        idx = folder_name.find(chap_num)
        prefix = folder_name[:idx]
        base_name = f"{prefix}{chap_num}"
        if part_num:
            val = float(f"{chap_num}.{part_num}")
        else:
            val = float(chap_num)
        return base_name, val
        
    return folder_name, 0.0

def convertir_capitulo_grupal(raw_dir, pdf_root, manga_name, base_cap_name, folder_list):
    """
    Converts a list of sub-chapters (e.g., Capitulo_26.1, Capitulo_26.2) into a single Capitulo_26.pdf.
    The pages are appended sequentially (e.g., Capitulo_26.1 first, then Capitulo_26.2, etc.).
    """
    manga_path = os.path.join(raw_dir, manga_name)
    manga_pdf_dir = os.path.join(pdf_root, manga_name)
    os.makedirs(manga_pdf_dir, exist_ok=True)
    
    pdf_filename = f"{base_cap_name}.pdf"
    pdf_path = os.path.join(manga_pdf_dir, pdf_filename)
    
    pdf_exists = os.path.exists(pdf_path)
    
    if not pdf_exists:
        # Collect all images from all folders in order
        all_images = []
        for cap_folder in folder_list:
            cap_path = os.path.join(manga_path, cap_folder)
            if not os.path.exists(cap_path):
                continue
            images = [f for f in os.listdir(cap_path) if f.lower().endswith(('.webp', '.png', '.jpg', '.jpeg'))]
            images.sort(key=get_natural_key)
            for img in images:
                all_images.append((cap_folder, img))
                
        if not all_images:
            print(f"  [!] Saltando {manga_name} - {base_cap_name}: No se encontraron imágenes en las carpetas {folder_list}.")
            return False
            
        print(f"  [+] Convirtiendo {manga_name} - {base_cap_name} ({len(all_images)} imágenes de {len(folder_list)} partes)...")
        
        pdf_doc = fitz.open()
        try:
            for cap_folder, img_name in all_images:
                img_path = os.path.join(manga_path, cap_folder, img_name)
                
                # Obtener dimensiones sin dejar el archivo abierto
                with Image.open(img_path) as img:
                    width, height = img.width, img.height
                
                # Crear una página PDF con las dimensiones de la imagen
                page = pdf_doc.new_page(width=width, height=height)
                
                try:
                    # Intento de inserción directa
                    page.insert_image(page.rect, filename=img_path)
                except Exception:
                    # Fallback si falla
                    with Image.open(img_path) as img:
                        if img.mode in ("RGBA", "P"):
                            img_rgb = img.convert("RGB")
                        else:
                            img_rgb = img
                        img_byte_arr = io.BytesIO()
                        img_rgb.save(img_byte_arr, format='JPEG')
                        img_data = img_byte_arr.getvalue()
                    page.insert_image(page.rect, stream=img_data)
            
            pdf_doc.save(pdf_path)
            pdf_exists = True
        except Exception as e:
            print(f"  [X] Error al crear PDF para {manga_name} - {base_cap_name}: {e}")
            return False
        finally:
            pdf_doc.close()
    else:
        print(f"  [~] El PDF para {manga_name} - {base_cap_name} ya existe. Procediendo a limpiar raws...")
        
    if pdf_exists:
        # 1. Actualizar base de datos
        manga_id = database.obtener_manga_por_titulo_sanitizado(manga_name)
        if manga_id:
            for cap_folder in folder_list:
                chapter_title = cap_folder.replace('_', ' ')
                database.marcar_capitulo_pdf(manga_id, chapter_title)
                print(f"  [DB] Capítulo '{chapter_title}' de {manga_name} marcado como pasado a PDF.")
        
        # 2. Eliminar carpetas del capítulo con imágenes raw
        for cap_folder in folder_list:
            cap_path = os.path.join(manga_path, cap_folder)
            try:
                if os.path.exists(cap_path):
                    shutil.rmtree(cap_path)
                    print(f"  [LIMPIEZA] Carpeta RAW de {manga_name} - {cap_folder} eliminada.")
            except Exception as e:
                print(f"  [!] Error al eliminar carpeta RAW para {manga_name} - {cap_folder}: {e}")
            
    return True

def convert_webp_to_pdf(manga_to_process=None, chapters_to_process=None):
    # Directorio base del proyecto
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Directorio de descargas temporales
    raw_dir = os.path.join(base_dir, "raw_downloads")
    # Directorio final para los PDFs
    pdf_root = os.path.join(base_dir, "pdf_storage")
    
    if not os.path.exists(raw_dir):
        print(f"Error: No se encuentra la carpeta de descargas en {raw_dir}")
        return 0

    os.makedirs(pdf_root, exist_ok=True)
    
    mangas = [manga_to_process] if manga_to_process else os.listdir(raw_dir)
    
    # 1. Recopilar todas las tareas de capítulos a convertir (agrupando subcapítulos)
    tareas = []
    for manga_name in mangas:
        manga_path = os.path.join(raw_dir, manga_name)
        if not os.path.isdir(manga_path):
            continue
            
        folders = [d for d in os.listdir(manga_path) if os.path.isdir(os.path.join(manga_path, d))]
        
        # Agrupar las carpetas del manga por su capítulo base
        grouped = {}
        for f in folders:
            # Filtrar si chapters_to_process está especificado y esta carpeta no está seleccionada
            if chapters_to_process and f not in chapters_to_process:
                continue
            base_name, val = parse_chapter_folder(f)
            if base_name not in grouped:
                grouped[base_name] = []
            grouped[base_name].append((f, val))
            
        # Ordenar cada grupo por su valor decimal y guardar en tareas
        for base_cap_name, group_list in grouped.items():
            group_list.sort(key=lambda x: x[1])
            folder_list = [x[0] for x in group_list]
            tareas.append((manga_name, base_cap_name, folder_list))

    # Helper para limpiar carpetas vacías
    def limpiar_vacios():
        for manga_name in os.listdir(raw_dir):
            manga_path = os.path.join(raw_dir, manga_name)
            if os.path.isdir(manga_path):
                if not os.listdir(manga_path):
                    try:
                        os.rmdir(manga_path)
                        print(f"  [LIMPIEZA] Carpeta vacía de manga eliminada: {manga_name}")
                    except Exception as e:
                        print(f"  [!] Error al eliminar carpeta vacía de manga {manga_name}: {e}")

    if not tareas:
        limpiar_vacios()
        return 0

    # 2. Procesar tareas en paralelo usando ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor
    total_created = 0
    
    print(f"\n[SISTEMA] Iniciando conversión de {len(tareas)} capítulos base a PDF en paralelo...")
    with ThreadPoolExecutor(max_workers=4) as executor:
        futuros = [
            executor.submit(convertir_capitulo_grupal, raw_dir, pdf_root, manga_name, base_cap_name, folder_list)
            for manga_name, base_cap_name, folder_list in tareas
        ]
        
        for fut in futuros:
            if fut.result():
                total_created += 1
                
    limpiar_vacios()
    return total_created

if __name__ == "__main__":
    convert_webp_to_pdf()
