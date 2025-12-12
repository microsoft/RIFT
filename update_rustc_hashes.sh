
#!/bin/bash

# Default values
riftFolder="."
outputFile=""
pyScript=""
tmpFile=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --riftFolder) riftFolder="$2"; shift 2 ;;
        --outputFile) outputFile="$2"; shift 2 ;;
        --pyScript) pyScript="$2"; shift 2 ;;
        --tmpFile) tmpFile="$2"; shift 2 ;;
        *) shift ;;
    esac
done

# Function to generate a random name
get_randomized_name() {
    local length=${1:-5}
    local chars='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    local randomName=""
    for ((i=0; i<length; i++)); do
        randomName+="${chars:RANDOM%${#chars}:1}"
    done
    echo "$randomName"
}

# Function to check AWS installation
test_aws_installation() {
    if command -v aws >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# If no overrides, use defaults
[[ -z "$outputFile" ]] && outputFile="$riftFolder/data/rustc_hashes.json"
[[ -z "$pyScript" ]] && pyScript="$riftFolder/scripts/collect_rustc_commithashes.py"
[[ -z "$tmpFile" ]] && tmpFile="$riftFolder/tmp/$(get_randomized_name).tmp"

echo "[RIFT] Updating rustc_hashes.json .."

# Check if AWS is installed
if ! test_aws_installation; then
    echo "[RIFT] AWS not installed! AWS command line client is required"
    exit 1
fi

# Validate paths
if [[ ! -f "$pyScript" ]]; then
    echo "[RIFT] Python script does not exist: $pyScript"
    exit 1
fi

tmpDir=$(dirname "$tmpFile")
if [[ ! -d "$tmpDir" ]]; then
    echo "[RIFT] Tmp folder does not exist for tmpFile: $tmpDir"
    exit 1
fi

# Check if we're updating an existing file
updateMode=false
pyArgs="-i \"$tmpFile\" -o \"$outputFile\""

if [[ -f "$outputFile" ]]; then
    updateMode=true
    echo "[RIFT] Existing rustc_hashes.json found, running in update mode"
    echo "[RIFT] Running AWS command (non-recursive), storing result in $tmpFile"
    # Run AWS command without --recursive for update mode
    aws --no-sign-request s3 ls s3://static-rust-lang-org/dist/ --output text --region us-west-2 > "$tmpFile"
    pyArgs="$pyArgs --update \"$outputFile\""
else
    echo "[RIFT] No existing rustc_hashes.json found, running full collection"
    echo "[RIFT] Running AWS command (recursive), storing result in $tmpFile"
    # Run AWS command with --recursive for full collection
    aws --no-sign-request s3 ls s3://static-rust-lang-org/dist/ --recursive --output text --region us-west-2 > "$tmpFile"
fi

echo "[RIFT] Running rustc_collect_commithashes.py .."
python3 $pyScript $pyArgs

echo "[RIFT] Cleaning up tmp file .."
if [[ -f "$tmpFile" ]]; then
    rm -f "$tmpFile"
    echo "[RIFT] Deleted temporary file $tmpFile"
fi

echo "[RIFT] Done!"
