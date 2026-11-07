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
if not exist build mkdir build
qcc -Vgcc_ntox86_64 -std=c11 -D_QNX_SOURCE -Wall -Wextra -Werror -O2 -g -o build\pp-agent agent\main.c agent\timing.c agent\ipc.c agent\load.c agent\system.c agent\service_probe.c
if errorlevel 1 exit /b %errorlevel%
qcc -Vgcc_ntox86_64 -std=c11 -D_QNX_SOURCE -Wall -Wextra -Werror -O2 -g -DSERVICE_DELAY_US=0 -DSERVICE_BUILD_ID=1 -o build\telemetry-baseline examples\telemetry-service\service.c
if errorlevel 1 exit /b %errorlevel%
qcc -Vgcc_ntox86_64 -std=c11 -D_QNX_SOURCE -Wall -Wextra -Werror -O2 -g -DSERVICE_DELAY_US=5000 -DSERVICE_BUILD_ID=2 -o build\telemetry-regressed examples\telemetry-service\service.c
if errorlevel 1 exit /b %errorlevel%
python scripts\build_manifest.py
if errorlevel 1 exit /b %errorlevel%
call "%~dp0build-hello.cmd"
exit /b %errorlevel%
