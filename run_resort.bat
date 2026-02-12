@echo off
echo Starting Hati House Management System...
set RESORT_NAME=Hati House
set PAGE_TITLE=QUẢN LÝ Hati House
set PAGE_ICON=🏚️
set FIREBASE_KEY_PATH=config/firebase_key.json

streamlit run main.py
pause
