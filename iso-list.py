#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- Imports ---
import configparser
import requests
import yaml
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import fnmatch # For wildcard matching like *.iso
import sys
import os
import shutil # For checking command existence
from operator import itemgetter
import re
import json
import argparse
import subprocess
# import hashlib # No longer needed for WindowsMode AWK approach

# --- Configuration Loading ---
def load_config(config_file='iso-list.conf'):
    """Loads configuration from the .conf file."""
    config = configparser.ConfigParser()
    config_data = {'settings': {}, 'scripts': {}}
    if not os.path.exists(config_file):
        print(f"Warning: Config file '{config_file}' not found. Using defaults.")
        return config_data

    try:
        config.read(config_file)
        if 'Settings' in config and 'yaml_source' in config['Settings']:
            config_data['settings']['yaml_source'] = config['Settings']['yaml_source']
        else:
             print(f"Warning: Missing [Settings] or 'yaml_source' in '{config_file}'.")

        # Only need the download script path now for WindowsMode Ensure XML step
        if 'ExternalScripts' in config:
            config_data['scripts']['download'] = config['ExternalScripts'].get('download_script_path')

        return config_data
    except configparser.Error as e:
        print(f"Error parsing config file '{config_file}': {e}. Using defaults.")
        return config_data # Return empty on parse error

# --- YAML Data Loading ---
def load_yaml_data(source):
    """Loads YAML data from a URL or local file."""
    source = source or 'distros.yaml' # Default to local file if not specified
    try:
        if source.startswith(('http://', 'https://')):
            print(f"Fetching YAML data from URL: {source}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }
            response = requests.get(source, timeout=15, headers=headers)
            response.raise_for_status()
            yaml_content = response.text
        else:
            print(f"Reading YAML data from local file: {source}")
            if not os.path.exists(source):
                print(f"Error: YAML file '{source}' not found.")
                sys.exit(1)
            with open(source, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
        data = yaml.safe_load(yaml_content)
        if not data or 'distributions' not in data:
             print(f"Error: YAML data empty or missing 'distributions'.")
             sys.exit(1)
        if not isinstance(data['distributions'], list):
             print(f"Error: YAML 'distributions' must be a list.")
             sys.exit(1)
        return data['distributions']
    except Exception as e:
        print(f"Error loading/parsing YAML from '{source}': {e}")
        sys.exit(1)


# --- Helper function for sorting version strings ---
def sort_key_version(item_dict):
    """Creates a sort key for version strings."""
    version_str = item_dict.get('name', '').strip('/')
    parts = re.findall(r'\d+', version_str)
    try:
        return tuple(map(int, parts)) if parts else (-1,)
    except ValueError:
        return (-1,) * len(parts) if parts else (-1,)

# --- Helper function to check multiple VersionMatch criteria ---
def check_version_match(item_name, version_match_criteria):
    """Checks if item name contains all specified version match criteria."""
    # Treat None or "" as no filter
    if version_match_criteria is None or version_match_criteria == "":
        return True
    if isinstance(version_match_criteria, str):
        return version_match_criteria in item_name
    elif isinstance(version_match_criteria, list):
        if not version_match_criteria: return True # Empty list matches all
        try:
            return all(str(criterion) in item_name for criterion in version_match_criteria)
        except TypeError:
             print(f"  Warning: Non-string item in VersionMatch list: {version_match_criteria}. Check YAML.")
             return False
    else:
        # Handle unexpected type for VersionMatch
        print(f"  Warning: Unexpected type for VersionMatch: {type(version_match_criteria)}. Ignoring filter.")
        return True # Default to passing if type is wrong

# --- Helper function to infer hash type ---
def infer_hash_type(pattern_or_filename, found_hash_value=None):
    """
    Infers hash type from pattern/filename first, then hash length.
    Returns common algorithm names (e.g., 'SHA256', 'MD5') or None.
    """
    if pattern_or_filename:
        name_lower = pattern_or_filename.lower()
        # Check for explicit algorithm names
        if 'sha512' in name_lower: return 'SHA512'
        if 'sha256' in name_lower: return 'SHA256'
        if 'sha1' in name_lower: return 'SHA1'
        if 'md5' in name_lower: return 'MD5'

    # Fallback: Check length of the found hash value
    if found_hash_value:
        hash_len = len(found_hash_value.strip()) # Strip whitespace just in case
        if hash_len == 128: return 'SHA512'
        if hash_len == 96: return 'SHA384'
        if hash_len == 64: return 'SHA256'
        if hash_len == 56: return 'SHA224'
        if hash_len == 40: return 'SHA1'
        if hash_len == 32: return 'MD5'

    print(f"    Could not infer hash type from pattern '{pattern_or_filename}' or hash length.")
    return None # Cannot determine

# --- Helper function to parse hash file content ---
def parse_hash_file(hash_content, target_iso_filename):
    """
    Parses standard checksum file formats (like sha256sum output)
    to find the hash for a specific target filename.
    """
    print(f"    Parsing hash file content for '{target_iso_filename}'...")
    hash_value = None
    line_regex = re.compile(r'^([a-fA-F0-9]{32,})\s+([* ]?)(.*)')

    lines = hash_content.splitlines()
    for line_num, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#'): continue

        match = line_regex.match(line)
        if match:
            potential_hash, separator, filename_part = match.groups()
            if filename_part == target_iso_filename or filename_part.endswith('/' + target_iso_filename):
                 print(f"      Found hash for '{target_iso_filename}' on line {line_num+1}: {potential_hash}")
                 hash_value = potential_hash; break

        elif '=' in line and '(' in line and ')' in line:
             parts = line.split('=', 1)
             if len(parts) == 2:
                 left_part, potential_hash = parts[0].strip(), parts[1].strip()
                 name_match = re.search(r'\((.*?)\)', left_part)
                 if name_match:
                      filename_in_parens = name_match.group(1)
                      if filename_in_parens == target_iso_filename and re.match(r'^[a-fA-F0-9]{32,}$', potential_hash):
                           print(f"      Found hash (alt format) for '{target_iso_filename}' on line {line_num+1}: {potential_hash}")
                           hash_value = potential_hash; break

    if not hash_value:
        print(f"    Hash for '{target_iso_filename}' not found within the hash file content.")

    return hash_value

# --- Core ISO/ESD Finding Logic (Web Scraping - find_iso_web) ---
def find_iso_web(distro_info):
    """
    Finds the ISO/ESD link AND its hash via web scraping.
    Respects VersionMatch criteria. Avoids aliases only if VersionMatch is None or "".
    Returns dict {'url': iso_url, 'hash_type': type, 'hash_value': val} or None.
    """
    name = distro_info.get('Name', 'N/A')
    base_url = distro_info.get('URL')
    extension_pattern = distro_info.get('Extension') # Required in YAML
    version_match_input = distro_info.get('VersionMatch')
    hash_match_pattern = distro_info.get('HashMatch')
    path_navigation = distro_info.get('PathNavigation', []) # New field for directory navigation
    
    # --- Handle DIRECT directive ---
    direct_url = distro_info.get('DIRECT')
    if direct_url and isinstance(direct_url, str):
        print(f"\nProcessing (DIRECT Mode): {name}")
        
        # Get version from YAML or default to Unknown
        version = distro_info.get('Version', "Unknown")
        print(f"  Using version from YAML: {version}")
        
        # Get SHA256 from YAML
        direct_hash = distro_info.get('SHA256')
        if not direct_hash:
            print(f"  Warning: No SHA256 provided for DIRECT download")
            
        print(f"  Using direct URL: {direct_url}")
        if direct_hash:
            print(f"  Using provided SHA256: {direct_hash}")
            
        # Try to get file size
        file_size = None
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://getfedora.org/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            })
            
            head_response = session.head(direct_url, timeout=15, allow_redirects=True)
            head_response.raise_for_status()
            content_length = head_response.headers.get('Content-Length')
            if content_length:
                file_size = int(content_length)
                print(f"  Size: {file_size} bytes")
        except Exception as e:
            print(f"  Error getting file size: {e}")
        
        # Make sure version is the correct one from YAML    
        result = {
            'url': direct_url, 
            'hash_type': 'SHA256', 
            'hash_value': direct_hash, 
            'version': version  # Use version from YAML
        }
        if file_size:
            result['size'] = file_size
            
        print(f"  Final result data: {result}")
        return result

    # --- Regular processing for non-DIRECT entries ---
    # --- Validation ---
    if not base_url or not isinstance(base_url, str) or not base_url.strip():
        print(f"\nSkipping: Invalid/missing 'URL' for '{name}'.")
        return None
    if not extension_pattern or not isinstance(extension_pattern, str):
        print(f"\nSkipping: Invalid or missing 'Extension' for '{name}'. Must be string pattern.")
        return None
    if version_match_input is not None and version_match_input != "" and not isinstance(version_match_input, (str, list)):
        print(f"\nWarning: Invalid type for 'VersionMatch' in '{name}'. Ignoring filter.")
        version_match_input = None
    if hash_match_pattern is not None and not isinstance(hash_match_pattern, str):
         print(f"\nWarning: Invalid type for 'HashMatch' in '{name}'. Ignoring hash search.")
         hash_match_pattern = None
    if not isinstance(path_navigation, list):
         print(f"\nWarning: Invalid type for 'PathNavigation' in '{name}'. Must be a list of directory names.")
         path_navigation = []

    print(f"\nProcessing (Web): {name}")
    print(f"  Base URL: {base_url}")
    print(f"  Looking for pattern: {extension_pattern}")
    print(f"  VersionMatch criteria: {version_match_input}")
    if hash_match_pattern: print(f"  Looking for Hash pattern: {hash_match_pattern}")
    if path_navigation: print(f"  Path navigation sequence: {path_navigation}")

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://getfedora.org/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }) # More browser-like headers to avoid 403 errors on mirrors

    selected_file_url = None; selected_filename = None
    file_directory_url = None; directory_links = []

    try:
        # --- Attempt 1: Look for file directly in the base URL ---
        print(f"  Attempt 1: Checking base URL: {base_url}")
        retry_count = 0
        max_retries = 5
        original_url = base_url
        
        while retry_count < max_retries:
            try:
                response = session.get(base_url, timeout=20)
                
                # Check for error responses that might indicate mirror issues
                if response.status_code in (403, 404, 500):
                    print(f"    Received {response.status_code} error from {base_url}")
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"    Exceeded max retries ({max_retries}). Giving up.")
                        return None
                        
                    print(f"    Retry {retry_count}/{max_retries}: Starting over with original URL")
                    # Reset to original URL
                    base_url = original_url
                    continue
                    
                response.raise_for_status()
                break  # Success, exit retry loop
                
            except requests.exceptions.RequestException as e:
                print(f"    Error during request: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"    Exceeded max retries ({max_retries}). Giving up.")
                    return None
                    
                print(f"    Retry {retry_count}/{max_retries}: Starting over with original URL")
                base_url = original_url
                continue
                
        # Get content type and prepare soup outside the retry loop
        content_type = response.headers.get('Content-Type', '').lower()
        if 'html' not in content_type: print(f"  Warn: Non-HTML at {base_url}")

        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        directory_links = links
        file_directory_url = base_url

        potential_files = []
        for link in links:
            href = link['href']
            if not href or href.startswith(('../', '/', '?', '#', 'mailto:')) or '://' in href:
                 if not href.startswith(base_url): continue
            filename = href.split('/')[-1]
            if fnmatch.fnmatch(filename, extension_pattern) and \
               check_version_match(filename, version_match_input):
                full_url = urljoin(base_url, href)
                potential_files.append({'filename': filename, 'url': full_url, 'name': filename})

        if potential_files:
            potential_files.sort(key=sort_key_version, reverse=True)
            selected_file = potential_files[0]
            print(f"  Found matching file directly: {selected_file['filename']}")
            if selected_file['url'].startswith(('http://', 'https://')):
                selected_file_url = selected_file['url']; selected_filename = selected_file['filename']
            else: print(f"  Error: Constructed URL '{selected_file['url']}' is not absolute."); return None
            # If we found the file directly, skip path navigation
            path_navigation = []

        # --- Attempt 2 & 3: Only if file not found directly ---
        if selected_file_url is None:
            print(f"  Attempt 2: Looking for version directories...")
            potential_dirs = []
            for link in links:
                href = link['href']
                if href.endswith('/') and href != '../' and not href.startswith(('?', '#')):
                    dir_name = href.strip('/')
                    if check_version_match(dir_name, version_match_input):
                        # Use effective version match to decide if sanity check needed
                        effective_vm = version_match_input if version_match_input else None
                        if effective_vm is not None or re.search(r'\d', dir_name) or len(dir_name) < 15 :
                             potential_dirs.append({'name': dir_name, 'url': urljoin(base_url, href)})

            if not potential_dirs: print("  No suitable version directories found."); return None
            potential_dirs.sort(key=sort_key_version, reverse=True)
            print(f"  Found {len(potential_dirs)} potential dirs matching criteria.")

            target_dir_info = None
            effective_vm = version_match_input if version_match_input else None
            if effective_vm is None:
                print(f"  Selecting best directory (No VersionMatch, avoiding aliases)...")
                avoid = ["latest", "current", "stable"]
                for pd in potential_dirs:
                    last = pd.get('name', '').rsplit('/', 1)[-1] or pd.get('name', '')
                    if last.lower() in avoid: print(f"    Skip '{pd['name']}' (alias '{last}')."); continue
                    print(f"    Select candidate (non-alias): '{pd['name']}'"); target_dir_info = pd; break
                if target_dir_info is None and potential_dirs: print("  WARN: Only alias dirs found. Fallback."); target_dir_info = potential_dirs[0]
            else:
                print(f"  Selecting highest version dir strictly matching VersionMatch...")
                if potential_dirs: target_dir_info = potential_dirs[0]; print(f"    Select candidate (strict match): '{target_dir_info['name']}'")
            if target_dir_info is None: print("  Failed to select target directory."); return None

            target_dir_url = target_dir_info['url']
            print(f"  Selected target directory: {target_dir_info['name']}/ -> {target_dir_url}")

            # --- Handle PathNavigation if specified ---
            if path_navigation:
                print(f"  Following path navigation sequence: {path_navigation}")
                current_url = target_dir_url
                original_url = target_dir_url  # Save original URL for retries
                retry_count = 0
                max_retries = 5
                
                # Keep track of where we are in the path navigation
                navigation_index = 0
                while navigation_index < len(path_navigation) and retry_count < max_retries:
                    dir_name = path_navigation[navigation_index]
                    print(f"    Navigating to: {dir_name}")
                    try:
                        resp = session.get(current_url, timeout=20)
                        
                        # Check for error responses that might indicate mirror issues
                        if resp.status_code in (403, 404, 500):
                            print(f"    Received {resp.status_code} error from {current_url}")
                            retry_count += 1
                            if retry_count >= max_retries:
                                print(f"    Exceeded max retries ({max_retries}). Giving up.")
                                return None
                                
                            print(f"    Retry {retry_count}/{max_retries}: Starting over with original URL")
                            # Reset to original URL and start path navigation over
                            current_url = original_url
                            navigation_index = 0
                            continue
                            
                        resp.raise_for_status()
                        
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        links = soup.find_all('a', href=True)
                        
                        # Find the matching directory
                        found = False
                        for link in links:
                            href = link['href']
                            if href.endswith('/') and href.strip('/') == dir_name:
                                current_url = urljoin(current_url, href)
                                found = True
                                break
                        
                        if not found:
                            print(f"    Error: Directory '{dir_name}' not found in {current_url}")
                            return None
                            
                        # Successfully navigated to this directory, move to next
                        navigation_index += 1
                            
                    except requests.exceptions.RequestException as e:
                        print(f"    Error navigating to {dir_name}: {e}")
                        return None
                
                if retry_count >= max_retries:
                    print(f"  Failed to navigate path after {max_retries} retries")
                    return None
                    
                target_dir_url = current_url
                print(f"  Final navigation URL: {target_dir_url}")

            print(f"  Attempt 3: Checking inside: {target_dir_url}")
            try: resp_subdir = session.get(target_dir_url, timeout=20); resp_subdir.raise_for_status()
            except requests.exceptions.RequestException as e_sub: print(f"  ERR fetch dir '{target_dir_url}': {e_sub}"); return None
            file_directory_url = target_dir_url
            soup_subdir = BeautifulSoup(resp_subdir.text, 'html.parser'); links_subdir = soup_subdir.find_all('a', href=True)
            directory_links = links_subdir

            matching_files_subdir = []
            for link in links_subdir:
                href = link['href']
                if not href or href.startswith(('../', '/', '?', '#', 'mailto:')) or '://' in href:
                     if not href.startswith(target_dir_url): continue
                filename = href.split('/')[-1]
                if fnmatch.fnmatch(filename, extension_pattern) and check_version_match(filename, version_match_input):
                     full_url = urljoin(target_dir_url, href); matching_files_subdir.append({'filename': filename, 'url': full_url, 'name': filename})
            if not matching_files_subdir: print(f"  No files matching criteria found in dir '{target_dir_info['name']}'."); return None
            matching_files_subdir.sort(key=sort_key_version, reverse=True)
            selected_file_subdir = matching_files_subdir[0]; print(f"  Selected final file: {selected_file_subdir['filename']}")
            if selected_file_subdir['url'].startswith(('http://', 'https://')):
                 selected_file_url = selected_file_subdir['url']; selected_filename = selected_file_subdir['filename']
            else: print(f"  ERR: Bad URL '{selected_file_subdir['url']}'"); return None

        # --- Hash File Search (Common path) ---
        if selected_file_url:
             print(f"  Selected file: {selected_file_url}")
             
             # --- Extract Version from filename ---
             # Check for explicit version in YAML first
             version = distro_info.get('Version')
             if version:
                 print(f"  Using explicit version from YAML: {version}")
             else:
                 # Try to extract version from URL or filename if not in YAML
                 version = "Unknown (est)" # Default
                 # Try to extract version from URL
                 match = re.search(r'(\d+\.\d+(?:\.\d+)?(?:-\d+)?)', selected_filename)
                 if match:
                     version = match.group(1) # <-- Simpler extraction
                     print(f"  Extracted version from filename: {version}")
                 # If that failed, try to get it from directory path
                 elif any(re.search(r'\/(\d+\.\d+(?:\.\d+)?(?:-\d+)?)(?=\/|$)', part) for part in dir_path_parts):
                     match_dir = re.search(r'\/(\d+\.\d+(?:\.\d+)?(?:-\d+)?)(?=\/|$)', '/'.join(dir_path_parts))
                     if match_dir:
                         version = match_dir.group(1) + " (from dir)" # <-- Simpler extraction
                         print(f"  Extracted version from directory: {version}")
                 else:
                     print(f"  No version pattern found in URL or filename, using default.")
             
             print(f"  Extracted Version: {version}")

             result_data = {'url': selected_file_url, 'hash_type': None, 'hash_value': None, 'version': version} # Add version here
             
             # --- Get file size using HEAD request ---
             print(f"  Getting file size for {selected_file_url}...")
             try:
                 head_response = session.head(selected_file_url, timeout=15, allow_redirects=True)
                 head_response.raise_for_status()
                 content_length = head_response.headers.get('Content-Length')
                 if content_length:
                     file_size = int(content_length)
                     result_data['size'] = file_size
                     print(f"    Size: {file_size} bytes")
                 else:
                     print(f"    No Content-Length header found")
                     # If HEAD doesn't include Content-Length, try a GET with stream=True
                     print(f"    Attempting GET request with stream=True...")
                     get_response = session.get(selected_file_url, stream=True, timeout=15, allow_redirects=True)
                     get_response.raise_for_status()
                     content_length = get_response.headers.get('Content-Length')
                     if content_length:
                         file_size = int(content_length)
                         result_data['size'] = file_size
                         print(f"    Size (from GET): {file_size} bytes")
                     else:
                         print(f"    Still no Content-Length header found")
             except Exception as e:
                 print(f"    Error getting file size: {e}")
             
             # --- Direct hash value from YAML ---
             direct_hash = distro_info.get('SHA256')
             if direct_hash:
                 print(f"  Using direct SHA256 hash from YAML: {direct_hash}")
                 result_data['hash_value'] = direct_hash
                 result_data['hash_type'] = 'SHA256'
                 return result_data
             
             if hash_match_pattern and file_directory_url and directory_links:
                 print(f"  Searching for hash file matching '{hash_match_pattern}' in {file_directory_url}...")
                 found_hash_url = None; hash_file_name = None
                 for link in directory_links:
                     href = link['href']; hash_filename = href.split('/')[-1]
                     if not href or href.startswith(('?', '#', 'mailto:', '../')): continue
                     if '://' in href and not href.startswith(file_directory_url): continue
                     if fnmatch.fnmatch(hash_filename, hash_match_pattern):
                         found_hash_url = urljoin(file_directory_url, href); hash_file_name = hash_filename
                         print(f"    Found hash file: {hash_filename} -> {found_hash_url}"); break
                 if found_hash_url:
                     try:
                         print(f"    Fetching hash file: {found_hash_url}..."); resp_hash = session.get(found_hash_url, timeout=15); resp_hash.raise_for_status()
                         found_hash = parse_hash_file(resp_hash.text, selected_filename) # Use found filename
                         if found_hash:
                             result_data['hash_value'] = found_hash
                             result_data['hash_type'] = infer_hash_type(hash_file_name or hash_match_pattern, found_hash)
                             print(f"      Hash: {result_data['hash_value']} ({result_data['hash_type']})")
                         else: print(f"    Hash for '{selected_filename}' not in '{found_hash_url}'.")
                     except requests.exceptions.RequestException as e_h: print(f"    ERR fetch hash file: {e_h}")
                     except Exception as e_p: print(f"    ERR parse hash file: {e_p}")
                 else: print(f"  Hash file matching '{hash_match_pattern}' not found.")
             else: print("  Hash search skipped.")
             return result_data
        else: print("  Failed to determine file URL."); return None
    except requests.exceptions.Timeout: print(f"  Error: Timeout occurred."); return None
    except requests.exceptions.RequestException as e: error_details = f"URL: {e.request.url if e.request else 'N/A'}"; print(f"  Error during network request: {e} ({error_details})"); return None
    except Exception as e: print(f"  An unexpected error occurred processing '{name}': {e}"); return None
    finally:
        if 'session' in locals() and session: session.close()


# --- Function to get Windows ESD details via AWK on local XML ---
def get_windows_esd_details_from_xml(distro_info, config_scripts):
    """
    Ensures products.xml is cached, then uses AWK to parse it based on
    Language, Edition, Architecture criteria from distro_info.
    Returns dict {'url': esd_url, 'hash_type': 'SHA1', 'hash_value': val} or None.
    """
    name = distro_info.get('Name', 'Windows ESD')
    print(f"\nProcessing (WindowsMode - AWK Parse XML): {name}")

    # Get Required Parameters
    edition = distro_info.get('Edition'); language = distro_info.get('Language'); arch = distro_info.get('Architecture')
    if not all([edition, language, arch]): print(f"  Error: Missing required parameters (Edition, Language, Architecture) for '{name}'."); return None
    print(f"  Edition: {edition}"); print(f"  Language: {language}"); print(f"  Architecture: {arch}")

    # Determine Script Path & Cache Path
    script_name = "download-windows-esd"; default_download_script = script_name
    download_script_cmd = config_scripts.get('download') or default_download_script
    cache_dir = os.path.join(os.environ.get('XDG_CACHE_HOME', os.path.join(os.path.expanduser('~'), '.cache')), script_name)
    xml_file_path = os.path.join(cache_dir, "products.xml")

    # Check if download script exists
    if not shutil.which(download_script_cmd): print(f"  Error: Download script '{download_script_cmd}' not found/executable."); return None

    # Step 1: Ensure products.xml is cached
    print(f"  Ensuring '{xml_file_path}' is up-to-date using '{download_script_cmd}'...")
    try:
        # Run script without args to trigger its internal cache check/update
        update_proc = subprocess.run([download_script_cmd], capture_output=True, text=True, encoding='utf-8', check=False, timeout=60)
        if not os.path.exists(xml_file_path):
             print(f"  Error: '{xml_file_path}' not found after running update script.");
             if update_proc.stderr: print(f"    Script Stderr: {update_proc.stderr.strip()}"); return None
             return None # Exit if file doesn't exist
        if update_proc.returncode != 0: print(f"  Warning: Update script exited code {update_proc.returncode}. Stderr: {update_proc.stderr.strip()}")
        print(f"  '{xml_file_path}' should be ready.")
    except Exception as e: print(f"  Unexpected error running update script: {e}"); return None

    # Step 2: Prepare and Execute AWK Script
    print(f"  Parsing '{xml_file_path}' with AWK...")
    awk_script = r"""
    BEGIN { FS=">"; RS="</File>"; # Field Separator = >, Record Separator = </File>
            target_lang = "<LanguageCode>" lang "</LanguageCode>";
            target_ed = "<Edition>" ed "</Edition>";
            target_arch = "<Architecture>" arch "</Architecture>";
            found=0;
    }
    # Check if record contains all criteria
    $0 ~ target_lang && $0 ~ target_ed && $0 ~ target_arch {
        # Extract fields using gsub to remove tags
        f_name = $0; gsub(/.*<FileName>|<\/FileName>.*/, "", f_name);
        f_path = $0; gsub(/.*<FilePath>|<\/FilePath>.*/, "", f_path);
        f_sha1 = $0; gsub(/.*<Sha1>|<\/Sha1>.*/, "", f_sha1);
        f_size = $0; gsub(/.*<Size>|<\/Size>.*/, "", f_size);
        # Print results with prefixes
        print "AWK_FileName:" f_name;
        print "AWK_FilePath:" f_path;
        print "AWK_Sha1:" f_sha1;
        print "AWK_Size:" f_size;
        found=1;
        exit; # Assume only one match needed
    }
    END { if (!found) { print "AWK_Error:No matching block found" > "/dev/stderr"; exit 1 } }
    """

    awk_command = ['awk', f'-vlang={language}', f'-ved={edition}', f'-varch={arch}', awk_script, xml_file_path]
    extracted_data = {}
    print(f"  Running AWK command...") # Command can be long, skip logging full command?
    try:
        awk_result = subprocess.run(awk_command, check=True, capture_output=True, text=True, encoding='utf-8', timeout=30)
        print(f"    AWK Stdout:\n{awk_result.stdout.strip()}")
        if awk_result.stderr: print(f"    AWK Stderr:\n{awk_result.stderr.strip()}")

        if awk_result.stdout:
            for line in awk_result.stdout.strip().splitlines():
                if ':' in line: key, value = line.split(':', 1); extracted_data[key.strip()] = value.strip()
            print(f"    Parsed AWK data: {extracted_data}")
        else: print(f"    AWK command produced no output. No match found?"); return None
    except Exception as e: print(f"  Error running AWK: {e}"); return None

    # Step 4: Format Result & Extract Version
    file_path_url = extracted_data.get('AWK_FilePath')
    sha1_hash = extracted_data.get('AWK_Sha1')
    file_name = extracted_data.get('AWK_FileName') # Get filename from awk output
    file_size = extracted_data.get('AWK_Size') # Get file size from awk output
    
    # Check for explicit version in YAML first
    version = distro_info.get('Version')
    if version:
        print(f"    Using explicit version from YAML: {version}")
    else:
        # Extract version from filename if not provided in YAML
        version = "Unknown (est)" # Default
        if file_name:
            # Extract version from filename like 26100.2033.241004-2336...
            match = re.match(r'(\d+\.\d+)', file_name) # Match major.minor build at the start
            if match:
                version = match.group(1)
                # Optionally add more detail if needed, e.g., full build string
                # full_build_match = re.match(r'(\d+\.\d+\.\d+-\d+)', file_name)
                # if full_build_match: version = full_build_match.group(1)
            print(f"    Extracted Windows Version: {version}")

    if not file_path_url: print(f"  Error: Could not extract FilePath (URL) from AWK output."); return None

    result = {'url': file_path_url, 'hash_type': 'SHA1' if sha1_hash else None, 'hash_value': sha1_hash, 'source': 'WindowsMode_AWK', 'version': version}
    
    # Add file size if available
    if file_size and file_size.isdigit():
        result['size'] = int(file_size)
        print(f"    File size: {result['size']} bytes")
    
    return result


# --- Git Command Function ---
# (No changes needed)
def run_git_commands(output_filename="links.json", branch="main"):
    print("\n--- Attempting Git Operations ---")
    try:
        status_result = subprocess.run(['git', 'status', '--porcelain', output_filename], capture_output=True, text=True, check=False, encoding='utf-8')
        if status_result.returncode != 0:
             if "fatal: pathspec" in status_result.stderr and "did not match any files" in status_result.stderr: print(f"Info: '{output_filename}' not tracked/exists. Will add.")
             else: print(f"Error checking git status: {status_result.stderr}"); return False
        elif not status_result.stdout.strip() and os.path.exists(output_filename): print(f"No changes in '{output_filename}'. Nothing to commit."); return False
    except FileNotFoundError: print("Error: 'git' command not found."); return False
    except Exception as e: print(f"Unexpected error during git status check: {e}"); return False

    print(f"Changes detected or file needs adding. Proceeding.")
    commit_made = False
    try:
        print(f"Running: git add {output_filename}"); subprocess.run(['git', 'add', output_filename], check=True)
        msg = f"Update {output_filename}"; print(f"Running: git commit -m \"{msg}\"")
        commit_res = subprocess.run(['git', 'commit', '-m', msg], capture_output=True, text=True, check=False, encoding='utf-8')
        if commit_res.returncode != 0:
             if "nothing to commit" in commit_res.stdout.lower() or "no changes added" in commit_res.stdout.lower() or "nothing added" in commit_res.stderr.lower(): print("Commit skipped: No changes staged."); return False
             else: print(f"Error running 'git commit': {commit_res.stderr or commit_res.stdout}"); return False
        else: print("Commit successful."); commit_made = True
        if commit_made: print(f"Running: git push origin {branch}"); subprocess.run(['git', 'push', 'origin', branch], check=True); print("Push successful.")
        else: print("Skipping push: no new commit.")
    except FileNotFoundError: print("Error: 'git' command not found."); return False
    except subprocess.CalledProcessError as e: print(f"Error during Git op: {e}\nCmd: '{e.cmd}'\nStderr: {e.stderr}"); return False
    except Exception as e: print(f"Unexpected error during Git ops: {e}"); return False
    print("---------------------------------"); return commit_made


# --- Main Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch ISO/ESD links and hashes.')
    parser.add_argument('distro_name', metavar='DISTRO_NAME', type=str, nargs='?', help='Optional: Specific distribution name.')
    parser.add_argument('--git', action='store_true', help='Auto add/commit/push links.json.')
    args = parser.parse_args()
    target_distro_name_arg = args.distro_name; perform_git_operations = args.git
    if target_distro_name_arg: print(f"Target specified: '{target_distro_name_arg}'")
    if perform_git_operations: print("Git auto-commit/push enabled.")

    config_data = load_config(); yaml_source = config_data.get('settings', {}).get('yaml_source'); config_scripts = config_data.get('scripts', {})
    all_distros = load_yaml_data(yaml_source)

    results = {}; processed_count = 0; error_count = 0; found_target = False
    for distro_info in all_distros:
        current_name = distro_info.get('Name')
        if not current_name: print("\nSkipping entry missing 'Name'."); continue
        if target_distro_name_arg:
            if current_name == target_distro_name_arg: found_target = True
            else: continue

        # --- Check for WindowsMode ---
        if str(distro_info.get('WindowsMode')).lower() == 'enabled':
            # Use the AWK-based handler for Windows ESD metadata
            entry_data = get_windows_esd_details_from_xml(distro_info, config_scripts)
        else:
            # Use the web scraping handler for Linux/BSD etc.
            entry_data = find_iso_web(distro_info)

        results[current_name] = entry_data # Store dict or None

        processed_count += 1
        if entry_data is None or (isinstance(entry_data, dict) and not entry_data.get('url')):
            error_count += 1

    if target_distro_name_arg and not found_target: print(f"\nError: Target '{target_distro_name_arg}' not found in YAML."); sys.exit(1)

    output_filename = "links.json"; save_successful = False
    try:
        print(f"\nWriting results to {output_filename}...")
        output_dir = os.path.dirname(output_filename);
        if output_dir and not os.path.exists(output_dir): os.makedirs(output_dir); print(f"Created dir: {output_dir}")
        with open(output_filename, 'w', encoding='utf-8') as f: json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved results to {output_filename}"); save_successful = True
    except Exception as e: print(f"Error writing results to {output_filename}: {e}")

    git_outcome = False
    if perform_git_operations and save_successful: git_outcome = run_git_commands(output_filename=output_filename, branch="main")
    elif perform_git_operations and not save_successful: print("\nSkipping Git: save failed.")

    print("\n--- Processing Summary ---")
    if target_distro_name_arg:
        status = "Unknown"; res_entry = results.get(target_distro_name_arg)
        if isinstance(res_entry, dict) and res_entry.get('url'):
             status = f"Found URL (Hash: {res_entry.get('hash_type') or 'N/A'})"
        elif res_entry is None: status = "Not Found/Error/Skipped"
        else: status = "Error (No URL found)"
        print(f"Processed target '{target_distro_name_arg}': Status = {status}")
    else: print(f"Processed {processed_count} distribution(s). Errors/Skipped/Not Found: {error_count}")
    if save_successful: print(f"Results saved in: {output_filename}")
    else: print(f"Failed to save results to {output_filename}")
    if perform_git_operations: print(f"Git operations outcome: {'Commit/Push OK' if git_outcome else 'No Commit/Push Failed'}")
    print("--------------------------")
