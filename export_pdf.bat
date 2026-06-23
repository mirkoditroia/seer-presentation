@echo off
setlocal
cd /d "%~dp0"
python export_pdf.py %*
exit /b %ERRORLEVEL%
