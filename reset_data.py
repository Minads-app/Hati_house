"""
RESET DATA - Xoa het bookings, reset phong ve trang thai trong, xoa khach hang.
Chay: python reset_data.py
"""
import os
import sys

# Set Firebase key path
os.environ["FIREBASE_KEY_PATH"] = "config/firebase_key.json"

import firebase_admin
from firebase_admin import credentials, firestore

_APP_NAME = "reset_tool"

def get_db():
    key_path = os.environ.get("FIREBASE_KEY_PATH", "config/firebase_key.json")
    
    if _APP_NAME not in firebase_admin._apps:
        if os.path.exists(key_path):
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred, name=_APP_NAME)
        else:
            print(f"[LOI] Khong tim thay file key: {key_path}")
            sys.exit(1)
    
    return firestore.client(app=firebase_admin.get_app(_APP_NAME))

def delete_collection(db, collection_name):
    """Xoa het documents trong 1 collection"""
    docs = db.collection(collection_name).stream()
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1
    return count

def reset_rooms(db):
    """Reset tat ca phong ve trang thai available"""
    docs = db.collection("rooms").stream()
    count = 0
    for doc in docs:
        doc.reference.update({
            "status": "Trống",
            "current_booking_id": "",
            "locked_by": "",
            "lock_expires_at": None
        })
        count += 1
    return count

def main():
    print("============================================")
    print("   RESET DATA - HATI House")
    print("============================================")
    print()
    print("Se thuc hien:")
    print("  1. Xoa tat ca BOOKINGS")
    print("  2. Reset tat ca PHONG ve trang thai trong")
    print("  3. Xoa tat ca KHACH HANG")
    print()
    
    confirm = input("Ban co chac chan muon reset? (go 'YES' de xac nhan): ").strip()
    if confirm != "YES":
        print("Da huy. Khong co gi thay doi.")
        return
    
    print()
    print("Dang ket noi Firebase...")
    db = get_db()
    
    # 1. Xoa bookings
    print("  [1/3] Xoa bookings...", end=" ")
    n = delete_collection(db, "bookings")
    print(f"Da xoa {n} bookings")
    
    # 2. Reset rooms
    print("  [2/3] Reset phong...", end=" ")
    n = reset_rooms(db)
    print(f"Da reset {n} phong")
    
    # 3. Xoa customers
    print("  [3/3] Xoa khach hang...", end=" ")
    n = delete_collection(db, "customers")
    print(f"Da xoa {n} khach hang")
    
    print()
    print("============================================")
    print("   HOAN TAT! Tat ca data da duoc reset.")
    print("============================================")

if __name__ == "__main__":
    main()
