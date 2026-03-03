@echo off
echo === HATI House - Push Code to GitHub ===
echo.
echo Bat dau...
pause

:: --- Kiem tra Git ---
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Git chua duoc cai dat!
    pause
    exit /b 1
)

cd /d "%~dp0"
echo Thu muc hien tai: %CD%
echo.

:: --- Kiem tra .gitignore ---
if not exist ".gitignore" (
    echo Tao .gitignore...
    (
        echo config/firebase_key.json
        echo firebase_key.json
        echo .streamlit/secrets.toml
        echo .env
        echo __pycache__/
        echo venv/
        echo .venv/
    ) > .gitignore
)

:: --- Lan dau: git init ---
if not exist ".git" (
    echo Lan dau - Khoi tao Git...
    git init
    git branch -M main
    set /p REPO_URL="Nhap URL GitHub repo: "
    if "%REPO_URL%"=="" (
        echo Chua nhap URL!
        pause
        exit /b 1
    )
    git remote add origin %REPO_URL%
)

:: --- Kiem tra firebase key ---
git ls-files --cached config/firebase_key.json 2>nul | findstr /r "." >nul
if %errorlevel% equ 0 (
    git rm --cached config/firebase_key.json >nul 2>&1
    git rm --cached firebase_key.json >nul 2>&1
)

:: --- Add ---
echo Dang add files...
git add .

:: Kiem tra thay doi
git diff --cached --quiet 2>nul
if %errorlevel% equ 0 (
    echo Khong co thay doi moi!
    pause
    exit /b 0
)

echo.
echo Cac file thay doi:
git status --short
echo.

set /p MSG="Mo ta thay doi (Enter = Update code): "
if "%MSG%"=="" set MSG=Update code

git commit -m "%MSG%"

:: --- Push ---
echo Dang push len GitHub...
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo === THANH CONG! Code da duoc push len GitHub ===
) else (
    echo.
    echo === LOI! Push that bai ===
)

echo.
pause
