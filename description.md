# Project Description: ISO/ESD Link Fetcher

## Purpose

This project automatically fetches the latest download links and checksums for various operating system distributions (like Debian, Ubuntu, Linux Mint, FreeBSD, and Windows).

-   It reads the list of distributions and their specific requirements from `distros.yaml`.
-   The core logic resides in `iso-list.py`, which performs web scraping for standard ISOs and utilizes the `download-windows-esd` script (and its cached `products.xml`) to get Windows ESD download details.
-   The final output, containing the distribution names, download URLs, hash types, hash values, and extracted version numbers, is stored in `links.json`.

## How to Make Changes

1.  **Adding/Modifying Distributions:**
    *   Edit the `distros.yaml` file. Add new entries or modify existing ones, specifying the Name, URL, Extension pattern, VersionMatch criteria, HashMatch pattern, and any Windows-specific details (WindowsMode, Edition, Language, Architecture) as needed.

2.  **Modifying Fetching/Parsing Logic:**
    *   Edit the `iso-list.py` script. This is where you would change:
        *   How websites are scraped (`find_iso_web` function).
        *   How Windows ESD details are extracted (`get_windows_esd_details_from_xml` function).
        *   How version numbers are parsed.
        *   How hash files are found and parsed.

3.  **Updating Windows Metadata Source:**
    *   The `download-windows-esd` shell script handles downloading and caching the `products.xml` file from Microsoft, which contains Windows ESD metadata. Modifications to this process would happen in this script.

4.  **Configuration:**
    *   The `iso-list.conf` file can specify the location of the `distros.yaml` source (local file or URL).

5.  **Applying Changes:**
    *   After modifying `distros.yaml` or `iso-list.py`, run the script to regenerate the output file:
        ```bash
        python3 iso-list.py
        ```
    *   This will update `links.json` with the latest fetched data based on your changes.
