#!/usr/bin/env python3
# generate-pages.py - Generate pages for pypi
#
# This file is based on https://github.com/bartbroere/pypi.bartbroe.re/blob/main/scrape.py.
#

import json
import os
from collections import defaultdict
import requests

WHEELS_RELEASE_URL = "https://api.github.com/repos/termux-user-repository/pypi-wheel-builder/releases/latest"

def get_wheel_infos():
  res = []
  print(f"Fetching release info from {WHEELS_RELEASE_URL}...")
  try:
    resp = requests.get(WHEELS_RELEASE_URL, timeout=30) # Added timeout
    resp.raise_for_status() # Check for HTTP errors
    release_info = resp.json() # Use .json() method
  except requests.exceptions.RequestException as e:
    print(f"Error fetching release info: {e}")
    return []
  except json.JSONDecodeError as e:
    print(f"Error parsing JSON response: {e}")
    print(f"Response text: {resp.text[:500]}...") # Log part of the response
    return []

  if "assets" not in release_info:
      print("Warning: 'assets' key not found in release info.")
      print(f"Release info: {release_info}")
      return []

  for asset_info in release_info["assets"]: # Renamed loop variable for clarity
    asset_name = asset_info.get("name")
    asset_url = asset_info.get("browser_download_url")
    if asset_name and asset_url and asset_name.endswith(".whl"):
      res.append((asset_name, asset_url))
    elif asset_name and not asset_name.endswith(".whl"):
      # Optionally log non-wheel assets if needed for debugging
      # print(f"Skipping non-wheel asset: {asset_name}")
      pass
    else:
      print(f"Warning: Skipping asset with missing name or URL: {asset_info}")

  print(f"Found {len(res)} wheel files.")
  return res

def get_packages_dict(wheel_infos):
  res = defaultdict(list)
  for wheel_info in wheel_infos:
    try:
      # More robust parsing, handles cases like 'package_name_foo-1.0...'
      package_name = wheel_info[0].split("-")[0]
      package_name = package_name.replace("_", "-").lower() # Normalize to lowercase hyphenated
      res[package_name].append(wheel_info)
    except IndexError:
      print(f"Warning: Could not parse package name from wheel: {wheel_info[0]}")
  print(f"Grouped wheels into {len(res)} packages.")
  return res

def generate_packages_index(packages_dict):
  docs_dir = 'docs'
  try:
    os.makedirs(docs_dir, exist_ok=True) # Use makedirs with exist_ok=True
    print(f"Ensured directory exists: {docs_dir}")
  except OSError as e:
    print(f"Error creating directory {docs_dir}: {e}")
    return # Stop if base docs dir cannot be created

  print(f"Generating individual package index pages...")
  count = 0
  for package_name, wheels_info in packages_dict.items():
    package_dir = os.path.join(docs_dir, package_name.lower()) # Use normalized name
    try:
      os.makedirs(package_dir, exist_ok=True)
    except OSError as e:
      print(f"Error creating directory {package_dir}: {e}")
      continue # Skip this package if dir cannot be created

    index_path = os.path.join(package_dir, 'index.html')
    try:
      with open(index_path, 'w', encoding='utf-8') as package_index: # Specify encoding
        package_index.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body{{margin:40px auto;max-width:650px;line-height:1.6;font-size:18px;color:#444;padding:0 10px}}
    h1,h2,h3{{line-height:1.2}}
    a {{ display: block; margin-bottom: 5px; }} /* Style links for better readability */
    </style>
    <title>Links for {package_name.lower()}</title>
</head>
<body>
<h1>Links for {package_name.lower()}</h1>
""")
        # --- MODIFICATION START ---
        for wheel_name, wheel_url in sorted(wheels_info): # Sort wheels for consistency
            display_name = wheel_name
            if "linux_aarch64" in wheel_name:
                display_name = wheel_name.replace("linux_aarch64", "android_24_aarch64")

            # Simple check for hash (sha256 often included in GitHub URLs)
            hash_part = ""
            if '#sha256=' in wheel_url:
                 hash_part = f" data-requires-python=\"\" data-yanked=\"false\" {wheel_url[wheel_url.find('#'):]}" # PEP 503 format

            package_index.write(f'    <a href="{wheel_url}"{hash_part}>{display_name}</a><br/>\n')
        # --- MODIFICATION END ---
        package_index.write("""
</body>
</html>
""")
      count += 1
    except IOError as e:
      print(f"Error writing index file {index_path}: {e}")

  print(f"Generated {count} package index pages.")


def generate_main_pages(packages):
  docs_dir = 'docs'
  try:
    # Ensure base directory exists (might be redundant but safe)
    os.makedirs(docs_dir, exist_ok=True)
  except OSError as e:
      print(f"Error creating directory {docs_dir}: {e}")
      return

  main_index_path = os.path.join(docs_dir, 'index.html')
  print(f"Generating main index page: {main_index_path}")
  try:
    with open(main_index_path, 'w', encoding='utf-8') as main_package_index: # Specify encoding
      main_package_index.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body{{margin:40px auto;max-width:650px;line-height:1.6;font-size:18px;color:#444;padding:0 10px}}
    h1,h2,h3{{line-height:1.2}}
    a {{ display: block; margin-bottom: 5px; }}
    pre {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; }}
    </style>
    <title>Termux User Repository PyPI</title>
</head>
<body>
    <h1>Termux User Repository PyPI Index</h1>
    <p>Unofficial pre-compiled Python wheels for Termux on aarch64 (Android 7+).</p>
    <p>Use this index with pip:</p>
    <pre>pip install --upgrade pip \npip install --extra-index-url https://termux-user-repository.github.io/pypi/ SomePackage</pre>
    <h2>Packages</h2>
""")
      # Sort packages alphabetically for consistent ordering
      for package_name in sorted(packages):
          # Ensure link uses the lowercase, hyphenated version consistent with directory structure
          normalized_package_name = package_name.lower().replace("_", "-")
          main_package_index.write(f'    <a href="{normalized_package_name}/">{normalized_package_name}</a><br/>\n')
      main_package_index.write("""
</body>
</html>
""")
    print("Successfully generated main index page.")
  except IOError as e:
    print(f"Error writing main index file {main_index_path}: {e}")

def main():
  print("Starting PyPI index generation...")
  wheel_infos = get_wheel_infos()
  if not wheel_infos:
      print("No wheel information retrieved. Exiting.")
      return
  packages_dict = get_packages_dict(wheel_infos)
  if not packages_dict:
      print("No packages found after grouping wheels. Exiting.")
      return
  generate_packages_index(packages_dict)
  generate_main_pages(packages_dict.keys())
  print("PyPI index generation complete.")

if __name__ == "__main__":
  main()
