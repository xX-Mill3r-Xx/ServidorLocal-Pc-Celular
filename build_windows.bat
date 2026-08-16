@echo off
py -m PyInstaller --noconfirm --clean --windowed --name LocalDrop app.py
echo Aplicativo criado em dist\LocalDrop\LocalDrop.exe
pause
