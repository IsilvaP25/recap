import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
manga_dir = os.path.join(base_dir, "outputs", "A_Killer_Lawyer")

if not os.path.exists(manga_dir):
    print("Manga dir outputs/A_Killer_Lawyer does not exist")
else:
    print(f"Listing outputs/A_Killer_Lawyer:")
    for root, dirs, files in os.walk(manga_dir):
        for f in files:
            rel_path = os.path.relpath(os.path.join(root, f), manga_dir)
            print(f" - {rel_path}")
