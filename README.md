<p align="center">
  <img src="src/assets/icons/nyini.png" alt="Nyini icon" width="128">
</p>

<h1 align="center">Nyini</h1>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-2ea44f" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  <img src="https://img.shields.io/badge/author-TheOnlyDuckxx-black" alt="Author">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/platform-Linux-FCC624?logo=linux&logoColor=black" alt="Platform">
</p>

Nyini is a desktop wallpaper manager for Linux. It is designed for local wallpaper libraries, with a native PySide6 interface, library indexing, metadata editing, filtering, video wallpaper support, and optional integrations such as Wallhaven and Gowall.

## Features

- Browse a local wallpaper library with grid and viewer modes.
- Index both image and video wallpapers.
- Filter by search, source, orientation, favorites, rating, and smart collections.
- Edit local metadata: tags, notes, favorite state, and rating.
- Review duplicate files with a dedicated duplicate review dialog.
- Import wallpapers from Wallhaven into the local Inbox.
- Preview and apply Gowall themes, then save generated results back to the library.
- Apply static wallpapers through Linux desktop backends with auto-detection.
- Apply video wallpapers through `mpvpaper` when supported.
- Switch the interface between English and French.
- Install the app into the Linux launcher with the provided desktop script.

## Installation

### Desktop install

```bash
./scripts/install_linux_desktop.sh
```

This installs Nyini in a user-local virtual environment, creates the `nyini` command, and adds the application to your launcher.

### Uninstall

```bash
./scripts/uninstall_linux_desktop.sh
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m src.main
```

## Optional tools

- `gowall` for theme generation and previews.
- `mpvpaper` and `mpv` for video wallpapers on compatible wlroots environments.
- A Wallhaven API key if you want fuller Wallhaven access.

## Validation

```bash
pytest -q
python -m build
```
