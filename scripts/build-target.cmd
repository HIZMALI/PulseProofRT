@echo off
setlocal
if not defined QNX_SDP (
    echo Set QNX_SDP to your licensed QNX SDP 8.0 directory.
    exit /b 2
)
call "%QNX_SDP%\qnxsdp-env.bat" >nul
@echo off
if errorlevel 1 exit /b %errorlevel%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Assert-VMStopped.ps1"
if errorlevel 1 exit /b %errorlevel%
if not exist "%~dp0..\artifacts\vm" mkdir "%~dp0..\artifacts\vm"
cd /d "%~dp0..\artifacts\vm"
if errorlevel 1 exit /b %errorlevel%
if not exist ..\ssh\target_ed25519.pub exit /b 2
if not exist local\snippets mkdir local\snippets
copy /y "%~dp0image-system-files.custom" local\snippets\system_files.custom >nul
if errorlevel 1 exit /b %errorlevel%
copy /y "%~dp0image-ifs-files.custom" local\snippets\ifs_files.custom >nul
if errorlevel 1 exit /b %errorlevel%
@echo off
mkqnximage --type=vmware --arch=x86_64 --hostname=pulseproof-qnx --cpu=2 --ram=2G --graphics=no --boot-mode=uefi --ssh-ident=../ssh/target_ed25519.pub --sshd-pregen=yes --noprompt --build
exit /b %errorlevel%

