# Google Maps Street View Downloader

[![Python](https://img.shields.io/badge/python-3.9+-blue)](https://www.python.org/)

[Full API Documentation](https://yousephzidan.github.io/gsvp-dl/)


## Overview

This project provides a **Google Street View Panorama Downloader** as both an **API** and a **command-line tool**.
It is optimized to download **millions of panoramas asynchronously**. Using Python ``Aiohttp``, and ``Asyncio``. 

### Key Features

* Fully asynchronous panorama & tile downloading
* Detects black tiles and older panoramas with black margins
* Handles differences between pre-2016 and post-2016 images
* Configurable zoom levels and concurrency
* Scales to large datasets (millions of panoramas)

---

## Quick Start

Download panoramas from a dataset with a single command:

```bash
python run.py --zoom 2 --dataset ./dataset.json --limit 100 --max-tile 100 --conn-limit 100 --conn-limit-perh 100 --output ./downloads
```

Example dataset (`dataset.json`):

```json
[
  "-0cRHfYuByN1eUvfjcF-Xg",
  "zkBlgLSISS2RgEQE0OQ_kg",
  "TJAWObg1DzqkNWiGpEm8YQ",
  "1SnVdDntjJavWTlyoxQ5YQ"
]
```

This will download panoramas into:

```
downloads/
  ├── panos_z2/
  │   ├── -0cRHfYuByN1eUvfjcF-Xg.jpg
  │   ├── zkBlgLSISS2RgEQE0OQ_kg.jpg
  │   └── ...
```

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yousephzidan/gsvp-dl.git
cd gsvp-dl
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r req.txt
```

## Usage

### CLI (recommended)

The entry point is `run.py`. Available arguments:

```bash
python run.py --zoom 3 \
              --dataset ./dataset.json \
              --max-pano 100 \
              --workers 5 \
              --limit 500 \
              --conn-limit 100 \
              --conn-limit-perh 100 \
              --output ./downloads
```

**Arguments:**

* `--zoom (int, required)` – Zoom level (0–5)
* `--dataset (str)` – Path to dataset JSON file (default: `./dataset.json`)
* `--max-pano (int)` – Max concurrent pano downloads (default: 50)
* `--workers (int)` – Max process pool workers (default: 20)
* `--limit (int)` – Limit panoids for testing (default: None)
* `--output (str)` – Output directory (default: current working dir)
* `--conn-limit (int)` – Maximum total TCP connections for aiohttp (default: 20)
* `--conn-limit-perh (int)` – Maximum TCP connections per host (default: 20)

### As a Library

You can also import it:

```python
import asyncio
import aiohttp

from gsvpd import fetch_panos
from gsvpd import timer
from rich import print

async def main():
    dataset: list[str] = ["list of pano ids"]       

    sem_pano = asyncio.Semaphore(100)
    connector = aiohttp.TCPConnector(limit_per_host=100)

    zoom_level: int = 2 
    workers: int = 5

    return await fetch_panos(sem_pano, connector, workers, zoom_level, dataset)
    
if __name__ == "__main__":
    try:

        with timer() as t:
            total_panos, successful_panos, output_dir = asyncio.run(main())

        print(f"\n[gray]{'-' * 85}[/]")
        print(f"\n[orange1]| Processed [green]{successful_panos}/{total_panos}[/] panos in [green]{t.time_elapsed}[/][/]")
        print(f"[orange1]| Saved at [green]{output_dir}[/][/]\n")
    except Exception as error:
        print(f"[red][MAIN]Error: {error}[/]")
    except KeyboardInterrupt:
        print("[red]Keyboard Interrupted[/]")
```

## 📊 Technical Details

The downloader handles panoramas differently depending on zoom level, image age, and tile grid.

* **Old panoramas (≤2016):** lower resolution
* **New panoramas (>2016):** higher resolution

### Zoom Level Specs

**Old Panoramas Specs | 2016 and below**

| Zoom Level | Width | Height | X tiles | Y tiles | Notes                                                                    |
| ---------- | ----- | ------ | ------- | ------- | ------------------------------------------------------------------------ |
| 0          | 416   | 208    | 1       | 1       | Single tile, 55-59% black space at the bottom                            |
| 1          | 832   | 416    | 2       | 1       | X/Y tile grid same for old/new. Extra bottom black space (≤2016)   |
| 2          | 1664  | 832    | 4       | 2       | X/Y tile grid same for old/new. Extra bottom black space (≤2016)   |
| 3          | 3328  | 1664   | 7       | 4       | Older images (2016 or earlier); less resolution, fewer tiles on X-Y axis |
| 4          | 6656  | 3328   | 13      | 7       | Older images (2016 or earlier); less resolution, fewer tiles on X-Y axis |
| 5          | 13312 | 6656   | 26      | 13      | Older images (2016 or earlier); less resolution, fewer tiles on X-Y axis |

This is how we can tell old panoramas (≤2016) from new ones (>2016) at different zoom levels:

- Zoom 0: Both old and new panoramas have black space at the bottom.
    - Old panoramas: ~55–59% black space
    - New panoramas: ~40–55% black space

- Zoom 1 & 2:
    - Old panoramas (≤2016) have extra black space at the bottom tiles.
    - New panoramas (>2016) do not have this extra black space.

**New Panoramas Specs | After 2016**k

| Zoom Level | Width | Height | X tiles | Y tiles | Notes                                         |
| ---------- | ----- | ------ | ------- | ------- | --------------------------------------------- |
| 0          | 512   | 256    | 1       | 1       | Single tile, 40-55% black space at the bottom |
| 1          | 1024  | 512    | 2       | 1       | X/Y tile grid same for old/new panos. No extra bottom black space
| 2          | 2048  | 1024   | 4       | 2       | X/Y tile grid same for old/new panos. No extra bottom black space             |
| 3          | 4096  | 2048   | 8       | 4       | Modern images (>2016)                     |
| 4          | 8192  | 4096   | 16      | 8       | Modern images (>2016)                     |
| 5          | 16384 | 8192   | 32      | 16      | Modern images (>2016)                     |


For zoom levels 3, 4, and 5, the difference between old and new panoramas is captured using a dictionary that maps the number of X/Y tiles to the correct image width and height.


## Limitations
* API endpoints are not official and may change.
* Black tile detection is heuristic and may not be 100% accurate.
* Downloading millions of panoramas may hit Google rate limits. 


## Disclaimer

This project is intended for educational and research purposes only.

By using this project, you agree that:

- You are solely responsible for how you use it.
- The maintainers are not liable for any misuse, account bans, legal issues, or damages.

## Contributing

Contributions are welcome!

* Fork the repo and create a new branch
* Make your changes with clear commit messages
* Submit a pull request

For larger changes, please open an issue first to discuss.


## License

This project is licensed under the MIT License.



