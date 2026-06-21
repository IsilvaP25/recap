# 🗺️ Plan de Implementación: Motor de Scroll Dinámico para Manhwas

Este plan detalla los cambios necesarios para transformar el pipeline actual de "Manga Recap" (estático) en un sistema capaz de manejar **Manhwas (Webtoons)** con desplazamiento vertical fluido y sincronizado por audio, optimizado para GPU.

---

## 1. Fase de Detección: Clasificación Automática
Para que el usuario no tenga que configurar nada, el sistema debe "entender" qué está procesando.

- **Métrica de Decisión:** Relación de aspecto (Aspect Ratio).
- **Lógica:** Durante la extracción de imágenes del PDF (`video_assembler.py`), se medirá `Alto / Ancho`.
- **Umbral:** Si el ratio es superior a **1.5** (ej: 720x1600), la página se marca internamente como `MANHWA_MODE`.
- **Base de Datos:** Añadir una columna `origin_type` (Manga/Manhwa) en la tabla `story_history` para persistir esta decisión.

---

## 2. Fase de Cálculo: Sincronización Espacio-Tiempo
El mayor desafío es que el scroll termine justo cuando el narrador deja de hablar.

### Fórmula Maestra de Velocidad:
```
Duración_Audio (s) = T
Altura_Imagen (px) = H_img
Altura_Salida (720px) = H_out

Velocidad (px/s) = (H_img - H_out) / T
```

- **Margen de Seguridad:** Añadir un pequeño "padding" de 0.5s al inicio y final con velocidad cero para que el espectador pueda situarse antes de que empiece el movimiento.

---

## 3. Fase de Renderizado: Optimización FFmpeg GPU
El scroll tradicional por CPU consume muchos recursos. Usaremos filtros de hardware para mantener los **60 FPS**.

### Filtros Propuestos:
1. **Scale_Nvidia:** Escalar la imagen al ancho de salida de **720p (1280px)** manteniendo el ratio.
2. **Scroll Filter:**
   ```bash
   -vf "crop=1280:720:0:t*Velocidad"
   ```
3. **Encodificado:** Forzar `h264_nvenc` a **24 FPS @ 720p**. Esto garantiza un look cinematográfico, una calidad nítida y reduce drásticamente el tiempo de renderizado, manteniendo el desplazamiento suave.

---

## 4. Fase de Transiciones: XFade Vertical
Para que el paso entre páginas largas no sea brusco:
- **Efecto:** `xfade` con transición tipo `vertical_scroll`.
- **Lógica:** El final de la página N se funde con el inicio de la página N+1 mientras ambas se mueven hacia arriba.

---

## 5. Checklist de Tareas (Próxima Sesión)

1. [ ] **`db_manager.py`**: Actualizar esquema para soportar el tipo de manga.
2. [ ] **`video_assembler.py`**:
   - [ ] Implementar `class ManhwaRenderer`.
   - [ ] Crear función `calculate_scroll_params(image, audio_duration)`.
   - [ ] Actualizar el loop de renderizado para detectar el modo Manhwa.
3. [ ] **`autopilot_flow.py`**: Asegurar que los metadatos generados por la IA incluyan el tag `#Manhwa` si se detecta este modo.
4. [ ] **Pruebas de Estrés:** Probar con un capítulo de +50 páginas largas para verificar la estabilidad de la VRAM.

---

> [!NOTE]
> **Referencia Visual:** El sistema debe imitar el video de YouTube proporcionado, donde la cámara actúa como un "lector" que baja por la página, deteniéndose ligeramente en los diálogos importantes.
