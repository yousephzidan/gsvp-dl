# year > 2016 
ZOOM_SIZES = {
    0: (512, 256),
    1: (1024, 512), 
    2: (2048, 1024), 
   
}

# year <= 2016 
OLD_ZOOM_SIZES = {
    0: (416, 208), 
    1: (832, 416), 
    2: (1664, 832), 
}

# Always use the post-2016 tile count for the chosen zoom level.
# For older panoramas, this means we’ll fetch a few extra black tiles.
# We can remove those extra black tiles later.
TILES_AXIS_COUNT = {
    0: (0, 0), 
    1: (1, 0), 
    2: (3, 1), 
    3: (7, 3), 
    4: (15, 7), 
    5: (31, 15)
}


# Mapping of (x_tiles, y_tiles) to (width_px, height_px).
# Based on the number of tiles fetched, we can calculate the final panorama size.
# Note:
# - "new" values = post-2016 panoramas
# - "old" values = pre-2016 panoramas (slightly fewer tiles → smaller size)
TILE_COUNT_TO_SIZE = {
    (8, 4):  (4096, 2048),   # z3 new
    (7, 4):  (3328, 1664),   # z3 old

    (16, 8): (8192, 4096),   # z4 new
    (13, 7): (6656, 3328),   # z4 old

    (32, 16): (16384, 8192), # z5 new
    (26, 13): (13312, 6656)  # z5 old
}

TILE_SIZE = 512