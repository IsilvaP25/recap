import os

base_proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
outputs_dir = os.path.join(base_proj, "outputs")

print("Checking MINIATURAS folders...")
found_any = False

if os.path.exists(outputs_dir):
    for manga in sorted(os.listdir(outputs_dir)):
        manga_path = os.path.join(outputs_dir, manga)
        if os.path.isdir(manga_path):
            min_dir = os.path.join(manga_path, "MINIATURAS")
            if os.path.exists(min_dir):
                base_images = []
                for f in os.listdir(min_dir):
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and not f.startswith("MegaRecap_"):
                        base_images.append(f)
                if base_images:
                    print(f"Manga: {manga.replace('_', ' ')}")
                    print(f"  Folder: {min_dir}")
                    print(f"  Base Images: {base_images}")
                    found_any = True

if not found_any:
    print("No mangas found with base images in their MINIATURAS directory.")
