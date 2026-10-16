@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Hot Wheels DB - Atualizar
cd /d "%~dp0scraper"
echo ============================================
echo   Hot Wheels DB - baixar wiki e montar DB
echo ============================================
if exist ".venv\Scripts\python.exe" goto RUN
rem Procura um Python que REALMENTE funcione (o launcher "py" pode apontar para instalacao removida)
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
if not defined PY (
  echo.
  echo ERRO: nenhum Python funcionando foi encontrado.
  echo Instale o Python 3.12 ou 3.13 em https://www.python.org/downloads/
  echo e marque a opcao "Add python.exe to PATH" na primeira tela do instalador.
  pause & exit /b 1
)
echo Preparando o ambiente na primeira execucao...
%PY% -m venv .venv || (echo ERRO ao criar o ambiente. & pause & exit /b 1)
:RUN
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
".venv\Scripts\python.exe" atualizar_db.py %*
echo.
pause
