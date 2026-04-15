@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0build-windows.ps1"
