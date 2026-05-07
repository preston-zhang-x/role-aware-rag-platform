@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 excel_parser_md.py
) else (
  python excel_parser_md.py
)

endlocal
