#!/usr/bin/env python3
# generate-pages.py - Generate pages for pypi
#
# This file is based on https://github.com/bartbroere/pypi.bartbroe.re/blob/main/scrape.py.
#

import json
import os
from collections import defaultdict
import requests
import shutil # Needed for efficient file copying

WHEELS_RELEASE_URL = "https://api.github.com/repos/termux-user-repository/pypi-wheel-builder/releases/latest"
DOCS_DIR = 'docs' # Define docs directory globally for consistency

# --- Helper Function for Downloading ---
def download_file(url, destination):
    """Downloads a file from a URL to a destination, streaming content."""
    print(f"Attempting download:\n  From: {url}\n  To:   {destination}")
    try:
        # Ensure the destination directory exists
        os.makedirs(os.path.dirname(destination), exist_ok=True)

        with requests.get(url, stream=True, timeout=60) as r: # Use stream=True, add timeout
            r.raise_for_status() # Check for download errors (4xx or 5xx)
            with open(destination, 'wb') as f:
                shutil.copyfileobj(r.raw, f) # Efficiently copy stream to file
        print(f"Successfully downloaded {os.path.basename(destination)}")
        return True
    except requests.exceptions.Timeout:
        print(f"Error: Timeout while downloading {url}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
    except IOError as e:
        print(f"Error writing file {destination}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during download: {e}")

    # Clean up potentially incomplete file if an error occurred
    if os.path.exists(destination):
        try:
            os.remove(destination)
            print(f"Cleaned up incomplete file: {destination}")
        except OSError as rm_err:
            print(f"Warning: Could not remove incomplete file {destination}: {rm_err}")
    return False
# --- End Helper Function ---

def get_wheel_infos():
  res = []
  print(f"Fetching release info from {WHEELS_RELEASE_URL}...")
  try:
    resp = requests.get(WHEELS_RELEASE_URL, timeout=30)
    resp.raise_for_status()
    release_info = resp.json()
  except requests.exceptions.RequestException as e:
    print(f"Error fetching release info: {e}")
    return []
  except json.JSONDecodeError as e:
    print(f"Error parsing JSON response: {e}")
    print(f"Response text: {resp.text[:500]}...")
    return []

  if "assets" not in release_info:
      print("Warning: 'assets' key not found in release info.")
      print(f"Release info: {release_info}")
      return []

  for asset_info in release_info["assets"]:
    asset_name = asset_info.get("name")
    asset_url = asset_info.get("browser_download_url")
    if asset_name and asset_url and asset_name.endswith(".whl"):
      res.append((asset_name, asset_url))
    elif asset_name and not asset_name.endswith(".whl"):
      pass
    else:
      print(f"Warning: Skipping asset with missing name or URL: {asset_info}")

  print(f"Found {len(res)} wheel files.")
  return res

def get_packages_dict(wheel_infos):
  res = defaultdict(list)
  for wheel_info in wheel_infos:
    try:
      package_name = wheel_info[0].split("-")[0]
      package_name = package_name.replace("_", "-").lower()
      res[package_name].append(wheel_info)
    except IndexError:
      print(f"Warning: Could not parse package name from wheel: {wheel_info[0]}")
  print(f"Grouped wheels into {len(res)} packages.")
  return res

def generate_packages_index(packages_dict):
  try:
    # Ensure the main docs directory exists FIRST
    os.makedirs(DOCS_DIR, exist_ok=True)
    print(f"Ensured base directory exists: {DOCS_DIR}")
  except OSError as e:
    print(f"FATAL: Error creating base directory {DOCS_DIR}: {e}")
    return # Stop if base docs dir cannot be created

  print(f"Generating individual package index pages...")
  generated_count = 0
  skipped_due_download_error = 0

  for package_name, wheels_info in packages_dict.items():
    package_dir = os.path.join(DOCS_DIR, package_name.lower())
    try:
      os.makedirs(package_dir, exist_ok=True)
    except OSError as e:
      print(f"Error creating directory {package_dir}: {e}")
      continue # Skip this package if dir cannot be created

    index_path = os.path.join(package_dir, 'index.html')
    try:
      with open(index_path, 'w', encoding='utf-8') as package_index:
        package_index.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body{{margin:40px auto;max-width:650px;line-height:1.6;font-size:18px;color:#444;padding:0 10px}}
    h1,h2,h3{{line-height:1.2}}
    a {{ display: block; margin-bottom: 5px; }}
    </style>
    <title>Links for {package_name.lower()}</title>
</head>
<body>
<h1>Links for {package_name.lower()}</h1>
""")
        # --- MODIFICATION START ---
        for wheel_name, wheel_url in sorted(wheels_info):
            display_name = wheel_name
            link_url = wheel_url # Default to original external URL
            needs_local_copy = False

            # Check if this wheel needs local download and renaming
            if "linux_aarch64" in wheel_name and "pydantic" in wheel_name:
                needs_local_copy = True
                display_name = wheel_name.replace("linux_aarch64", "android_24_aarch64")
                # Place the renamed wheel directly inside DOCS_DIR
                local_wheel_path = os.path.join(DOCS_DIR, display_name)

                # Download ONLY if the local file doesn't exist
                if not os.path.exists(local_wheel_path):
                    if not download_file(wheel_url, local_wheel_path):
                        print(f"ERROR: Failed to download/save {display_name}. Skipping link generation for this file.")
                        skipped_due_download_error += 1
                        continue # Skip adding link for this failed download

                # If download was successful or file already existed, set the relative link
                # Link from docs/<package>/index.html to docs/<wheel> is ../<wheel>
                link_url = f"../{display_name}"

            # Add hash information if available from the original URL
            # This helps pip verify integrity even if served locally sometimes
            hash_part = ""
            if '#sha256=' in wheel_url:
                 hash_part = f" data-requires-python=\"\" data-yanked=\"false\" {wheel_url[wheel_url.find('#'):]}"

            # Write the anchor tag using the determined display name and link URL
            package_index.write(f'    <a href="{link_url}"{hash_part}>{display_name}</a><br/>\n')
        # --- MODIFICATION END ---
        package_index.write("""
</body>
</html>
""")
      generated_count += 1
    except IOError as e:
      print(f"Error writing index file {index_path}: {e}")

  print(f"Generated {generated_count} package index pages.")
  if skipped_due_download_error > 0:
      print(f"Warning: Skipped adding links for {skipped_due_download_error} files due to download errors.")


def generate_main_pages(packages):
  # Ensure base directory exists (might be redundant but safe)
  try:
    os.makedirs(DOCS_DIR, exist_ok=True)
  except OSError as e:
      print(f"Error creating directory {DOCS_DIR}: {e}")
      return

  main_index_path = os.path.join(DOCS_DIR, 'index.html')
  print(f"Generating main index page: {main_index_path}")
  try:
    with open(main_index_path, 'w', encoding='utf-8') as main_package_index:
      main_package_index.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    body{{margin:40px auto;max-width:650px;line-height:1.6;font-size:18px;color:#444;padding:0 10px}}
    h1,h2,h3{{line-height:1.2}}
    a {{ display: block; margin-bottom: 5px; }}
    pre {{ background-color: #f0f0f0; padding: 10px; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; }}
    </style>
    <title>Termux User Repository PyPI</title>
</head>
<body>
    <h1>Termux User Repository PyPI Index</h1>
    <p>Unofficial pre-compiled Python wheels for Termux on aarch64 (Android 7+).</p>
    <p>Use this index with pip/uv:</p>
    <pre>pip install --upgrade pip \n# or use uv: uv pip install --upgrade pip\n\n# Install packages:\npip install --extra-index-url https://{os.environ.get('GITHUB_REPOSITORY_OWNER', 'your-github-username')}.github.io/{os.environ.get('GITHUB_REPOSITORY_NAME', 'pypi')}/ SomePackage\n# OR with uv:\nuv pip install --extra-index-url https://{os.environ.get('GITHUB_REPOSITORY_OWNER', 'your-github-username')}.github.io/{os.environ.get('GITHUB_REPOSITORY_NAME', 'pypi')}/ SomePackage</pre>
    <p><strong>Note:</strong> This index provides wheels originally built for <code>linux_aarch64</code>, relabeled and served as <code>android_24_aarch64</code> for compatibility with tools like <code>uv</code> in Termux. Compatibility is not guaranteed for all packages.</p>
    <h2>Packages</h2>
""")
      # Sort packages alphabetically for consistent ordering
      for package_name in sorted(packages):
          normalized_package_name = package_name.lower().replace("_", "-")
          # Link to the directory, trailing slash is important for simple index
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
  generate_packages_index(packages_dict) # This now handles downloads/renaming
  generate_main_pages(packages_dict.keys())
  print("PyPI index generation complete.")
  print(f"Make sure to commit and push the entire '{DOCS_DIR}' directory (including downloaded wheels) to your GitHub Pages branch.")

if __name__ == "__main__":
  main()
