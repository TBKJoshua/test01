@echo off
TITLE Gemini IDE Launcher

ECHO =================================================
ECHO  Gemini IDE Setup ^& Launch
ECHO =================================================
ECHO.
ECHO This script will set up a virtual environment, install dependencies, and run the application.
ECHO.

REM Check if Python is available in the system's PATH.
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO ERROR: Python is not found in your system's PATH.
    ECHO Please install Python 3 from python.org and ensure it's added to your PATH.
    ECHO.
    pause
    exit /b
)

REM Check for the existence of the virtual environment directory.
IF NOT EXIST venv (
    ECHO [1/3] Creating Python virtual environment in 'venv\' directory...
    python -m venv venv
    IF %ERRORLEVEL% NEQ 0 (
        ECHO ERROR: Failed to create the virtual environment.
        pause
        exit /b
    )
    ECHO      Done.
) ELSE (
    ECHO [1/3] Virtual environment 'venv\' already exists. Skipping creation.
)
ECHO.

REM Activate the virtual environment and install packages from requirements.txt.
ECHO [2/3] Activating virtual environment and installing/updating packages...
CALL venv\Scripts\activate.bat
pip install -r requirements.txt
ECHO      Done.
ECHO.

REM Run the main Python application.
ECHO [3/3] Starting the Gemini IDE application...
ECHO      Please close this window when you are finished with the application.
ECHO.
python gemini_app.py

ECHO.
ECHO =================================================
ECHO  Application has been closed.
ECHO =================================================
pause
