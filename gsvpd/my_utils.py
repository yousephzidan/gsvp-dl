import numpy as np
import time
import json
from rich import print
import argparse
import os
from PIL import Image

class timer:
    """
    Context manager to measure and print elapsed execution time.

    Usage:
        with timer():
            # your code here
    -----
    >>> with timer() as t:
    ...     # some code to measure
    ...     time.sleep(2)
    >>> print(t.time_elapsed)
    '0h 0m 2.00s'
    """

    def __enter__(self):
        self.start = time.time()
        self.time_elapsed = None
        return self


    def __exit__(self, *args):
        self.end = time.time()
        self.interval = self.end - self.start
        hrs, rem = divmod(self.interval, 3600)
        mins, secs = divmod(rem, 60)
        self.time_elapsed = f"{int(hrs)}h {int(mins)}m {secs:.2f}s"
        return False 

def has_black_bottom(tile, black_threshold: int = 10, check_rows: int = 5) -> bool:
    """
    Check if the bottom rows of a tile image are completely black.

    Args:
        tile (PIL.Image.Image): The image tile to check.
        black_threshold (int, optional): Max RGB value considered 'black'. Defaults to 10.
        check_rows (int, optional): Number of bottom rows to inspect. Defaults to 5.

    Returns:
        bool: True if all bottom rows are black, False otherwise.
    """
    arr = np.array(tile)
    bottom = arr[-check_rows:]
    return np.all(bottom <= black_threshold)


def black_percentage(tile, threshold: int = 10) -> float:
    """
    Calculate the percentage of black pixels in a tile.

    Args:
        tile (PIL.Image.Image): Tile image to analyze.
        threshold (int, optional): Max RGB value to consider a pixel 'black'. Defaults to 10.

    Returns:
        float: Percentage of black pixels (0–100).
    """
    img_np = np.array(tile)

    # Pixel is black if all channels <= threshold
    black_pixels = np.all(img_np <= threshold, axis=2)

    # Compute percentage
    percent_black = np.sum(black_pixels) / black_pixels.size * 100
    return percent_black


def open_dataset(dataset_location: str) -> list[str]:
    """
    Load dataset JSON file.

    Args:
        dataset_location (str): Path to dataset JSON file.

    Returns:
        list[str]: Parsed JSON data.
    """
    with open(dataset_location) as dataset:
        return json.load(dataset)


def limit_dataset(dataset: list[dict], limit_count: int) -> list[dict]:
    """
    Limit dataset size for testing or sampling.

    Args:
        dataset (list[dict]): Full dataset loaded from JSON.
        limit_count (int): Maximum number of items to return.

    Returns:
        list[dict]: Subset of the dataset up to `limit_count` entries.
    """
    return dataset[:limit_count]


def parse_args():
    """
    Parse command-line arguments for the panorama downloader.

    Arguments:
        --zoom (int, required): Zoom level (0–5).
        --dataset (str, optional): Path to dataset JSON file. Default: ./dataset.json
        --max-pano (int, optional): Max concurrent pano downloads. Default: 50
        --max-tile (int, optional): Max concurrent tile downloads per pano. Default: 50
        --workers (int, optional): Max process pool workers. Default: 20
        --limit (int, optional): Limit panoids for testing. Default: None

    Returns:
        argparse.Namespace: Parsed arguments object.
    """
    parser = argparse.ArgumentParser(
        description="Google Street View Panorama Downloader"
    )

    parser.add_argument("--zoom", type=int, required=True, help="Zoom level (0-5)")
    parser.add_argument("--dataset", type=str, default="./dataset.json", help="Path to dataset.json")
    parser.add_argument("--max-pano", type=int, default=50, help="Max concurrent pano downloads")
    parser.add_argument("--max-tile", type=int, default=50, help="Max concurrent tile downloads per pano")
    parser.add_argument("--workers", type=int, default=20, help="Max process pool workers")
    parser.add_argument("--limit", type=int, default=None, help="Limit panoids")
    parser.add_argument("--output", type=str, default=os.getcwd(), help="Output directory (default: current working directory)")
    parser.add_argument("--conn-limit", type=int, default=20, help="Maximum total TCP connections (default: 20)")
    parser.add_argument("--conn-limit-perh", type=int, default=20, help="Maximum TCP connections per host (default: 20)")

    return parser.parse_args()



def format_size(num_bytes: int) -> str:
    """
    Convert a file size in bytes into a human-readable string.

    Args:
        num_bytes (int): File size in bytes.

    Returns:
        str: Formatted size (e.g., '512.00 KB', '384.00 MB').
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} PB"

def save_img(full_img: Image, output_dir: str, panoid: str, zoom_level: int) -> str:
    """
    Save a PIL image to disk in a structured directory layout and return its file size.

    The function creates a subdirectory based on the zoom level (e.g., "panos_z1"),
    saves the given image as a JPEG file named with the provided panorama ID, and
    calculates the saved file's size in a human-readable format.

    Args:
        full_img (Image): A PIL Image object to be saved.
        output_dir (str): Base directory where the image should be stored.
        panoid (str): Unique panorama identifier used as the output filename.
        zoom_level (int): Zoom level used to organize the output directory.

    Returns:
        str: File size of the saved image in a human-readable format 
             (e.g., "512.00 KB", "1.23 MB").
    """
    zoom_output_folder = os.path.join(output_dir, f"panos_z{zoom_level}")
    os.makedirs(zoom_output_folder, exist_ok=True) 
    out_path = os.path.join(zoom_output_folder, f"{panoid}.jpg")

    full_img.save(out_path)
    file_size_bytes = os.path.getsize(out_path)
    file_size_fmt = format_size(file_size_bytes)

    return file_size_fmt
