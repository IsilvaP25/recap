import os
import sys

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.pipeline import db_manager

def main():
    print(f"DB Path in db_manager: {db_manager.DB_PATH}")
    script, thumb = db_manager.get_short_script("Single_Dad_In_Another_World")
    print(f"Script: {script}")
    print(f"Thumb: {thumb}")

if __name__ == "__main__":
    main()
