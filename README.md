# ✨ ISO List ✨

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Add your LICENSE file -->
[![GitHub last commit](https://img.shields.io/github/last-commit/mikl0s/iso-list)](https://github.com/mikl0s/iso-list/commits/main) <!-- Adjust branch if needed -->
[![GitHub repo size](https://img.shields.io/github/repo-size/mikl0s/iso-list)](https://github.com/mikl0s/iso-list)
[![GitHub issues](https://img.shields.io/github/issues/mikl0s/iso-list)](https://github.com/mikl0s/iso-list/issues)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/mikl0s/iso-list/pulls)
<!-- Optional: Add GitHub Actions status badge if you set it up
[![Update Status](https://github.com/mikl0s/iso-list/actions/workflows/update-links.yml/badge.svg)](https://github.com/mikl0s/iso-list/actions/workflows/update-links.yml)
-->

**Automatically Updated Links to the Latest Linux and Windows ISO Downloads**

Tired of manually searching mirror sites for the *absolute latest* stable ISO file for your favorite Linux distributions? Need the latest Windows ESD link? This project automates that process!

`iso-list` reads a simple configuration file (`distros.yaml`), scrapes the official download pages or mirror directories, identifies the latest stable ISO/ESD based on defined patterns, and saves the direct download links (along with hashes, if found) to a clean `links.json` file.

---

## 🚀 Features

*   **Automated Updates:** Finds the latest ISO/ESD links programmatically.
*   **Configurable:** Easily add or modify distributions via the `distros.yaml` file.
*   **Smart Scraping:** Can navigate into version subdirectories (e.g., `/stable/22.1/`) to find the correct files.
*   **Flexible Matching:** Supports wildcard patterns (`*.iso`, `*netinst.iso`, etc.) for different ISO types.
*   **Windows Support:** Can now also fetch links for Windows ISOs (ESD files) using various methods.
*   **Hash Retrieval:** Attempts to find and include file hashes (SHA1, SHA256, SHA512) from download pages or accompanying files.
*   **Simple Output:** Generates a clean `links.json` file, perfect for scripting or automation.

## 🤔 How It Works

1.  Reads the `iso-list.conf` to find the source of the distribution list (`distros.yaml`, either local or remote URL).
2.  Fetches and parses the `distros.yaml` file.
3.  For each distribution entry:
    *   Visits the specified `URL` or uses a specific handler (like for Windows).
    *   Parses the HTML page looking for `<a>` links or uses API/scripting methods.
    *   Filters links matching the `Extension` pattern or specific criteria.
    *   If no direct match, it looks for version directories (e.g., `22.04/`, `12.1/`).
    *   Sorts directories/files to find the latest version.
    *   If necessary, navigates into the latest version directory and repeats the search.
    *   Constructs the full, absolute download URL for the latest matching ISO/ESD.
    *   Attempts to find associated hash files (e.g., `SHA256SUMS`, `SHA512SUMS`) and extracts the hash for the specific file.
4.  Writes all found links and hashes (or `null` if not found) into the `links.json` file.

## ✨ Output (`links.json`)

The script generates a `links.json` file in the root directory containing a mapping of the distribution `Name` from the YAML file to an object containing its latest found ISO/ESD URL and hash information.

**Example `links.json`:**

```json
{
    "Windows 11 Pro + Workstation (en-US, x64)": {
        "url": "http://dl.delivery.mp.microsoft.com/filestreamingservice/files/2a163cd8-b8bb-4e9f-a8b6-ed492b9316be/26100.2033.241004-2336.ge_release_svc_refresh_CLIENTCONSUMER_RET_x64FRE_en-us.esd",
        "hash_type": "SHA1",
        "hash_value": "92858d17328b07f5d0a42b235aaaa082dff0a12b",
        "source": "WindowsMode_AWK",
        "version": "26100.2033",
        "size": 4161510161
    },
    "Debian 12 Netinst (Latest)": {
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.10.0-amd64-netinst.iso",
        "hash_type": "SHA512",
        "hash_value": "cb089def0684fd93c9c2fbe45fd16ecc809c949a6fd0c91ee199faefe7d4b82b64658a264a13109d59f1a40ac3080be2f7bd3d8bf3e9cdf509add6d72576a79b",
        "version": "12.10",
        "size": 663748608
    },
    "Ubuntu Server 24.04 LTS": {
        "url": "https://releases.ubuntu.com/24.04.2/ubuntu-24.04.2-live-server-amd64.iso",
        "hash_type": "SHA256",
        "hash_value": "d6dab0c3a657988501b4bd76f1297c053df710e06e0c3aece60dead24f270b4d",
        "version": "24.04",
        "size": 3213064192
    },
    "Linux Mint Cinnamon (Latest)": {
        "url": "https://mirrors.edge.kernel.org/linuxmint/stable/22.1/linuxmint-22.1-cinnamon-64bit.iso",
        "hash_type": "SHA256",
        "hash_value": "ccf482436df954c0ad6d41123a49fde79352ca71f7a684a97d5e0a0c39d7f39f",
        "version": "22.1",
        "size": 2980511744
    },
    "FreeBSD latest release": {
        "url": "https://download.freebsd.org/releases/amd64/amd64/ISO-IMAGES/14.2/FreeBSD-14.2-RELEASE-amd64-bootonly.iso",
        "hash_type": "SHA512",
        "hash_value": "35a76364e2ea5437ce004c4f49619723a77ce0eb5dec84336b2b062f7697005cd33608b8bce67e96f91a4095ebb9584c665af1d609f79e70fbae298a26747473",
        "version": "14.2",
        "size": 459491328
    },
    "Fedora Workstation (Latest)": {
        "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/41/Workstation/x86_64/iso/Fedora-Workstation-Live-x86_64-41-1.4.iso",
        "hash_type": "SHA256",
        "hash_value": "a2dd3caf3224b8f3a640d9e31b1016d2a4e98a6d7cb435a1e2030235976d6da2",
        "version": "1.4",
        "size": 2458187776
    },
    "CentOS 10 Stream (Latest)": {
        "url": "https://mirror.netsite.dk/centos-stream/10-stream/BaseOS/x86_64/iso/CentOS-Stream-10-latest-x86_64-dvd1.iso",
        "hash_type": null,
        "hash_value": null,
        "version": "Unknown (est)",
        "size": 7602765824
    },
    "Arch Linux (Latest)": {
        "url": "https://geo.mirror.pkgbuild.com/iso/latest/archlinux-x86_64.iso",
        "hash_type": "SHA256",
        "hash_value": "1155af9c142387c45eb6fbdbf32f5652fb514ce15a4d17a83e6056a996895026",
        "version": "Unknown (est)",
        "size": 1236303872
    },
    "Pop!_OS 22.04 LTS with NVIDIA": {
        "url": "https://iso.pop-os.org/22.04/amd64/nvidia/51/pop-os_22.04_amd64_nvidia_51.iso",
        "hash_type": "SHA256",
        "hash_value": "808a3df159b57ec69fe8dae47c69d4b07a834ddeff0bd73fc7d4ada485b61725",
        "version": "Unknown",
        "size": 3064233984
    },
    "Kali Linux (Latest)": {
        "url": "https://cdimage.kali.org/kali-2025.1a/kali-linux-2025.1a-installer-netinst-amd64.iso",
        "hash_type": "SHA256",
        "hash_value": "32c3cf9eeba5f49ace1bcc8b16293495a151c0c175bf80f8601031cb973425f5",
        "version": "2025.1",
        "size": 636485632
    },
    "Solus Budgie (Latest)": {
        "url": "https://downloads.getsol.us/isos/2025-01-26/Solus-Budgie-Release-2025-01-26.iso",
        "hash_type": "SHA256",
        "hash_value": "4e2d664b6821b8d358c67967be1bfd71b222bf0e748f224c794f3f2a7b96c266",
        "version": "Unknown (est)",
        "size": 3204448256
    },
    "Zorin 17.3 Core": {
        "url": "https://mirrors.edge.kernel.org/zorinos-isos/17/Zorin-OS-17.3-Core-64-bit.iso",
        "hash_type": "SHA256",
        "hash_value": "58cc54a7d0974367bf9b5563c828a39a3d19a25b188c9ce211a6c9467794e762",
        "version": "17.3",
        "size": 3657433088
    },
    "Proxmox VE latest release": {
        "url": "https://enterprise.proxmox.com/iso/proxmox-ve_8.4-1.iso",
        "hash_type": "SHA256",
        "hash_value": "d237d70ca48a9f6eb47f95fd4fd337722c3f69f8106393844d027d28c26523d8",
        "version": "8.4",
        "size": 1571895296
    }
}
```
