@echo off
setlocal

for %%I in ("%~dp0.") do set "REPO_ROOT=%%~fI"
set "ELECTRON_ROOT=%REPO_ROOT%\electron_app"

start "VISA Django" cmd /k "pushd ""%REPO_ROOT%"" && poetry run python manage.py runserver"
start "VISA Electron" cmd /k "pushd ""%ELECTRON_ROOT%"" && npm start"

endlocal