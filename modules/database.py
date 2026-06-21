import sqlite3

import os

def conectar():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'database', 'manga_recap.db')
    return sqlite3.connect(db_path)

def inicializar_db():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mangas (
            id TEXT PRIMARY KEY,
            titulo TEXT,
            resumen TEXT,
            total_capitulos INTEGER,
            estado TEXT,
            tipo TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS capitulos (
            id TEXT PRIMARY KEY,
            manga_id TEXT,
            titulo TEXT,
            descargado BOOLEAN DEFAULT 0,
            pasado_a_pdf BOOLEAN DEFAULT 0,
            FOREIGN KEY (manga_id) REFERENCES mangas (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imagenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id TEXT,
            url_original TEXT,
            ruta_local TEXT,
            analisis TEXT,
            FOREIGN KEY (chapter_id) REFERENCES capitulos (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guiones (
            chapter_id TEXT PRIMARY KEY,
            contenido TEXT,
            FOREIGN KEY (chapter_id) REFERENCES capitulos (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comentarios (
            id TEXT PRIMARY KEY,
            youtube_video_id TEXT,
            manga_key TEXT,
            autor TEXT,
            texto TEXT,
            fecha_publicacion TEXT,
            leido INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    
    # Ejecutar migraciones para bases de datos existentes
    migracion_añadir_columna_analisis()
    migracion_añadir_columna_pdf()

def resetear_db():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS guiones')
    cursor.execute('DROP TABLE IF EXISTS imagenes')
    cursor.execute('DROP TABLE IF EXISTS capitulos')
    cursor.execute('DROP TABLE IF EXISTS mangas')
    conn.commit()
    conn.close()
    inicializar_db()

def guardar_guion(chapter_id, contenido):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO guiones (chapter_id, contenido)
        VALUES (?, ?)
    ''', (chapter_id, contenido))
    conn.commit()
    conn.close()

def obtener_guion(chapter_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT contenido FROM guiones WHERE chapter_id = ?', (chapter_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def insertar_manga(manga_id, titulo, resumen, total_cap, estado, tipo):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO mangas (id, titulo, resumen, total_capitulos, estado, tipo)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (manga_id, titulo, resumen, total_cap, estado, tipo))
    conn.commit()
    conn.close()

def insertar_capitulo(chapter_id, manga_id, titulo):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO capitulos (id, manga_id, titulo)
        VALUES (?, ?, ?)
    ''', (chapter_id, manga_id, titulo))
    conn.commit()
    conn.close()

def insertar_imagen(chapter_id, url, ruta):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO imagenes (chapter_id, url_original, ruta_local)
        VALUES (?, ?, ?)
    ''', (chapter_id, url, ruta))
    conn.commit()
    conn.close()

def marcar_capitulo_descargado(chapter_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('UPDATE capitulos SET descargado = 1 WHERE id = ?', (chapter_id,))
    conn.commit()
    conn.close()

def obtener_manga(manga_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM mangas WHERE id = ?', (manga_id,))
    res = cursor.fetchone()
    conn.close()
    return res

def capitulo_esta_descargado(chapter_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT descargado FROM capitulos WHERE id = ?', (chapter_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else False

def guardar_analisis_imagen(image_id, texto):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('UPDATE imagenes SET analisis = ? WHERE id = ?', (texto, image_id))
    conn.commit()
    conn.close()

def migracion_añadir_columna_analisis():
    # Funcion utilitaria para añadir la columna si la DB ya existe
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute('ALTER TABLE imagenes ADD COLUMN analisis TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        # La columna ya existe
        pass
    conn.close()

def migracion_añadir_columna_pdf():
    # Funcion utilitaria para añadir la columna si la DB ya existe
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute('ALTER TABLE capitulos ADD COLUMN pasado_a_pdf BOOLEAN DEFAULT 0')
        conn.commit()
    except sqlite3.OperationalError:
        # La columna ya existe
        pass
    conn.close()

def obtener_manga_por_titulo_sanitizado(manga_folder_name):
    from modules.utils import sanitizar_nombre_carpeta
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT id, titulo FROM mangas')
    mangas = cursor.fetchall()
    conn.close()
    for m_id, titulo in mangas:
        if sanitizar_nombre_carpeta(titulo) == manga_folder_name:
            return m_id
    return None

def marcar_capitulo_pdf(manga_id, chapter_title):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('UPDATE capitulos SET pasado_a_pdf = 1 WHERE manga_id = ? AND titulo = ?', (manga_id, chapter_title))
    conn.commit()
    conn.close()

def obtener_comentarios_pendientes():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT id, youtube_video_id, manga_key, autor, texto, fecha_publicacion, leido FROM comentarios WHERE leido = 0 ORDER BY fecha_publicacion DESC')
    rows = cursor.fetchall()
    conn.close()
    return [{
        'id': r[0],
        'youtube_video_id': r[1],
        'manga_key': r[2],
        'autor': r[3],
        'texto': r[4],
        'fecha_publicacion': r[5],
        'leido': r[6]
    } for r in rows]

def marcar_comentario_leido(comentario_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('UPDATE comentarios SET leido = 1 WHERE id = ?', (comentario_id,))
    conn.commit()
    conn.close()

def obtener_cantidad_comentarios_sin_leer():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM comentarios WHERE leido = 0')
    count = cursor.fetchone()[0]
    conn.close()
    return count