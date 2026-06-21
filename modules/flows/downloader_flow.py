import os
from modules import database, local_manager, downloader, manga_search

def ejecutar_descarga_manga(m_id, m_titulo, automatico=False, forzar=False, manga_data=None):
    print(f"\nConsultando capítulos para: {m_titulo}...")
    try:
        if not manga_data or "chapters" not in manga_data:
            manga_data = manga_search.obtener_detalles_completos(m_id)
            
        capitulos = manga_data.get("chapters", [])
    except Exception as e:
        print(f"Error al obtener capítulos: {e}")
        return

    if not capitulos:
        print("No se encontraron capítulos.")
        return

    modo_descarga = "todos"
    rango_inicio = None
    rango_fin = None
    max_cantidad = None

    if not automatico and not forzar:
        print(f"Se encontraron {len(capitulos)} capítulos.")
        
        if m_id:
            print(f"\n" + "-"*30)
            print(f"[REVISIÓN EXTERNA]")
            print(f"🔗 Enlace: {m_id}")
            if manga_data and manga_data.get("type"):
                print(f"📂 Tipo: {manga_data.get('type').upper()}")
            print("-"*30 + "\n")

        print("Opciones de descarga:")
        print("1. Descargar todos los capítulos que falten (Completo)")
        print("2. Descargar un rango de capítulos específico (ej. 10 a 25)")
        print("3. Descargar los últimos X capítulos")
        print("4. Cancelar")
        
        opcion = input("\nSelecciona una opción (1-4): ").strip()
        if opcion == "1":
            modo_descarga = "todos"
        elif opcion == "2":
            modo_descarga = "rango"
            try:
                rango_inicio = int(input("Capítulo inicial (incluido): ").strip())
                rango_fin = int(input("Capítulo final (incluido): ").strip())
                if rango_inicio > rango_fin:
                    print("El capítulo inicial no puede ser mayor que el final. Descarga cancelada.")
                    return
            except ValueError:
                print("Valores no válidos. Descarga cancelada.")
                return
        elif opcion == "3":
            modo_descarga = "cantidad"
            try:
                max_cantidad = int(input("¿Cuántos de los últimos capítulos deseas descargar?: ").strip())
                if max_cantidad <= 0:
                    print("La cantidad debe ser mayor que cero. Descarga cancelada.")
                    return
            except ValueError:
                print("Valor no válido. Descarga cancelada.")
                return
        else:
            print("Descarga cancelada.")
            return

    # REGISTRO DIFERIDO: Solo si aceptamos descargar o si es automático/forzado
    if manga_data:
        database.insertar_manga(
            m_id, 
            m_titulo, 
            manga_data.get("summary"), 
            manga_data.get("total_chapter"), 
            manga_data.get("status"), 
            manga_data.get("type")
        )
        downloader.descargar_portada(m_id, m_titulo)

    # 1. Pre-filtrar y extraer números de capítulos válidos
    import re
    
    def format_chapter_number(num_float):
        return str(int(num_float)) if num_float == int(num_float) else str(num_float)
        
    caps_validos = []
    for cap in capitulos:
        titulo_api = cap.get("capitulo", "")
        c_id = cap.get("url")
        
        nums = re.findall(r"(\d+[\.\-]\d+|\d+)", titulo_api)
        if not nums:
            continue
            
        num_str = nums[0].replace("-", ".")
        try:
            num_float = float(num_str)
            es_especial = any(x in titulo_api.lower() for x in ["ova", "extra", "special", "omake", "promo"])
            
            if es_especial:
                continue
                
            caps_validos.append({
                "num": num_float,
                "url": c_id,
                "titulo": titulo_api,
                "original_data": cap
            })
        except ValueError:
            continue

    # 2. Aplicar el filtro según el modo seleccionado
    if modo_descarga == "rango":
        caps_a_descargar = [c for c in caps_validos if rango_inicio <= c["num"] <= rango_fin]
    elif modo_descarga == "cantidad":
        # Dado que caps_validos está ordenado de más antiguo a más nuevo,
        # los "últimos X" corresponden a los últimos elementos de la lista.
        caps_a_descargar = caps_validos[-max_cantidad:] if len(caps_validos) > max_cantidad else caps_validos
    else:
        # Modo 'todos'
        caps_a_descargar = caps_validos

    # 3. Descargar los capítulos seleccionados
    for c in caps_a_descargar:
        num_cap = format_chapter_number(c["num"])
        c_id = c["url"]
        
        # Si forzamos, entramos siempre. Si no, solo si la DB dice que falta.
        if forzar or local_manager.requiere_descarga(c_id):
            if forzar: print(f"\n--- Verificando Capítulo {num_cap} ---")
            else: print(f"\n--- Descargando Capítulo {num_cap} ---")
            
            database.insertar_capitulo(c_id, m_id, f"Capitulo {num_cap}")
            downloader.descargar_capitulo(m_titulo, c_id, num_cap)
        else:
            if not automatico: print(f"Capítulo {num_cap} ya marcado como completo. Saltando...")

def descargar_capitulo_uno_filtrados(cantidad):
    year_str = input("Introduce el año inicial/mínimo (ej. 2005): ")
    try:
        year_min = int(year_str)
        if year_min < 1900 or year_min > 2100:
            print("Año no válido.")
            return
    except ValueError:
        print("Entrada de año inválida.")
        return

    print(f"\nBuscando mangas desde el año {year_min} en adelante de forma aleatoria...")
    
    import random
    import re
    
    # Rango de páginas del directorio a barajar (páginas 1 a 100)
    pags_disponibles = list(range(1, 101))
    random.shuffle(pags_disponibles)
    
    exitos = 0
    mangas_procesados = set()
    
    for page in pags_disponibles:
        if exitos >= cantidad:
            break
            
        print(f"\n[SISTEMA] Cargando página {page} del directorio...")
        pool = manga_search.obtener_pool_mangas(page)
        if not pool:
            print(f"No se pudieron obtener mangas de la página {page}.")
            continue
            
        # Barajar mangas en la página para mayor aleatoriedad
        random.shuffle(pool)
        
        # 1. Filtrar candidatos de esta página
        candidatos = []
        for item in pool:
            m_id = item['url']
            m_titulo = item['titulo']
            
            if m_id in mangas_procesados:
                continue
            mangas_procesados.add(m_id)
            
            # Verificar si ya está descargado completo
            if local_manager.manga_esta_descargado(m_id):
                print(f"  [SKIP] '{m_titulo}' ya se encuentra descargado en la base de datos.")
                continue
            candidatos.append(item)

        if not candidatos:
            continue

        print(f"  [SISTEMA] Evaluando {len(candidatos)} mangas de la página {page} en paralelo...")
        
        # 2. Obtener detalles en paralelo
        from concurrent.futures import ThreadPoolExecutor
        resultados_detalles = []
        
        def obtener_detalles_seguro(item):
            try:
                det = manga_search.obtener_detalles_completos(item['url'])
                return item, det
            except Exception as e:
                print(f"  Error obteniendo detalles de '{item['titulo']}': {e}")
                return item, None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futuros = [executor.submit(obtener_detalles_seguro, item) for item in candidatos]
            for fut in futuros:
                res = fut.result()
                if res[1] is not None:
                    resultados_detalles.append(res)

        # 3. Evaluar y procesar uno por uno los mangas obtenidos
        for item, detalles in resultados_detalles:
            if exitos >= cantidad:
                break
                
            m_id = item['url']
            m_titulo = item['titulo']
            
            try:
                if not detalles.get("chapters"):
                    continue
                    
                # El primer capítulo es el más antiguo (primer elemento del array)
                first_chapter = detalles["chapters"][0]
                first_chap_date = first_chapter.get("date", "")
                
                # Asumir año actual si la fecha es relativa (por ejemplo "3 hours ago", "yesterday", etc.)
                first_chap_year = 2026
                match = re.search(r'\b(19\d{2}|20\d{2})\b', first_chap_date)
                if match:
                    first_chap_year = int(match.group(1))
                    
                if first_chap_year < year_min:
                    print(f"  [SKIP] '{m_titulo}' es del año {first_chap_year} (menor que {year_min}).")
                    continue
                    
                print(f"\n>>> [APROBADO] '{m_titulo}' del año {first_chap_year} >= {year_min}. Buscando Capítulo 1...")
                
                # Buscar capítulo 1 estándar
                cap_1_url = None
                capitulos = detalles.get("chapters", [])
                for cap in capitulos:
                    titulo_api = cap.get("capitulo", "")
                    c_url = cap.get("url")
                    
                    nums = re.findall(r"(\d+[\.\-]\d+|\d+)", titulo_api)
                    if not nums:
                        continue
                    num_str = nums[0].replace("-", ".")
                    try:
                        num_float = float(num_str)
                        if num_float == 1.0:
                            if not any(x in titulo_api.lower() for x in ["ova", "extra", "special", "omake", "promo"]):
                                cap_1_url = c_url
                                break
                    except ValueError:
                        continue
                        
                if not cap_1_url:
                    print(f"  No se encontró Capítulo 1 estándar para {m_titulo}. Saltando...")
                    continue
                    
                # Guardamos el manga en la base de datos
                database.insertar_manga(
                    m_id,
                    m_titulo,
                    detalles.get("summary"),
                    detalles.get("total_chapter"),
                    detalles.get("status"),
                    detalles.get("type")
                )
                downloader.descargar_portada(m_id, m_titulo)
                
                # Insertamos y descargamos el capítulo 1
                print(f"  Iniciando descarga de Capítulo 1...")
                database.insertar_capitulo(cap_1_url, m_id, "Capitulo 1")
                downloader.descargar_capitulo(m_titulo, cap_1_url, 1)
                
                # Comprobar si realmente se marcó como completado
                if database.capitulo_esta_descargado(cap_1_url):
                    exitos += 1
                    print(f"  [OK] ¡Descarga exitosa de '{m_titulo}' ({exitos}/{cantidad})!")
                else:
                    print(f"  [ERROR] Falló la descarga de Capítulo 1 para '{m_titulo}'.")
                    
            except Exception as e:
                print(f"  Error procesando {m_titulo}: {e}")
                
    print(f"\n[OK] Proceso completado. Se descargaron {exitos}/{cantidad} mangas nuevos correctamente.")

def iniciar_flujo():
    print("\n--- FASE 1: BÚSQUEDA Y DESCARGA ---")
    print("1. Buscar por nombre")
    print("2. Manga aleatorio")
    print("3. Reanudar descarga específica (Elegir Manga) [Hint: Usa 'd' + número para borrar]")
    print("4. DESCARGA AUTOMÁTICA (Todos los mangas registrados)")
    print("5. VERIFICAR INTEGRIDAD (Repasar TODAS las descargas desde cero)")
    print("6. Descargar capítulo 1 de X mangas aleatorios por año")
    op = input("Selecciona: ")
    
    if op == "1":
        nombre = input("Nombre del manga: ")
        resultados = manga_search.buscar_por_titulo(nombre)
        if not resultados: return

        for i, m in enumerate(resultados[:15]):
            print(f"{i+1}. {m.get('title')}")
        
        sel = input("\nSelección: ")
        if sel.isdigit() and 0 < int(sel) <= len(resultados):
            m_id = resultados[int(sel)-1].get("id")
            detalles = manga_search.obtener_detalles_completos(m_id)
            m_titulo = detalles.get("title")
            ejecutar_descarga_manga(m_id, m_titulo, manga_data=detalles)
    elif op == "2":
        print("\n--- INICIANDO MODO DESCUBRIMIENTO (Escribe 'salir' para terminar) ---")
        cola_descubrimiento = []
        vistos = set()

        while True:
            if not cola_descubrimiento:
                manga_batch = manga_search.obtener_manga_aleatorio(return_list=True)
                if not manga_batch:
                    print("No se encontraron novedades. Reintentando...")
                    import time
                    time.sleep(2)
                    continue
                
                import random
                random.shuffle(manga_batch)
                cola_descubrimiento = [m for m in manga_batch if m.get("id") not in vistos]
                
                if not cola_descubrimiento:
                    vistos.clear()
                    cola_descubrimiento = manga_batch
                    random.shuffle(cola_descubrimiento)

            manga = cola_descubrimiento.pop(0)
            m_id = manga.get("id")
            vistos.add(m_id)
            
            detalles = manga_search.obtener_detalles_completos(m_id)
            m_titulo = detalles.get("title", "Sin título")
            
            print(f"\n" + "="*40)
            print(f"[DESCUBRIMIENTO]: {m_titulo}")
            print(f"🔗 Enlace: {m_id}")
            print("="*40)
            
            accion = input("\n[s] Descargar | [n] Siguiente | [salir] Salir: ").lower()
            
            if accion == 'salir':
                break
            elif accion == 's':
                ejecutar_descarga_manga(m_id, m_titulo, manga_data=detalles)
            elif accion == 'n':
                continue
            else:
                print("Opción no válida.")
    elif op == "3":
        mangas = local_manager.listar_mangas_registrados()
        if not mangas:
            print("No hay mangas registrados.")
            return
            
        filtro = input("\nIntroduce el nombre del manga a buscar (o presiona Enter para listar todos): ").strip().lower()
        if filtro:
            import re
            def normalizar(t):
                return re.sub(r'[^\w\s]', ' ', t.lower()).strip()
            
            filtro_norm = normalizar(filtro)
            palabras_filtro = filtro_norm.split()
            
            if palabras_filtro:
                mangas_filtrados = []
                for m in mangas:
                    titulo_norm = normalizar(m[1])
                    # Verifica coincidencia directa o que todas las palabras buscadas estén en el título
                    if filtro_norm in titulo_norm or all(p in titulo_norm for p in palabras_filtro):
                        mangas_filtrados.append(m)
            else:
                mangas_filtrados = mangas
        else:
            mangas_filtrados = mangas

        if not mangas_filtrados:
            print("No se encontraron mangas que coincidan con el nombre ingresado.")
            return

        print(f"\nMangas encontrados ({len(mangas_filtrados)}):")
        for i, m in enumerate(mangas_filtrados): 
            print(f"{i+1}. {m[1]}")
            
        sel = input("\nSelección (o 'd' + número para borrar, ej: d2): ")
        
        if sel.lower().startswith('d'):
            idx_str = sel[1:]
            if idx_str.isdigit() and 0 < int(idx_str) <= len(mangas_filtrados):
                idx = int(idx_str) - 1
                m_id, m_titulo = mangas_filtrados[idx][0], mangas_filtrados[idx][1]
                confirmar = input(f"¿Estás SEGURO de borrar '{m_titulo}' de la base de datos? (s/n): ")
                if confirmar.lower() == 's':
                    import sqlite3
                    conn = database.conectar()
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM guiones WHERE chapter_id IN (SELECT id FROM capitulos WHERE manga_id = ?)', (m_id,))
                    cursor.execute('DELETE FROM imagenes WHERE chapter_id IN (SELECT id FROM capitulos WHERE manga_id = ?)', (m_id,))
                    cursor.execute('DELETE FROM capitulos WHERE manga_id = ?', (m_id,))
                    cursor.execute('DELETE FROM mangas WHERE id = ?', (m_id,))
                    conn.commit()
                    conn.close()
                    print(f"✅ '{m_titulo}' ha sido eliminado de la base de datos.")
            return

        if sel.isdigit() and 0 < int(sel) <= len(mangas_filtrados):
            m_id, m_titulo = mangas_filtrados[int(sel)-1][0], mangas_filtrados[int(sel)-1][1]
            ejecutar_descarga_manga(m_id, m_titulo)
    elif op == "4":
        mangas = local_manager.listar_mangas_registrados()
        if not mangas:
            print("No hay mangas registrados.")
            return
        print(f"\nIniciando descarga automática de {len(mangas)} mangas...")
        for row in mangas:
            m_id, m_titulo = row[0], row[1]
            print(f"\n>>> PROCESANDO: {m_titulo}")
            ejecutar_descarga_manga(m_id, m_titulo, automatico=True)
        print("\n[OK] Descarga automática finalizada.")
    elif op == "5":
        mangas = local_manager.listar_mangas_registrados()
        if not mangas:
            print("No hay mangas registrados.")
            return
        print("\n!!! ADVERTENCIA: Esta opción repasará TODOS tus capítulos físicamente.")
        print("Si borraste spam de capítulos completados, podrían volver a descargarse.")
        if input("¿Deseas continuar? (s/n): ").lower() != 's': return
        
        for row in mangas:
            m_id, m_titulo = row[0], row[1]
            print(f"\n>>> AUDITANDO: {m_titulo}")
            ejecutar_descarga_manga(m_id, m_titulo, forzar=True)
        print("\n[OK] Auditoría de integridad finalizada.")
    elif op == "6":
        cant_str = input("\n¿Cuántos mangas deseas descargar?: ")
        if cant_str.isdigit() and int(cant_str) > 0:
            descargar_capitulo_uno_filtrados(int(cant_str))
        else:
            print("Cantidad no válida.")
