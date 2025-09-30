"""
Core module for downloading, processing, and stitching Google Street View panoramas.

This module provides asynchronous functions to:

- Fetch individual panorama tiles from Google Street View with retry logic (`fetch_tile`).
- Determine panorama dimensions based on zoom level and tile content (`determine_dimensions`).
- Stitch multiple tiles into a single panorama image (`stitch_tiles`).
- Process a single panorama by fetching tiles, determining dimensions, stitching, and saving (`process_panoid`).
- Download and process multiple panoramas concurrently (`fetch_panos`).

The module supports different zoom levels (0–5) and handles old (pre-2016) and new panorama formats.
It uses asyncio for concurrent network requests and a process pool executor for CPU-bound tasks like image analysis.

Dependencies:
- aiohttp for asynchronous HTTP requests
- PIL/Pillow for image processing
- rich for colored logging
"""
import asyncio
from concurrent.futures import ProcessPoolExecutor

import aiohttp
from aiohttp import ClientTimeout

from PIL import Image
from io import BytesIO

from rich import print
from typing import Tuple, Union
import os

from .constants import (
    ZOOM_SIZES, 
    OLD_ZOOM_SIZES, 
    TILE_COUNT_TO_SIZE,
    TILES_AXIS_COUNT,
    TILE_SIZE
)
from .my_utils import (
    has_black_bottom,
    black_percentage,
    save_img
)


async def fetch_tile(
    session: aiohttp.ClientSession, 
    panoid: str,
    x: int, 
    y: int, 
    zoom_level: int, 
    retries: int = 3, 
    backoff: float = 0.2
) -> Union[None, Tuple]:
    """
    Fetch a single panorama tile from Google Street View with retry support.

    Args:
        session (aiohttp.ClientSession): The active HTTP session.
        panoid (str): The panorama ID to fetch tiles from.
        x (int): Tile X index.
        y (int): Tile Y index.
        zoom_level (int): Zoom level (0–5).
        retries (int): Number of retry attempts on failure (default: 3).
        backoff (float): Initial backoff delay in seconds between retries (default: 1.0).

    Returns:
        tuple[int, int, PIL.Image.Image] | None: 
            A tuple containing (x, y, tile image) if successful, otherwise None.
    """
    url = f"https://cbk0.google.com/cbk?output=tile&panoid={panoid}&zoom={zoom_level}&x={x}&y={y}"

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, timeout=ClientTimeout(30)) as response:

                if response.status != 200:
                    return None

                BLACK_TILE_BYTE_SIZE = 1184
                BLACK_TILE_SIZE = int(response.headers.get("Content-Length", 0))

                if BLACK_TILE_SIZE == BLACK_TILE_BYTE_SIZE:  # black tile
                    return None

                data = await response.read()
                tile = Image.open(BytesIO(data))
                return (x, y, tile)

        except Exception as error:
            if attempt < retries:
                wait_time = backoff * (2 ** (attempt - 1))  # exponential backoff
                print(f"[yellow][Retry] {attempt}/{retries} for tile ({x},{y}) pano `{panoid}` in {wait_time:.1f}s: {error}[/]")
                await asyncio.sleep(wait_time)
            else:
                print(f"[red][TILE ERROR] Failed after {retries} retries for tile {x},{y} pano `{panoid}`: {error}[/]")

    return None

async def determine_dimensions(
    executor,
    tiles: list, 
    zoom_level: int, 
    x_tiles_count: int, 
    y_tiles_count: int
) -> Tuple[int, int]:
    """
    Determine the width and height of a panorama image based on zoom level 
    and tile analysis.

    For zoom level 0:
        - Uses `black_percentage` to check if it's an old panorama.
    For zoom levels 1–2:
        - Uses `has_black_bottom` to detect old panorama bottom margin.
    For zoom levels 3+:
        - Uses `TILE_COUNT_TO_SIZE` lookup.

    Args:
        executor (ProcessPoolExecutor | None): Executor for CPU-bound tasks.
        tiles (list): List of tiles in the format [(x, y, Image), ...].
        zoom_level (int): Zoom level (0–5).
        x_tiles_count (int): Number of horizontal tiles fetched.
        y_tiles_count (int): Number of vertical tiles fetched.

    Returns:
        Tuple[int, int]: Width and height of the panorama in pixels.
    """
    if zoom_level == 0:
        black_perc = await asyncio.get_running_loop().run_in_executor(
            executor, black_percentage, tiles[0][2]
        )
        return OLD_ZOOM_SIZES[zoom_level] if black_perc > 55 else ZOOM_SIZES[zoom_level]

    elif 0 < zoom_level <= 2:
        black = await asyncio.get_running_loop().run_in_executor(
            executor, has_black_bottom, tiles[1][2]
        )
        return OLD_ZOOM_SIZES[zoom_level] if black else ZOOM_SIZES[zoom_level]

    return TILE_COUNT_TO_SIZE.get((x_tiles_count, y_tiles_count))


def stitch_tiles(tiles: list, width: int, height: int) -> Image.Image:
    """
    Combine individual panorama tiles into a single stitched image.

    Args:
        tiles (list): List of tiles as tuples (x, y, Image).
        width (int): Total width of the stitched image.
        height (int): Total height of the stitched image.

    Returns:
        PIL.Image.Image: The final stitched panorama image.
    """
    full_img = Image.new("RGB", (width, height))
    for x, y, tile in tiles:
        full_img.paste(tile, (x * TILE_SIZE, y * TILE_SIZE))
        tile.close()
    return full_img


async def process_panoid(
    session: aiohttp.ClientSession, 
    panoid: str, 
    sem_pano: asyncio.Semaphore, 
    executor: ProcessPoolExecutor, 
    zoom_level: int, 
    output_dir: str
) -> Union[dict, None]:
    """
    Download, reconstruct, and save a single panorama.

    Steps:
        1. Fetch all tiles for the given panoid and zoom level.
        2. Filter out black or missing tiles.
        3. Determine panorama dimensions using zoom level and tile content.
        4. Stitch tiles into a single panorama image.
        5. Save the resulting image to disk.
        6. Return metadata about the panorama.

    Args:
        session (aiohttp.ClientSession): Active HTTP session.
        panoid (str): Panorama ID to fetch.
        sem_pano (asyncio.Semaphore): Semaphore to limit concurrent panorama downloads.
        executor (ProcessPoolExecutor): Executor for CPU-bound tasks.
        zoom_level (int): Zoom level (0–5).
        output_dir (str): Directory to save the panorama image.

    Returns:
        dict | None: Metadata dictionary containing:
            - "panoid" (str): Panorama ID.
            - "zoom" (int): Zoom level used.
            - "size" (tuple[int, int]): Image width and height in pixels.
            - "tiles" (tuple[int, int]): Count of tiles (x_tiles, y_tiles).
            - "file_size" (int): Size of saved image in bytes.
        Returns None if the panorama could not be fetched or processed.
     """
    try:
        async with sem_pano:
            # Number of tiles along the X (horizontal) and Y (vertical) axes
            # This defines how many tile requests are needed for this zoom level
            tiles_x, tiles_y = TILES_AXIS_COUNT[zoom_level]

            # fetch tiles
            tasks = [
                fetch_tile(session, panoid, x, y, zoom_level)
                for x in range(tiles_x + 1)
                for y in range(tiles_y + 1)
            ]
            tiles = [tile for tile in await asyncio.gather(*tasks) if tile is not None]

            if not tiles:
                print(f"[yellow][FAIL] Panoid `{panoid}` | No tiles fetched (may be expired, removed, or invalid)[/]")
                return None

            # count tiles
            x_values = {x for x, _, _ in tiles}
            y_values = {y for _, y, _ in tiles}
            x_tiles_count, y_tiles_count = len(x_values), len(y_values)

            # determine panorama dimensions
            w, h = await determine_dimensions(executor, tiles, zoom_level, x_tiles_count, y_tiles_count)

            # stitch & save
            full_img = stitch_tiles(tiles, w, h)
            img_file_size = save_img(full_img, output_dir, panoid, zoom_level)
            img_size = full_img.size
            full_img.close()

            print(
                f"[green][OK] Panoid `{panoid}` | zoom {zoom_level} "
                f"| w*h {img_size[0]}x{img_size[1]} "
                f"| tiles: {x_tiles_count}x{y_tiles_count} "
                f"| size {img_file_size}[/]"
            )
            return {
                "panoid": panoid,
                "zoom": zoom_level,
                "size": img_size,
                "tiles": (x_tiles_count, y_tiles_count),
                "file_size": img_file_size,
            }

    except Exception as error:
        print(f"[red][PROCESSING ERROR] Panoid `{panoid}`: {error}[/]")
        return None

async def fetch_panos(
    sem_pano: asyncio.Semaphore, 
    connector: aiohttp.TCPConnector, 
    max_workers: int, 
    zoom_level: int, 
    panoids: list[str], 
    output_dir: Union[str, None] =  None
) -> tuple[int, int, str]:
   """
    Download and process multiple panoramas concurrently.

    Args:
        sem_pano (asyncio.Semaphore): Semaphore to control concurrent pano downloads.
        connector (aiohttp.TCPConnector): Connector with concurrency limits for aiohttp.
        max_workers (int): Max number of workers for the process pool (used for image checks).
        zoom_level (int): Zoom level (0–5).
        panoids (list[str]): List of panorama IDs to fetch.

    Workflow:
        - Creates an aiohttp session.
        - Uses a process pool executor for CPU-bound tasks.
        - Runs `process_panoid()` for each panoid concurrently.

    Returns:
        tuple[int, int, str]: A tuple containing:
            - total_panos (int): Number of panorama IDs processed.
            - successful_panos (int): Number of panoramas successfully downloaded.
            - output_dir (str): Output directory where the panoramas are saved.
   """
   print("[green]| Running Scraper..[/]\n")

   if output_dir is None: output_dir = os.getcwd()

   async with aiohttp.ClientSession(connector=connector) as session:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            tasks = [process_panoid(session, panoid, sem_pano, executor, zoom_level, output_dir) for panoid in panoids]
            tasks_res = await asyncio.gather(*tasks)

        success_panos = tuple(filter(lambda pano: pano is not None, tasks_res)) 

        return len(tasks) ,len(success_panos), output_dir

