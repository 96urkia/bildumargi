@echo off
REM Bildumargi - arranque en Windows
REM Si Python no esta en el PATH, sustituye "python" por la ruta completa
REM al ejecutable, por ejemplo: C:\Python312\python.exe
cd /d "%~dp0"
echo Carpeta: %CD%
echo.
python iniciar.py
echo.
echo La aplicacion se ha detenido.
echo Si no llego a arrancar, lee el mensaje de arriba.
pause
