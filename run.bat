@echo off
REM Activate virtual environment and run Streamlit app
call .venv-1\Scripts\activate.bat
streamlit run app.py
pause