import os
import shutil

def create_resort():
    print("========================================")
    print("   RESORT SETUP WIZARD")
    print("========================================")
    
    # 1. Ask for information
    resort_name = input("Enter Resort Name (e.g. Mui Nai Resort): ").strip()
    page_title = input(f"Enter Page Title [QUẢN LÝ {resort_name}]: ").strip() or f"QUẢN LÝ {resort_name}"
    page_icon = input("Enter Page Icon (emoji) [🏨]: ").strip() or "🏨"
    
    print("\n--- Firebase Configuration ---")
    print("Please place your firebase service account JSON file in the 'config' folder.")
    firebase_file = input("Enter the filename of your firebase key (e.g. mui_nai_key.json): ").strip()
    
    # 2. Validation
    config_dir = os.path.join(os.getcwd(), "config")
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        
    full_key_path = os.path.join(config_dir, firebase_file)
    if not os.path.exists(full_key_path):
        print(f"⚠️ Warning: File '{firebase_file}' not found in 'config/' folder.")
        print(f"   Expected path: {full_key_path}")
        print("   Please make sure to copy the file there before running the app.")
    
    # 3. Generate .env file (for local dev)
    env_content = f"""# Resort Configuration
RESORT_NAME={resort_name}
PAGE_TITLE={page_title}
PAGE_ICON={page_icon}
FIREBASE_KEY_PATH=config/{firebase_file}
"""
    with open(".env", "w", encoding="utf-8") as f:
        f.write(env_content)
    
    print("\n✅ Created .env file.")
    
    # 4. Generate startup script (run_resort.bat)
    bat_content = f"""@echo off
echo Starting {resort_name} Management System...
set RESORT_NAME={resort_name}
set PAGE_TITLE={page_title}
set PAGE_ICON={page_icon}
set FIREBASE_KEY_PATH=config/{firebase_file}

streamlit run main.py
pause
"""
    bat_file = "run_resort.bat"
    with open(bat_file, "w", encoding="utf-8") as f:
        f.write(bat_content)
        
    print(f"✅ Created {bat_file} startup script.")
    
    print("\n========================================")
    print("SETUP COMPLETE!")
    print(f"To run the app, double click: {bat_file}")
    print("========================================")

if __name__ == "__main__":
    create_resort()
