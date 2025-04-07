# ✨ ISO List ✨

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Add your LICENSE file -->
[![GitHub last commit](https://img.shields.io/github/last-commit/mikl0s/iso-list)](https://github.com/mikl0s/iso-list/commits/main) <!-- Adjust branch if needed -->
[![GitHub repo size](https://img.shields.io/github/repo-size/mikl0s/iso-list)](https://github.com/mikl0s/iso-list)
[![GitHub issues](https://img.shields.io/github/issues/mikl0s/iso-list)](https://github.com/mikl0s/iso-list/issues)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/mikl0s/iso-list/pulls)
<!-- Optional: Add GitHub Actions status badge if you set it up
[![Update Status](https://github.com/mikl0s/iso-list/actions/workflows/update-links.yml/badge.svg)](https://github.com/mikl0s/iso-list/actions/workflows/update-links.yml)
-->

**Automatically Updated Links to the Latest Linux ISO Downloads**

Tired of manually searching mirror sites for the *absolute latest* stable ISO file for your favorite Linux distributions? This project automates that process!

`iso-list` reads a simple configuration file (`distros.yaml`), scrapes the official download pages or mirror directories, identifies the latest stable ISO based on defined patterns, and saves the direct download links to a clean `links.json` file.

---

## 🚀 Features

*   **Automated Updates:** Finds the latest ISO links programmatically.
*   **Configurable:** Easily add or modify distributions via the `distros.yaml` file.
*   **Smart Scraping:** Can navigate into version subdirectories (e.g., `/stable/22.1/`) to find the correct files.
*   **Flexible Matching:** Supports wildcard patterns (`*.iso`, `*netinst.iso`, etc.) for different ISO types.
*   **Simple Output:** Generates a clean `links.json` file, perfect for scripting or automation.

## 🤔 How It Works

1.  Reads the `iso-manager.conf` to find the source of the distribution list (`distros.yaml`, either local or remote URL).
2.  Fetches and parses the `distros.yaml` file.
3.  For each distribution entry:
    *   Visits the specified `URL`.
    *   Parses the HTML page looking for `<a>` links.
    *   Filters links matching the `Extension` pattern.
    *   If no direct match, it looks for version directories (e.g., `22.04/`, `12.1/`).
    *   Sorts directories/files to find the latest version.
    *   If necessary, navigates into the latest version directory and repeats the search.
    *   Constructs the full, absolute download URL for the latest matching ISO.
4.  Writes all found links (or `null` if not found) into the `links.json` file.

## ✨ Output (`links.json`)

The script generates a `links.json` file in the root directory containing a mapping of the distribution `Name` from the YAML file to its latest found ISO URL.

**Example `links.json`:**

```json
{
    "Debian 12": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.5.0-amd64-netinst.iso",
    "Ubuntu Server LTS": "https://releases.ubuntu.com/noble/ubuntu-24.04-server-amd64.iso",
    "Linux Mint Cinnamon": "https://mirrors.edge.kernel.org/linuxmint/stable/22.1/linuxmint-22.1-cinnamon-64bit.iso",
    "Distro Not Found Example": null
}
