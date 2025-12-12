"""
Helper script to initialize JSON file mapping commit hashes to corresponding rust version.
Python is too slow to process this IMO, we need to implement this in either golang or rust.
"""

import argparse
import re
import requests
import json
import logging
from datetime import datetime
import os


logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)


AWS_URL = "https://static.rust-lang.org/"

def parse_line(line):
    """Parse AWS S3 listing line to extract timestamp, date, and path.

    Args:
        line: String in format "YYYY-MM-DD HH:MM:SS filesize dist/YYYY-MM-DD/filename" (recursive)
               or "PRE YYYY-MM-DD/" (non-recursive, folder listing)

    Returns:
        tuple: (stored_ts, ts, path) or None if parsing fails
        For non-recursive PRE entries, returns ('folder', date, None) to indicate folder
    """
    # Try recursive format first: "YYYY-MM-DD HH:MM:SS filesize dist/YYYY-MM-DD/filename"
    pattern_recursive = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\d+\s+(dist\/(\d{4}-\d{2}-\d{2})\/.+)$'
    match = re.match(pattern_recursive, line)

    if match:
        stored_ts = match.group(1)  # "2024-10-16 18:15:30"
        path = match.group(2)        # "dist/2024-10-17/channel-rust-nightly.toml"
        ts = match.group(3)          # "2024-10-17"
        return stored_ts, ts, path

    # Try non-recursive format: "PRE YYYY-MM-DD/"
    pattern_nonrecursive = r'^\s*PRE\s+(\d{4}-\d{2}-\d{2})\/$'
    match = re.match(pattern_nonrecursive, line)

    if match:
        ts = match.group(1)  # "2024-10-17"
        return 'folder', ts, None

    return None


def is_new_entry(update_date, stored_ts):
    """Check if stored_ts is newer than update_date.

    Args:
        update_date: String timestamp in format %Y-%m-%d %H:%M:%S
        stored_ts: String timestamp in format %Y-%m-%d %H:%M:%S

    Returns:
        True if stored_ts is later than update_date, False otherwise
    """
    try:
        update_dt = datetime.strptime(update_date, "%Y-%m-%d %H:%M:%S")
        stored_dt = datetime.strptime(stored_ts, "%Y-%m-%d %H:%M:%S")
        return stored_dt > update_dt
    except Exception as e:
        logger.error(f"Error comparing timestamps: {e}")
        return False

def extract_rustc_information(url):
    """Download and parse TOML file to extract rustc version and git commit hash.

    Args:
        url: URL to the TOML file

    Returns:
        tuple: (version, git_commit_hash, hash_short) or None if parsing fails
               git_commit_hash and hash_short may be None if not present in the file
    """
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None

        content = response.text
        lines = content.split('\n')

        # Look for [pkg.rustc] section
        in_rustc_section = False
        version = None
        git_commit_hash = None
        hash_short = None

        for line in lines:
            line = line.strip()

            # Check if we're entering the rustc section
            if line == '[pkg.rustc]':
                in_rustc_section = True
                continue

            # Check if we're leaving the rustc section (new section starts)
            if in_rustc_section and line.startswith('[') and line != '[pkg.rustc]':
                break

            # Extract version and git_commit_hash if in rustc section
            if in_rustc_section:
                if line.startswith('version = '):
                    # Extract version string between quotes
                    version_match = re.search(r'version = "(.+)"', line)
                    if version_match:
                        version = version_match.group(1)
                        # Extract short hash from version string (e.g., "1.74.0-nightly (d9c8274fb 2023-09-12)")
                        short_hash_match = re.search(r'\(([0-9a-fA-F]{9})\s', version)
                        if short_hash_match:
                            hash_short = short_hash_match.group(1)

                elif line.startswith('git_commit_hash = '):
                    # Extract git commit hash between quotes
                    hash_match = re.search(r'git_commit_hash = "(.+)"', line)
                    if hash_match:
                        git_commit_hash = hash_match.group(1)

        # Return the tuple if we found at least the version
        if version is not None:
            return version, git_commit_hash, hash_short

        return None

    except Exception as e:
        logger.error(f"Error extracting rustc information from {url}: {e}")
        return None

def main(args):
    """Main."""
    logger.info(f"Collecting rustc hashes, storing results in {args.o}")
    lines = []
    json_output = None
    last_update_ts = None
    update_running = False

    if args.update is not None and os.path.isfile(args.update):
        update_running = True
        logger.info(f"Updating {args.update} file with latest rustc hashes!")
        with open(args.update, "r") as f:
            json_output = json.load(f)
            last_update_ts = json_output["update_date"]
    else:
        json_output = {"rustc_hashes": [], "update_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    
    with open(args.i, "r") as f:
        lines = f.readlines()
    logger.info(f"Total lines = {len(lines)}")

    # Iterate through each entry
    for line in lines:
        line = line.strip("\n")
        parsed = parse_line(line)
        if parsed is None:
            continue

        stored_ts, ts, path = parsed

        # Handle folder entries (non-recursive format)
        if stored_ts == 'folder':
            # For folder entries, we need to construct URLs for the TOML files
            # Try common channel files: nightly, beta, stable
            for channel in ['nightly', 'beta', 'stable']:
                channel_name = f"channel-rust-{channel}.toml"
                full_path = f"dist/{ts}/{channel_name}"
                url = f"{AWS_URL}{full_path}"

                # For update mode, use current timestamp for folder entries
                folder_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if update_running and not is_new_entry(last_update_ts, folder_ts):
                    continue

                result = extract_rustc_information(url)
                if result is None:
                    # It's okay if not all channels exist for a given date
                    continue
                version, git_commit_hash, hash_short = result

                # Extract version_short (version without parenthesis content)
                version_short = version.split('(')[0].strip() if '(' in version else version

                json_output["rustc_hashes"].append({"url": url,
                                                    "stored_ts": folder_ts,
                                                    "ts": ts,
                                                    "version": version,
                                                    "version_short": version_short,
                                                    "git_commit_hash": git_commit_hash,
                                                    "hash_short": hash_short,
                                                    "channel_name": channel_name})
                logger.info(f"Processed {url}\tversion = {version}")
            continue

        # Handle file entries (recursive format)
        if not line.endswith(".toml"):
            continue

        # If the update mode is running, check if its a new entry
        if update_running and not is_new_entry(last_update_ts, stored_ts):
            continue

        url = f"{AWS_URL}{path}"
        result = extract_rustc_information(url)
        if result is None:
            logger.error(f"Failed parsing TOML file at {url}")
            continue
        version, git_commit_hash, hash_short = result

        # Extract version_short (version without parenthesis content)
        version_short = version.split('(')[0].strip() if '(' in version else version

        # Extract channel_name from path (e.g., "dist/2021-03-16/channel-rust-nightly.toml" -> "channel-rust-nightly.toml")
        channel_name = path.split('/')[-1]

        json_output["rustc_hashes"].append({"url": url,
                                            "stored_ts": stored_ts,
                                            "ts": ts,
                                            "version": version,
                                            "version_short": version_short,
                                            "git_commit_hash": git_commit_hash,
                                            "hash_short": hash_short,
                                            "channel_name": channel_name})
        logger.info(f"Processed {url}\tversion = {version}")

    if args.update:
        with open(args.update, "w+") as f:
            json_output["update_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            json.dump(json_output, f)
    with open(args.o, "w+") as f:
       json.dump(json_output, f)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", help="Input file, result of aws --no-sign-request s3 ls s3://static-rust-lang-org/dist/ --recursive >> out.txt", required=True)
    parser.add_argument("-o", help="Output file name", default="./rustc_hashes.json")
    parser.add_argument("--update", default=None)
    main(parser.parse_args())