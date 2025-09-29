"""
gsvpd - Google Street View Panorama Downloader

This module provides tools to download, process, and stitch Google Street View panoramas.

Key features:
- Concurrently fetch panorama tiles using asyncio + aiohttp.
- Detect and skip black or missing tiles.
- Stitch tiles into complete panorama images.
- Save images in structured directories with human-readable file sizes.
- Supports multiple zoom levels (0–5).

Example usage::

    import asyncio
    import aiohttp
    from gsvpd import fetch_panos
    from gsvpd import timer
    from rich import print

    async def main():
        dataset = ["list of pano ids"]
        sem_pano = asyncio.Semaphore(100)
        sem_tile = asyncio.Semaphore(100)
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=100)
        zoom_level = 2
        workers = 5
        return await fetch_panos(sem_pano, sem_tile, connector, workers, zoom_level, dataset)

    with timer() as t:
        total_panos, successful_panos, output_dir = asyncio.run(main())
        print(f"Processed {successful_panos}/{total_panos} panos in {t.time_elapsed}")
        print(f"Saved at {output_dir}")
"""
from .core import *
from .my_utils import *
from .constants import *
