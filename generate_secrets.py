"""
Script tự động chuyển đổi firebase_key.json → TOML format
để paste vào Streamlit Cloud Secrets.

Cách dùng:
    python generate_secrets.py

Output sẽ in ra nội dung TOML để copy-paste vào Streamlit Cloud > App Settings > Secrets.
"""

import json
import os
import sys

def main():
    # Tìm firebase_key.json
    paths_to_check = [
        os.path.join("config", "firebase_key.json"),
        "firebase_key.json",
    ]
    
    key_path = None
    for p in paths_to_check:
        if os.path.exists(p):
            key_path = p
            break
    
    if not key_path:
        print("❌ Không tìm thấy firebase_key.json!")
        print("   Đặt file vào thư mục config/ hoặc thư mục gốc của dự án.")
        sys.exit(1)
    
    print(f"📂 Đọc file: {key_path}")
    
    with open(key_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Tạo nội dung TOML
    print("\n" + "=" * 60)
    print("📋 COPY NỘI DUNG DƯỚI ĐÂY VÀO STREAMLIT CLOUD SECRETS:")
    print("=" * 60 + "\n")
    
    print("[firebase]")
    for key, value in data.items():
        if isinstance(value, str):
            # Escape backslash-n trong private_key
            escaped = value.replace("\\", "\\\\").replace("\n", "\\n")
            print(f'{key} = "{escaped}"')
        elif isinstance(value, (int, float)):
            print(f'{key} = {value}')
        elif isinstance(value, bool):
            print(f'{key} = {"true" if value else "false"}')
        else:
            print(f'{key} = "{value}"')
    
    print("\n" + "=" * 60)
    print("✅ Copy toàn bộ nội dung trên (bao gồm [firebase])")
    print("   rồi paste vào: Streamlit Cloud > App Settings > Secrets")
    print("=" * 60)

if __name__ == "__main__":
    main()
