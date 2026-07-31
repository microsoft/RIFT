@echo off
REM cleanup_rustup.bat
REM This script removes all installed rustup toolchains and targets

echo ========================================
echo Rustup Cleanup Script
echo ========================================
echo.
echo This script will:
echo - Remove all installed toolchains
echo - Remove all installed targets
echo.
echo WARNING: This will remove ALL Rust toolchains and targets!
echo Press Ctrl+C to cancel, or
pause

echo.
echo ========================================
echo Step 1: Listing current toolchains...
echo ========================================
rustup toolchain list

echo.
echo ========================================
echo Step 2: Removing all toolchains...
echo ========================================

REM Get list of toolchains and remove each one
for /f "tokens=1" %%i in ('rustup toolchain list') do (
    echo Removing toolchain: %%i
    rustup toolchain uninstall %%i
)

echo.
echo ========================================
echo Step 3: Listing current targets...
echo ========================================
rustup target list --installed

echo.
echo ========================================
echo Step 4: Removing all targets...
echo ========================================

REM Get list of installed targets and remove each one
for /f "tokens=1" %%i in ('rustup target list --installed') do (
    echo Removing target: %%i
    rustup target remove %%i
)

echo.
echo ========================================
echo Cleanup Complete!
echo ========================================
echo.
echo All toolchains and targets have been removed.
echo You can reinstall toolchains with: rustup toolchain install ^<toolchain^>
echo You can reinstall targets with: rustup target add ^<target^>
echo.
pause
