import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "manga_recap.db")

def migrate_old_pipeline_db():
    old_db_path = os.path.join(BASE_DIR, "database", "manga_pipeline.db")
    if not os.path.exists(old_db_path):
        return
        
    print(f"  [MIGRACIÓN] Detectada base de datos antigua {old_db_path}. Iniciando migración a {DB_PATH}...")
    try:
        old_conn = sqlite3.connect(old_db_path)
        old_cursor = old_conn.cursor()
        
        old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in old_cursor.fetchall() if not t[0].startswith('sqlite_')]
        
        if not tables:
            old_conn.close()
            os.remove(old_db_path)
            print("  [MIGRACIÓN] Base de datos antigua estaba vacía. Eliminada.")
            return
            
        new_conn = sqlite3.connect(DB_PATH)
        new_cursor = new_conn.cursor()
        
        for table in tables:
            print(f"  [MIGRACIÓN] Migrando tabla '{table}'...")
            old_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
            create_sql = old_cursor.fetchone()[0]
            try:
                new_cursor.execute(create_sql)
            except sqlite3.OperationalError as oe:
                if "already exists" not in str(oe):
                    raise
            
            old_cursor.execute(f"SELECT * FROM [{table}]")
            rows = old_cursor.fetchall()
            
            if rows:
                placeholders = ', '.join(['?'] * len(rows[0]))
                insert_sql = f"INSERT OR IGNORE INTO [{table}] VALUES ({placeholders})"
                new_cursor.executemany(insert_sql, rows)
                
        new_conn.commit()
        new_conn.close()
        old_conn.close()
        
        os.remove(old_db_path)
        print("  [MIGRACIÓN] Migración finalizada con éxito. Base de datos antigua eliminada.")
    except Exception as e:
        print(f"  [ERROR MIGRACIÓN] Error al migrar base de datos: {e}")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    migrate_old_pipeline_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table for full chapter scripts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manga TEXT,
            chapter INTEGER,
            page_num INTEGER,
            content TEXT,
            status TEXT DEFAULT 'completed',
            UNIQUE(manga, chapter, page_num)
        )
    ''')
    
    # Table for Shorts (one per manga/Chapter 1)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shorts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manga TEXT UNIQUE,
            content TEXT,
            thumbnail_prompt TEXT,
            status TEXT DEFAULT 'completed',
            is_uploaded INTEGER DEFAULT 0,
            youtube_id TEXT,
            video_created INTEGER DEFAULT 0,
            scheduled_date TEXT
        )
    ''')
    
    # Migración: Añadir columnas si no existen
    try:
        cursor.execute('ALTER TABLE shorts ADD COLUMN thumbnail_prompt TEXT')
    except sqlite3.OperationalError: pass
    try:
        cursor.execute('ALTER TABLE shorts ADD COLUMN is_uploaded INTEGER DEFAULT 0')
    except sqlite3.OperationalError: pass
    try:
        cursor.execute('ALTER TABLE shorts ADD COLUMN youtube_id TEXT')
    except sqlite3.OperationalError: pass
    try:
        cursor.execute('ALTER TABLE shorts ADD COLUMN video_created INTEGER DEFAULT 0')
    except sqlite3.OperationalError: pass
    try:
        cursor.execute('ALTER TABLE shorts ADD COLUMN scheduled_date TEXT')
    except sqlite3.OperationalError: pass
    
    # Table for Global Config (Scheduling, etc.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Inicializar fecha de última subida si no existe (hace 2 días para permitir la primera)
    import datetime
    cursor.execute('INSERT OR IGNORE INTO global_config (key, value) VALUES (?, ?)', 
                   ('last_main_upload', (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat()))
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS story_history (
            manga TEXT PRIMARY KEY,
            last_chapter INTEGER,
            summary TEXT,
            origin_type TEXT DEFAULT 'manga'
        )
    ''')
    
    # Migración: Añadir origin_type si no existe
    try:
        cursor.execute('ALTER TABLE story_history ADD COLUMN origin_type TEXT DEFAULT "manga"')
    except sqlite3.OperationalError: pass
    
    # Table for Video Parts management
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pipeline_parts (
            manga TEXT,
            part_number INTEGER,
            start_chapter INTEGER,
            end_chapter INTEGER,
            status TEXT,
            is_uploaded INTEGER DEFAULT 0,
            youtube_id TEXT,
            is_maraton_uploaded INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (manga, part_number)
        )
    ''')
    
    # Table for deleted videos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deleted_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manga TEXT,
            type TEXT,
            chapter_or_part TEXT,
            ai_provider TEXT,
            youtube_id TEXT UNIQUE,
            title TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending_repair',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Verificar si las columnas nuevas existen (para bases de datos viejas)
    cursor.execute("PRAGMA table_info(pipeline_parts)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'is_uploaded' not in columns:
        print("  [DB] Añadiendo columna is_uploaded...")
        cursor.execute('ALTER TABLE pipeline_parts ADD COLUMN is_uploaded INTEGER DEFAULT 0')
    if 'youtube_id' not in columns:
        print("  [DB] Añadiendo columna youtube_id...")
        cursor.execute('ALTER TABLE pipeline_parts ADD COLUMN youtube_id TEXT')
    if 'is_maraton_uploaded' not in columns:
        print("  [DB] Añadiendo columna is_maraton_uploaded...")
        cursor.execute('ALTER TABLE pipeline_parts ADD COLUMN is_maraton_uploaded INTEGER DEFAULT 0')
        
    # Auto-sincronización de videos ya creados en disco
    outputs_dir = os.path.join(BASE_DIR, "outputs")
    if os.path.exists(outputs_dir):
        mangas = [d for d in os.listdir(outputs_dir) if os.path.isdir(os.path.join(outputs_dir, d))]
        for manga in mangas:
            manga_key = manga.replace(' ', '_')
            video_path = os.path.join(outputs_dir, manga, "VIDEOS", "Short_1.mp4")
            if os.path.exists(video_path):
                # Asegurar registro en shorts
                cursor.execute('INSERT OR IGNORE INTO shorts (manga) VALUES (?)', (manga_key,))
                # Marcar como creado
                cursor.execute('UPDATE shorts SET video_created = 1 WHERE manga = ?', (manga_key,))
                
    conn.commit()
    conn.close()

def save_page_script(manga, chapter, page_num, content):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO scripts (manga, chapter, page_num, content)
        VALUES (?, ?, ?, ?)
    ''', (manga, chapter, page_num, content))
    conn.commit()
    conn.close()

def get_page_script(manga, chapter, page_num):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT content FROM scripts WHERE manga = ? AND chapter = ? AND page_num = ?', (manga, chapter, page_num))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def save_short_script(manga, content, thumbnail_prompt=None):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO shorts (manga, content, thumbnail_prompt)
        VALUES (?, ?, ?)
    ''', (manga, content, thumbnail_prompt))
    conn.commit()
    conn.close()

def get_short_script(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT content, thumbnail_prompt FROM shorts WHERE manga = ?', (manga,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (None, None)

def is_short_uploaded(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT is_uploaded FROM shorts WHERE manga = ?', (manga,))
    row = cursor.fetchone()
    conn.close()
    return row[0] == 2 if row and row[0] is not None else False

def mark_short_as_uploaded(manga, youtube_id):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE shorts 
        SET is_uploaded = 1, youtube_id = ? 
        WHERE manga = ?
    ''', (youtube_id, manga))
    conn.commit()
    print(f"  [DB_MANAGER] Short de '{manga}' marcado como subido con éxito.")
    conn.close()

# --- NEW: History and Parts Management ---

def save_story_history(manga, last_chapter, summary, origin_type='manga'):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO story_history (manga, last_chapter, summary, origin_type)
        VALUES (?, ?, ?, ?)
    ''', (manga, last_chapter, summary, origin_type))
    conn.commit()
    conn.close()

def get_story_history(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT summary, last_chapter, origin_type FROM story_history WHERE manga = ?', (manga,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (None, 0, 'manga')

def save_pipeline_part(manga, part_num, start_cap, end_cap, status='completed'):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO pipeline_parts (manga, part_number, start_chapter, end_chapter, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (manga, part_num, start_cap, end_cap, status))
    conn.commit()
    conn.close()

def mark_as_uploaded(manga, part_number, youtube_id):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pipeline_parts 
        SET is_uploaded = 1, youtube_id = ? 
        WHERE manga = ? AND part_number = ?
    ''', (youtube_id, manga, part_number))
    conn.commit()
    conn.close()

def mark_maraton_as_uploaded(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE pipeline_parts 
        SET is_maraton_uploaded = 1 
        WHERE manga = ? AND part_number = 5
    ''')
    conn.commit()
    conn.close()

def is_maraton_uploaded(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT is_maraton_uploaded FROM pipeline_parts WHERE manga = ? AND part_number = 5', (manga,))
    row = cursor.fetchone()
    conn.close()
    return row[0] == 1 if row and row[0] is not None else False


def get_next_upload_slot():
    import datetime
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Buscar la última fecha registrada en la configuración global
    cursor.execute('SELECT value FROM global_config WHERE key = ?', ('last_main_upload',))
    row = cursor.fetchone()
    
    ahora = datetime.datetime.now()
    
    if not row or not row[0]:
        conn.close()
        return None # Publicación instantánea hoy
        
    try:
        # Parsear última fecha
        fecha_str = row[0].replace('Z', '').split('+')[0]
        ultima_fecha = datetime.datetime.fromisoformat(fecha_str)
        
        # Si la última subida fue antes de hoy (ayer o antes), hoy no se ha subido nada
        if ultima_fecha.date() < ahora.date():
            conn.close()
            return None # Publicación instantánea hoy
        else:
            # Ya se subió algo hoy, programar para el día siguiente
            base_fecha = max(ultima_fecha, ahora)
            proximo = base_fecha + datetime.timedelta(days=1)
            proximo = proximo.replace(hour=11, minute=0, second=0, microsecond=0)
            proximo_iso = proximo.strftime('%Y-%m-%dT%H:%M:%SZ')
            conn.close()
            return proximo_iso
    except Exception as e:
        print(f"  [AVISO] Error procesando fecha '{row[0]}': {e}. Reseteando a publicación instantánea.")
        conn.close()
        return None

def update_last_upload_date(date_iso):
    """Actualiza la fecha de referencia global tras una subida exitosa. Si es nula, registra la fecha/hora actual."""
    if not date_iso:
        import datetime
        date_iso = datetime.datetime.now().isoformat()
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE global_config SET value = ? WHERE key = ?', (date_iso, 'last_main_upload'))
    conn.commit()
    conn.close()
    print(f"  [DB] Calendario de videos largos actualizado a: {date_iso}")

def get_last_part(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(part_number), end_chapter FROM pipeline_parts WHERE manga = ? AND status = "completed"', (manga,))
    row = cursor.fetchone()
    conn.close()
    return row if row[0] is not None else (0, 0)

def get_pending_uploads(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT part_number, start_chapter, end_chapter 
        FROM pipeline_parts 
        WHERE manga = ? AND is_uploaded = 0 AND status = "completed"
        ORDER BY part_number ASC
    ''', (manga,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def is_short_video_created(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT video_created FROM shorts WHERE manga = ?', (manga,))
    row = cursor.fetchone()
    conn.close()
    return row[0] >= 1 if row and row[0] is not None else False

def is_both_short_videos_created(manga):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT video_created FROM shorts WHERE manga = ?', (manga,))
    row = cursor.fetchone()
    conn.close()
    return row[0] >= 2 if row and row[0] is not None else False

def mark_short_video_created(manga, created=1):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE shorts 
        SET video_created = ? 
        WHERE manga = ?
    ''', (created, manga))
    conn.commit()
    conn.close()

def get_last_scheduled_short_date():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(scheduled_date) FROM shorts WHERE is_uploaded >= 1 AND scheduled_date IS NOT NULL')
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_scheduled_short_dates():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT scheduled_date FROM shorts WHERE is_uploaded >= 1 AND scheduled_date IS NOT NULL')
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]

def mark_short_as_uploaded_with_date_step(manga, youtube_id, scheduled_date, step):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Obtener el youtube_id anterior para concatenarlo
    cursor.execute('SELECT youtube_id FROM shorts WHERE manga = ?', (manga,))
    row = cursor.fetchone()
    old_id = row[0] if row and row[0] is not None else ""
    new_id = f"{old_id},{youtube_id}" if old_id else youtube_id
    
    cursor.execute('''
        UPDATE shorts 
        SET is_uploaded = ?, youtube_id = ?, scheduled_date = ?
        WHERE manga = ?
    ''', (step, new_id, scheduled_date, manga))
    conn.commit()
    print(f"  [DB_MANAGER] Short de '{manga}' marcado como subido con éxito (Paso {step}/4) (Programado: {scheduled_date}).")
    conn.close()

def mark_short_as_uploaded_with_date(manga, youtube_id, scheduled_date):
    mark_short_as_uploaded_with_date_step(manga, youtube_id, scheduled_date, 1)

def mark_short_as_uploaded_with_date_step2(manga, youtube_id, scheduled_date):
    mark_short_as_uploaded_with_date_step(manga, youtube_id, scheduled_date, 2)

def mark_short_as_uploaded_single(manga, youtube_id, scheduled_date):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE shorts 
        SET is_uploaded = 2, youtube_id = ?, scheduled_date = ?
        WHERE manga = ?
    ''', (youtube_id, scheduled_date, manga))
    conn.commit()
    print(f"  [DB_MANAGER] Short de '{manga}' marcado como subido con éxito (Programado: {scheduled_date}).")
    conn.close()


def get_pending_shorts_uploads():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT manga 
        FROM shorts 
        WHERE (video_created >= 1 AND is_uploaded < 2)
        OR manga IN (
            SELECT DISTINCT manga FROM deleted_videos WHERE type = 'short' AND status = 'repaired'
        )
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def register_deleted_video(manga, type_val, chapter_or_part, ai_provider, youtube_id, title, description):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO deleted_videos (manga, type, chapter_or_part, ai_provider, youtube_id, title, description, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_repair')
    ''', (manga, type_val, str(chapter_or_part), ai_provider, youtube_id, title, description))
    conn.commit()
    conn.close()

def mark_deleted_video_as_repaired(manga, type_val, chapter_or_part, ai_provider):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE deleted_videos 
        SET status = 'repaired' 
        WHERE manga = ? AND type = ? AND chapter_or_part = ? AND ai_provider = ? AND status = 'pending_repair'
    ''', (manga, type_val, str(chapter_or_part), ai_provider))
    conn.commit()
    conn.close()

def mark_deleted_video_as_reuploaded(manga, type_val, chapter_or_part, ai_provider, new_youtube_id):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE deleted_videos 
        SET status = 'reuploaded', youtube_id = ? 
        WHERE manga = ? AND type = ? AND chapter_or_part = ? AND ai_provider = ? AND status = 'repaired'
    ''', (new_youtube_id, manga, type_val, str(chapter_or_part), ai_provider))
    conn.commit()
    conn.close()

def is_video_pending_repair(manga, type_val, chapter_or_part, ai_provider):
    manga = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 1 FROM deleted_videos 
        WHERE manga = ? AND type = ? AND chapter_or_part = ? AND ai_provider = ? AND status = 'pending_repair'
    ''', (manga, type_val, str(chapter_or_part), ai_provider))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def get_video_status(manga, type_val='short', chapter_or_part='1'):
    manga_key = manga.replace(' ', '_')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Obtener registro de shorts o pipeline_parts
    yt_ids = []
    is_uploaded_val = 0
    if type_val == 'short':
        cursor.execute("SELECT youtube_id, is_uploaded FROM shorts WHERE manga = ?", (manga_key,))
        row = cursor.fetchone()
        if row:
            is_uploaded_val = row[1] or 0
            if row[0]:
                yt_ids = [x.strip() for x in row[0].split(',') if x.strip()]
    else:
        cursor.execute("SELECT youtube_id, is_uploaded FROM pipeline_parts WHERE manga = ? AND part_number = ?", (manga_key, int(chapter_or_part)))
        row = cursor.fetchone()
        if row:
            is_uploaded_val = row[1] or 0
            if row[0]:
                yt_ids = [x.strip() for x in row[0].split(',') if x.strip()]
                
    # 2. Consultar deleted_videos
    cursor.execute("""
        SELECT ai_provider, youtube_id, status 
        FROM deleted_videos 
        WHERE manga = ? AND type = ? AND chapter_or_part = ?
    """, (manga_key, type_val, str(chapter_or_part)))
    deleted_rows = cursor.fetchall()
    conn.close()
    
    # Mapear eliminaciones
    deleted_map = {}
    for ai, yid, status in deleted_rows:
        if ai not in deleted_map or status == 'pending_repair':
            deleted_map[ai] = {'youtube_id': yid, 'status': status}
            
    providers = ['gemini', 'ollama'] if type_val == 'short' else ['gemini']
    status_map = {}
    
    for provider in providers:
        if provider in deleted_map:
            del_info = deleted_map[provider]
            if del_info['status'] == 'pending_repair':
                status_map[provider] = 'pending_repair'
            elif del_info['status'] == 'repaired':
                status_map[provider] = 'repaired'
            else:
                if del_info['youtube_id'] in yt_ids:
                    status_map[provider] = 'uploaded'
                else:
                    status_map[provider] = 'reuploaded'
        else:
            if type_val == 'short':
                if provider == 'gemini':
                    if len(yt_ids) == 2:
                        status_map['gemini'] = 'uploaded'
                    elif len(yt_ids) == 1:
                        if 'ollama' in deleted_map:
                            status_map['gemini'] = 'uploaded'
                        else:
                            status_map['gemini'] = 'uploaded' if is_uploaded_val >= 1 else 'pending_upload'
                    else:
                        status_map['gemini'] = 'pending_upload'
                else: # ollama
                    if len(yt_ids) == 2:
                        status_map['ollama'] = 'uploaded'
                    elif len(yt_ids) == 1:
                        if 'gemini' in deleted_map:
                            status_map['ollama'] = 'uploaded'
                        else:
                            status_map['ollama'] = 'pending_upload'
                    else:
                        status_map['ollama'] = 'pending_upload'
            else: # recap
                if yt_ids:
                    status_map['gemini'] = 'uploaded'
                else:
                    status_map['gemini'] = 'pending_upload'
                    
    return status_map

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
