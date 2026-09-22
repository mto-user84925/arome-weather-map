@echo off
title Météo AROME HD & Multi-Modèles — Serveur Local
cd /d "%~dp0"
echo ======================================================================
echo    Synchronisation avec le Cloud GitHub (Recuperation des cartes)...
echo ======================================================================
git pull origin main --quiet 2>nul
echo ======================================================================
echo    Demarrage du serveur local http://localhost:8080 ...
echo ======================================================================
start "" "http://localhost:8080"
python -m http.server 8080
pause
