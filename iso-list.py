import configparser
import requests
import yaml
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import fnmatch # For wildcard matching like *.iso
import sys
import os
from operator import itemgetter
import re
import json # <-- Import the json module

# --- Configuration Loading ---
# (No changes needed here)
def load_config(config_file='iso-manager.conf'):
    """Loads configuration from the .conf file."""
    config = configparser.ConfigParser()
    if not os.path.exists(config_file):
        print(f"Error: Configuration file '{config_file}' not found.")
        print(f"Please create '{config_file}' with a [Settings] section and a 'yaml_source' key.")
        sys.exit(1)
    try:
        config.read(config_file)
        if 'Settings' not in config or 'yaml_source' not in config['Settings']:
            print(f"Error: Missing [Settings] section or 'yaml_source' key in '{config_file}'.")
            sys.exit(1)
        return config['Settings']['yaml_source']
    except configparser.Error as e:
        print(f"Error parsing config file '{config_file}': {e}")
        sys.exit(1)

# --- YAML Data Loading ---
# (No changes needed here)
def load_yaml_data(source):
    """Loads YAML data from a URL or local file."""
    try:
        if source.startswith('http://') or source.startswith('https://'):
            print(f"Fetching YAML data from URL: {source}")
            headers = {'User-Agent': 'ISO-List-Script/1.1'}
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
             print(f"Error: YAML data is empty or missing the 'distributions' key.")
             sys.exit(1)
        if not isinstance(data['distributions'], list):
             print(f"Error: The 'distributions' key in YAML must contain a list.")
             sys.exit(1)
        return data['distributions']

    except requests.exceptions.RequestException as e:
        print(f"Error fetching YAML from URL '{source}': {e}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML data from '{source}': {e}")
        sys.exit(1)
    except IOError as e:
         print(f"Error reading local YAML file '{source}': {e}")
         sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while loading YAML: {e}")
        sys.exit(1)


# --- Helper function for sorting version strings ---
# (No changes needed here)
def sort_key_version(item_dict):
    """
    Creates a sort key for version strings (like '21.10/', '22/').
    Extracts numbers and converts them to tuples of integers.
    Handles the trailing '/' if present.
    """
    version_str = item_dict.get('name', '').strip('/')
    parts = re.findall(r'\d+', version_str)
    try:
        return tuple(map(int, parts))
    except ValueError:
        return tuple(0 for _ in parts) if parts else (0,)


# --- Core ISO Finding Logic ---
# (No changes needed here)
def find_latest_iso(distro_info):
    """
    Finds the latest ISO link for a given distribution.
    Handles direct links and traversing into the latest version subdirectory if needed.
    """
    name = distro_info.get('Name', 'N/A')
    base_url = distro_info.get('URL')
    extension_pattern = distro_info.get('Extension', '*.iso')

    if not base_url or not isinstance(base_url, str) or not base_url.strip():
        print(f"\nSkipping: Invalid or missing 'URL' for distribution '{name}'.")
        return None
    if not isinstance(extension_pattern, str):
        print(f"\nSkipping: Invalid 'Extension' format for distribution '{name}'.")
        return None

    print(f"\nProcessing: {name}")
    print(f"  Base URL: {base_url}")
    print(f"  Looking for pattern: {extension_pattern}")

    session = requests.Session()
    session.headers.update({'User-Agent': 'ISO-List-Script/1.1 (+https://github.com/your_repo)'})

    try:
        # --- Attempt 1: Look for ISO directly in the base URL ---
        print(f"  Attempt 1: Checking base URL directly: {base_url}")
        response = session.get(base_url, timeout=20)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        if 'html' not in content_type:
             print(f"  Warning: Content-Type at {base_url} is '{content_type}', not HTML. Parsing might fail.")

        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)

        matching_files = []
        for link in links:
            href = link['href']
            if not href or href.startswith(('../', '/', '?', '#', 'mailto:')) or '://' in href:
                 if not href.startswith(base_url):
                    continue
            filename = href.split('/')[-1]
            if fnmatch.fnmatch(filename, extension_pattern):
                full_url = urljoin(base_url, href)
                matching_files.append({'filename': filename, 'url': full_url, 'name': filename})

        if matching_files:
            matching_files.sort(key=sort_key_version, reverse=True)
            latest_file = matching_files[0]
            print(f"  Found direct match: {latest_file['filename']}")
            if not latest_file['url'].startswith(('http://', 'https://')):
                 print(f"  Error: Constructed URL '{latest_file['url']}' is not absolute.")
                 return None
            return latest_file['url']

        # --- Attempt 2: If no direct ISO match, look for version directories ---
        print(f"  No direct ISO match found. Attempt 2: Looking for version directories...")
        version_dirs = []
        for link in links:
            href = link['href']
            if href.endswith('/') and href != '../' and not href.startswith(('?', '#')):
                if re.search(r'\d', href):
                    dir_name = href
                    version_dirs.append({'name': dir_name, 'url': urljoin(base_url, href)})

        if not version_dirs:
            print("  No suitable version directories found at the base URL.")
            return None

        version_dirs.sort(key=sort_key_version, reverse=True)
        latest_dir_info = version_dirs[0]
        latest_dir_url = latest_dir_info['url']
        print(f"  Found latest potential version directory: {latest_dir_info['name']} -> {latest_dir_url}")

        # --- Attempt 3: Fetch the latest version directory and look for ISOs there ---
        print(f"  Attempt 3: Checking inside directory: {latest_dir_url}")
        response_subdir = session.get(latest_dir_url, timeout=20)
        response_subdir.raise_for_status()
        content_type_subdir = response_subdir.headers.get('Content-Type', '').lower()
        if 'html' not in content_type_subdir:
             print(f"  Warning: Content-Type at {latest_dir_url} is '{content_type_subdir}', not HTML. Parsing might fail.")

        soup_subdir = BeautifulSoup(response_subdir.text, 'html.parser')
        links_subdir = soup_subdir.find_all('a', href=True)

        matching_files_subdir = []
        for link in links_subdir:
            href = link['href']
            if not href or href.startswith(('../', '/', '?', '#', 'mailto:')) or '://' in href:
                 if not href.startswith(latest_dir_url):
                    continue
            filename = href.split('/')[-1]
            if fnmatch.fnmatch(filename, extension_pattern):
                full_url = urljoin(latest_dir_url, href)
                matching_files_subdir.append({'filename': filename, 'url': full_url, 'name': filename})

        if not matching_files_subdir:
            print(f"  No files matching pattern '{extension_pattern}' found in directory '{latest_dir_info['name']}'.")
            return None

        matching_files_subdir.sort(key=sort_key_version, reverse=True)
        latest_file_subdir = matching_files_subdir[0]
        print(f"  Selected latest from subdirectory: {latest_file_subdir['filename']}")
        if not latest_file_subdir['url'].startswith(('http://', 'https://')):
             print(f"  Error: Constructed URL '{latest_file_subdir['url']}' is not absolute.")
             return None
        return latest_file_subdir['url']

    except requests.exceptions.Timeout:
        print(f"  Error: Timeout occurred during request.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  Error during network request: {e}")
        return None
    except Exception as e:
        print(f"  An unexpected error occurred while processing '{name}': {e}")
        # import traceback
        # traceback.print_exc()
        return None
    finally:
        session.close()

# --- Main Execution (MODIFIED) ---
if __name__ == "__main__":
    target_distro_name_arg = None
    if len(sys.argv) > 1:
        target_distro_name_arg = sys.argv[1]
        print(f"Target distribution specified via command line: '{target_distro_name_arg}'")

    yaml_source = load_config()
    all_distros = load_yaml_data(yaml_source)

    results = {}
    processed_count = 0
    error_count = 0

    # --- Process Distributions ---
    for distro_info in all_distros:
        current_name = distro_info.get('Name')
        if not current_name:
            print("\nSkipping entry with missing 'Name'.")
            continue

        # If a specific target was given, only process that one
        if target_distro_name_arg and current_name != target_distro_name_arg:
            continue
        # Mark if the target was found (even if processing fails later)
        elif target_distro_name_arg and current_name == target_distro_name_arg:
             # No specific action needed here now, just proceed to process
             pass
        elif target_distro_name_arg and current_name != target_distro_name_arg:
            # If target specified, skip others
            continue


        # Process the current distribution
        latest_iso_url = find_latest_iso(distro_info)
        results[current_name] = latest_iso_url # Store result (URL or None)
        processed_count += 1
        if latest_iso_url is None:
            error_count += 1

    # --- Check if the specified target was actually in the YAML ---
    if target_distro_name_arg and target_distro_name_arg not in results:
         # This handles the case where the arg was given, but no matching 'Name' was found in the YAML list
         print(f"\nError: Distribution named '{target_distro_name_arg}' not found in the YAML data.")
         sys.exit(1) # Exit if the specific target wasn't found


    # --- Save Results to JSON File ---
    output_filename = "links.json"
    try:
        print(f"\nWriting results to {output_filename}...")
        with open(output_filename, 'w', encoding='utf-8') as f:
            # Use indent for pretty printing, ensure_ascii=False if needed for non-ASCII names
            json.dump(results, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved results to {output_filename}")
    except IOError as e:
        print(f"Error writing results to {output_filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while saving JSON: {e}")

    # --- Optional: Print Summary to Console ---
    print("\n--- Processing Summary ---")
    if target_distro_name_arg:
        url = results.get(target_distro_name_arg) # Use .get for safety
        status = "Found" if url else "Not Found or Error"
        print(f"Processed target '{target_distro_name_arg}': Status = {status}")
    else:
        print(f"Processed {processed_count} distribution(s).")
        print(f"Errors/Not Found: {error_count}")
    print(f"Results saved in: {output_filename}")
    print("--------------------------")
