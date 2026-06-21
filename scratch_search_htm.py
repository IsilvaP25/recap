import os

def search_file(filepath, query):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    
    print(f"Searching for '{query}' in: {filepath}")
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    # Find all occurrences of query and print surrounding lines
    lines = content.split('\n')
    found_count = 0
    for i, line in enumerate(lines):
        if query.lower() in line.lower():
            found_count += 1
            if found_count > 30:
                print("... truncated (too many matches) ...")
                break
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            print(f"\n--- Line {i+1} ---")
            for idx in range(start, end):
                marker = ">>>" if idx == i else "   "
                print(f"{marker} {idx+1}: {lines[idx].strip()}")
                
    print(f"Total matches: {found_count}")

if __name__ == "__main__":
    search_file(r"C:\Users\ignacio\Desktop\Nueva carpeta (2)\end to end\api\youtube_api.htm", "comment")
