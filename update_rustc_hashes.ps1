param (
    [string]$riftFolder = ".",
    [string]$outputFile = "",
    [string]$pyScript   = "",
    [string]$tmpFile    = ""
)

function Get-Randomized-Name {
    param (
        [int]$Length = 5  # Default length is 5
    )

    # Define character set (letters and digits)
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

    # Generate random string
    $randomName = -join ((1..$Length) | ForEach-Object { $chars[(Get-Random -Minimum 0 -Maximum $chars.Length)] })

    return $randomName
}

function Test-AWSInstallation {
    try {
        # Try to get the path of aws executable
        $awsPath = Get-Command aws -ErrorAction Stop
        if ($awsPath) {
            return $true
        }
    }
    catch {
        return $false
    }
}

# If no overrides, use defaults
if (-not $outputFile) { $outputFile = Join-Path $riftFolder "data/rustc_hashes.json" }
if (-not $pyScript)   { $pyScript   = Join-Path $riftFolder "scripts/collect_rustc_commithashes.py" }
if (-not $tmpFile)    { $tmpFile    = Join-Path $riftFolder "tmp/$(Get-Randomized-Name).tmp" }
Write-Host "[RIFT] Updating rustc_hashes.json .."

# Check if AWS is installed
if (-not (Test-AWSInstallation))
{
    Write-Host "[RIFT] AWS not installed! AWS command line client is required"
    exit
}


if (-not (Test-Path $pyScript -PathType Leaf)) {
    Write-Host "[RIFT] Python script does not exist: $pyScript"
    exit
}
if (-not (Test-Path (Split-Path $tmpFile) -PathType Container)) {
    Write-Host "[RIFT] Tmp folder does not exist for tmpFile: $(Split-Path $tmpFile)"
    exit
}
Write-Host "[RIFT] Running AWS command, storing result in $tmpFile"

# Run AWS command
Start-Process -FilePath "aws" `
    -ArgumentList "--no-sign-request s3 ls s3://static-rust-lang-org/dist/" `
    -RedirectStandardOutput $tmpFile `
    -NoNewWindow `
    -Wait

Write-Host "[RIFT] Running rustc_collect_commithashes.py .."
Start-Process -FilePath "py" `
    -ArgumentList "$pyScript -i $tmpFile -o $outputFile" `
    -NoNewWindow `
    -Wait

Write-Host "[RIFT] Cleaning up tmp file .."
if (Test-Path $tmpFile)
{
    Remove-Item $tmpFile -Force
    Write-Host "[RIFT] Deleted temporary file $tmpFile"
}

Write-Host "[RIFT] Done!"