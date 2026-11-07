@echo off
setlocal
if not defined QNX_SDP (
    echo Set QNX_SDP to your licensed QNX SDP 8.0 directory.
    exit /b 2
)
call "%QNX_SDP%\qnxsdp-env.bat" >nul
@echo off
if errorlevel 1 exit /b %errorlevel%
cd /d "%~dp0.."
if errorlevel 1 exit /b %errorlevel%
if not exist build mkdir build
qcc -Vgcc_ntox86_64 -Wall -Wextra -Werror -g -o build\hello examples\hello\hello.c
exit /b %errorlevel%
