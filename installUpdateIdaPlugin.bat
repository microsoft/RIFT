@echo off
REM Usual path C:\Users\[USER]\AppData\Roaming\Hex-Rays\IDA Pro\plugins

if "%~1"=="" (
    echo [installUpdateIdaPlugin] No path to plugin dir provided! Usually %USERPROFILE%\AppData\Roaming\Hex-Rays\IDA Pro\plugins
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
echo [installUpdateIdaPlugin] Copying config and rustc_hashes.json file to %IdaPluginsDir%\rift_essentials
REM copy .\data\rustc_hashes.json "%IdaPluginsDir%\rift_essentials\rustc_hashes.json"
copy .\rift_config.cfg "%IdaPluginsDir%\rift_essentials\rift_config.cfg"
