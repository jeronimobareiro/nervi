# Download and install

Nervi is free for Windows and Linux.

## Installers

The installers for **Windows** (`.exe`) and **Linux** (AppImage) are published on the GitHub releases page, together with the first preliminary version.

[See published releases](https://github.com/jeronimobareiro/nervi/releases){ .md-button .md-button--primary }

If no release appears yet, the first one is being prepared. Meanwhile you can install it from the source code, as explained below.

!!! note "Windows warning during installation"
    The installers are not digitally signed yet, so Windows may show the "Windows protected your PC" warning. If you downloaded the file from the official releases page, choose **More info → Run anyway**.

On Linux, after downloading the AppImage, make it executable (right click → Properties → Permissions, or `chmod +x Nervi-*.AppImage`) and open it with a double click.

## From the source code

For those who want the latest development version or to use Nervi from Python. You need [Rust](https://www.rust-lang.org/tools/install) and [Python](https://www.python.org/downloads/) 3.10 or later.

```bash
git clone https://github.com/jeronimobareiro/nervi.git
cd nervi
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install maturin PySide6-Essentials
maturin develop --release
python -m nervi.gui                # opens the interface
```

If you will only use Nervi from Python, you do not need to install `PySide6-Essentials`.

## Requirements

- Windows 10 or 11, or a recent 64-bit Linux distribution.
- No internet connection is needed: all the calculation runs on your computer and your models never leave it.
