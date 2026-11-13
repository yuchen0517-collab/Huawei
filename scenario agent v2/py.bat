@echo off

chcp 65001 >nul

rem Temporary launcher: the system python command is a Windows Store stub.

rem Usage: py.bat scripts\offline_check.py

rem        py.bat -m pytest tests -q

set PYTHONDONTWRITEBYTECODE=1

"C:\Users\26913\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" %*
