import os

root_dir = r"c:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\Proyecto manga recap"
matches = []

for root, dirs, files in os.walk(root_dir):
    # Skip folders like .git, __pycache__, outputs
    if any(p in root for p in [".git", "__pycache__", "outputs", "_TEMP"]):
        continue
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8") as file:
                    content = file.read()
                    if "db" in f.lower() or "sqlite" in content or "recap.db" in content:
                        print(f"Found candidate file: {path}")
                        if "manga_recap.db" in content:
                            print(f"  --> MATCH: contains 'manga_recap.db'")
            except Exception as e:
                pass
