@echo off
set PYTHONUTF8=1
setlocal
if "%CEREBRO_PYTHON%"=="" (set CEREBRO_PYTHON=python)
"%CEREBRO_PYTHON%" "%~dp0..\cerebro\cerebro.py" %*
