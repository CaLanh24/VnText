@echo off
python "%~dp0../../../release/verify_skill.py" >nul
if errorlevel 1 exit /b %errorlevel%
call "%USERPROFILE%/.codex/skills/impeccable/scripts/impeccable.cmd" hook
