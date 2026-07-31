@echo off
REM Usual path C:\Users\[USER]\AppData\Roaming\Hex-Rays\IDA Pro\plugins

if "%~1"=="" (
    echo [installUpdateIdaPlugin] No path to plugin dir provided! Usually \"%USERPROFILE%\AppData\Roaming\Hex-Rays\IDA Pro\plugins\"
    exit /b 1
)

set IdaPluginsDir=%~1

echo [installUpdateIdaPlugin] Installing/Updating RIFT Ida Pro Plugin

echo [installUpdateIdaPlugin] Copying files from plugins/Ida to %IdaPluginsDir%
copy .\plugins\Ida\rift_plugin.py "%IdaPluginsDir%\rift_plugin.py"

mkdir "%IdaPluginsDir%\librift_ida"
echo [installUpdateIdaPlugin] Copying plugin support files to %IdaPluginsDir%\librift_ida
copy .\plugins\Ida\librift_ida\__init__.py "%IdaPluginsDir%\librift_ida\__init__.py"
copy .\plugins\Ida\librift_ida\rift_form.py "%IdaPluginsDir%\librift_ida\rift_form.py"
copy .\plugins\Ida\librift_ida\rift_ida_core.py "%IdaPluginsDir%\librift_ida\rift_ida_core.py"
copy .\plugins\Ida\librift_ida\rift_controller.py "%IdaPluginsDir%\librift_ida\rift_controller.py"

mkdir "%IdaPluginsDir%\librift"
echo [installUpdateIdaPlugin] Copying core files from lib/ to %IdaPluginsDir%\librift
copy .\librift\__init__.py "%IdaPluginsDir%\librift\__init__.py"
copy .\librift\crate.py "%IdaPluginsDir%\librift\crate.py"
copy .\librift\meta_extractor.py "%IdaPluginsDir%\librift\meta_extractor.py"
copy .\librift\rift_cfg.py "%IdaPluginsDir%\librift\rift_cfg.py"
copy .\librift\rift_meta.py "%IdaPluginsDir%\librift\rift_meta.py"
copy .\librift\rustmeta.py "%IdaPluginsDir%\librift\rustmeta.py"
copy .\librift\storage_handler.py "%IdaPluginsDir%\librift\storage_handler.py"
copy .\librift\utils.py "%IdaPluginsDir%\librift\utils.py"
copy .\librift\rift_os.py "%IdaPluginsDir%\librift\rift_os.py"
copy .\librift\rift_connector.py "%IdaPluginsDir%\librift\rift_connector.py"


mkdir "%IdaPluginsDir%\rift_essentials"
mkdir "%IdaPluginsDir%\rift_essentials\work"
mkdir "%IdaPluginsDir%\rift_essentials\tmp"
echo [installUpdateIdaPlugin] Copying config and rustc_hashes.json file to %IdaPluginsDir%\rift_essentials
copy .\data\rustc_hashes.json "%IdaPluginsDir%\rift_essentials\rustc_hashes.json"

REM Ask whether to configure rift_config.cfg interactively
echo.
set /p "CONFIGURE_NOW=Do you want to configure rift_config.cfg now? (Y/N): "
if /i "%CONFIGURE_NOW%"=="Y" goto :configure

echo [installUpdateIdaPlugin] Copying existing rift_config.cfg
copy .\rift_config.cfg "%IdaPluginsDir%\rift_essentials\rift_config.cfg"
goto :done

:configure
echo.
echo [installUpdateIdaPlugin] Enter paths below. Press Enter to keep the shown default.
echo.

set "PCF_PATH=C:\Rift\binaries\pcf.exe"
set /p "PCF_PATH=Path to pcf.exe [%PCF_PATH%]: "

set "SIGMAKE_PATH=C:\Rift\binaries\sigmake.exe"
set /p "SIGMAKE_PATH=Path to sigmake.exe [%SIGMAKE_PATH%]: "

set "WORK_FOLDER=C:\RIFT\work"
set /p "WORK_FOLDER=Path to work folder [%WORK_FOLDER%]: "

set "CARGO_PROJ_FOLDER=C:\RIFT\tmp"
set /p "CARGO_PROJ_FOLDER=Path to cargo proj folder [%CARGO_PROJ_FOLDER%]: "

set "RUSTC_HASHES=C:\RIFT\data\rustc_hashes.json"
set /p "RUSTC_HASHES=Path to rustc_hashes.json [%RUSTC_HASHES%]: "

set "STRINGS_PATH=C:\Rift\binaries\strings.exe"
set /p "STRINGS_PATH=Path to strings.exe [%STRINGS_PATH%]: "

echo.
set "ENABLE_SERVER=N"
set /p "ENABLE_SERVER=Enable RiftServer? (Y/N) [N]: "

if /i "%ENABLE_SERVER%"=="Y" (
    set "SERVER_IP=127.0.0.1"
    set /p "SERVER_IP=RiftServer IP address [127.0.0.1]: "
    set "SERVER_PORT=5001"
    set /p "SERVER_PORT=RiftServer port [5001]: "
    set "SERVER_MODE=local"
    set /p "SERVER_MODE=RiftServer mode, local or remote [local]: "
    set "FLIRT_DIR=C:\RIFT\ServerStorage"
    set /p "FLIRT_DIR=RiftServer flirt_dir (storage folder) [%FLIRT_DIR%]: "
)

if /i "%SERVER_MODE%"=="remote" (
    set "API_KEY="
    set /p "API_KEY=RiftServer ApiKey: "
    set "SRC_CA_CERT="
    set /p "SRC_CA_CERT=Path to the RiftServer's TLS CA cert to pin (TlsCaCert): "
)

REM Write rift_config.cfg directly to destination
set "DEST_CFG=%IdaPluginsDir%\rift_essentials\rift_config.cfg"
echo.
echo [installUpdateIdaPlugin] Writing rift_config.cfg to %DEST_CFG%

(
echo [Default]
echo # Path to Ida Pro utility pcf.exe
echo PcfPath = %PCF_PATH%
echo # Path to Ida Pro utility sigmake.exe
echo SigmakePath = %SIGMAKE_PATH%
echo # Path to work folder, where generated files will be temporarily stored in
echo WorkFolder = %WORK_FOLDER%
echo # Path to folder, where cargo projects will be initialized
echo CargoProjFolder = %CARGO_PROJ_FOLDER%
echo # Path to generated rustc_hashes.json
echo RustcHashes = %RUSTC_HASHES%
echo # Path to strings.exe, on Windows preferably from the SysInternalsSuite by Mark Russinovich
echo StringsTool = %STRINGS_PATH%
) > "%DEST_CFG%"

if /i "%ENABLE_SERVER%"=="Y" (
    (
    echo.
    echo [RiftServer]
    echo # local or remote
    echo server_mode = %SERVER_MODE%
    echo Ip = %SERVER_IP%
    echo Port = %SERVER_PORT%
    echo flirt_dir = %FLIRT_DIR%
    ) >> "%DEST_CFG%"
)

if /i "%SERVER_MODE%"=="remote" (
    echo [installUpdateIdaPlugin] Copying TLS CA cert to %IdaPluginsDir%\rift_essentials\rift_ca_cert.pem
    copy "%SRC_CA_CERT%" "%IdaPluginsDir%\rift_essentials\rift_ca_cert.pem"
    (
    echo ApiKey = %API_KEY%
    echo TlsCaCert = %IdaPluginsDir%\rift_essentials\rift_ca_cert.pem
    ) >> "%DEST_CFG%"
)

echo [installUpdateIdaPlugin] rift_config.cfg written successfully.

:done
echo [installUpdateIdaPlugin] Done.
