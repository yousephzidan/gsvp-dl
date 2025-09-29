import pytest
import asyncio
from PIL import Image
from io import BytesIO
from unittest.mock import AsyncMock, patch 
from ..core import TILE_COUNT_TO_SIZE
from .. import core


def dummy_image_bytes(size=(256, 256), color=(255, 0, 0)):
    """Generate dummy image bytes for testing purposes."""
    buf = BytesIO()
    Image.new('RGB', size, color).save(buf, format='JPEG')
    buf.seek(0)
    return buf.read()


def dummy_image(size=(256, 256), color=(255, 0, 0)):
    """Return a PIL Image object."""
    return Image.new('RGB', size, color)


@pytest.mark.asyncio
async def test_fetch_tile_success_mocked(monkeypatch):
    sem = asyncio.Semaphore(1)

    class MockResponse:
        status = 200
        headers = {"Content-Length": "1024"}

        async def read(self):
            return dummy_image_bytes()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_get(*args, **kwargs):
        return MockResponse()

    async with core.aiohttp.ClientSession() as session:
        monkeypatch.setattr(session, "get", mock_get)
        result = await core.fetch_tile(session, "fake_panoid", 0, 0, sem, 3)
        assert result is not None
        x, y, img = result
        assert x == 0 and y == 0
        assert isinstance(img, Image.Image)


@pytest.mark.asyncio
async def test_fetch_tile_black_tile_mocked(monkeypatch):
    sem = asyncio.Semaphore(1)

    class MockResponse:
        status = 200
        headers = {"Content-Length": "1184"}

        async def read(self):
            return b""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_get(*args, **kwargs):
        return MockResponse()

    async with core.aiohttp.ClientSession() as session:
        monkeypatch.setattr(session, "get", mock_get)
        result = await core.fetch_tile(session, "fake_panoid", 0, 0, sem, 3)
        assert result is None


@pytest.mark.asyncio
async def test_fetch_tile_failure():
    session = AsyncMock()
    mock_response = AsyncMock()
    mock_response.__aenter__.side_effect = Exception("Network error")
    session.get.return_value = mock_response

    sem = asyncio.Semaphore(1)
    result = await core.fetch_tile(session, "fake_panoid", 0, 0, sem, 3, retries=2, backoff=0)
    assert result is None


@pytest.mark.asyncio
async def test_process_panoid_success(monkeypatch, tmp_path):
    async def fake_fetch_tile(session, panoid, x, y, sem_tile, zoom_level, **kwargs):
        return x, y, dummy_image((512, 512), (255, 0, 0))

    monkeypatch.setattr(core, "fetch_tile", fake_fetch_tile)

    sem_pano = asyncio.Semaphore(1)
    sem_tile = asyncio.Semaphore(2)
    session = None
    executor = None
    zoom_level = 3
    panoid = "fake_panoid"

    result = await core.process_panoid(session, panoid, sem_pano, sem_tile, executor, zoom_level, tmp_path)
    assert result is not None
    assert result["panoid"] == panoid
    assert result["zoom"] == zoom_level
    assert result["tiles"][0] > 0 and result["tiles"][1] > 0

    expected_file = tmp_path / f"panos_z{zoom_level}" / f"{panoid}.jpg"
    assert expected_file.exists()


@pytest.mark.parametrize("zoom_level", [0, 1, 2, 3, 4, 5])
@pytest.mark.asyncio
async def test_different_zoom_levels(zoom_level, tmp_path):
    async def fake_fetch_tile(session, panoid, x, y, sem_tile, zl, **kwargs):
        return x, y, dummy_image((512, 512), (100 + x * 10, 100 + y * 10, 150))

    def sync_black_percentage(tile):
        return 50.0

    def sync_has_black_bottom(tile, **kwargs):
        return False

    sem_pano = asyncio.Semaphore(1)
    sem_tile = asyncio.Semaphore(10)
    session = None
    panoid = f"fake_panoid_z{zoom_level}"

    with patch.object(core, "fetch_tile", fake_fetch_tile), \
         patch("gsvpd.core.black_percentage", sync_black_percentage), \
         patch("gsvpd.core.has_black_bottom", sync_has_black_bottom):
        executor = None

        result = await core.process_panoid(session, panoid, sem_pano, sem_tile, executor, zoom_level, tmp_path)

    assert result is not None
    assert result["panoid"] == panoid
    assert result["zoom"] == zoom_level

    from ..constants import TILES_AXIS_COUNT
    nxt, nyt = TILES_AXIS_COUNT.get(zoom_level, (0, 0))
    expected_x_tiles = nxt + 1 if nxt else 1
    expected_y_tiles = nyt + 1 if nyt else 1
    assert result["tiles"][0] == expected_x_tiles
    assert result["tiles"][1] == expected_y_tiles

    expected_file = tmp_path / f"panos_z{zoom_level}" / f"{panoid}.jpg"
    assert expected_file.exists()


@pytest.mark.asyncio
async def test_process_panoid_no_tiles(monkeypatch, tmp_path):
    async def fake_fetch_tile(session, panoid, x, y, sem_tile, zoom_level, **kwargs):
        return None

    monkeypatch.setattr(core, "fetch_tile", fake_fetch_tile)

    sem_pano = asyncio.Semaphore(1)
    sem_tile = asyncio.Semaphore(2)
    session = None
    executor = None
    zoom_level = 3
    panoid = "expired_panoid"

    result = await core.process_panoid(session, panoid, sem_pano, sem_tile, executor, zoom_level, tmp_path)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_panos_with_failures(tmp_path, monkeypatch):
    async def fake_fetch_tile(session, panoid, x, y, sem_tile, zoom_level, **kwargs):
        if panoid == "panoid2":
            return None
        return x, y, dummy_image((512, 512))

    monkeypatch.setattr(core, "fetch_tile", fake_fetch_tile)
    panoids = ["panoid1", "panoid2", "panoid3"]

    sem_pano = asyncio.Semaphore(10)
    sem_tile = asyncio.Semaphore(20)
    connector = core.aiohttp.TCPConnector(limit=10, limit_per_host=10)

    total_panos, successful_panos, output_dir = await core.fetch_panos(
        sem_pano,
        sem_tile,
        connector,
        max_workers=2,
        zoom_level=3,
        panoids=panoids,
        output_dir=str(tmp_path)
    )

    assert total_panos == 3
    assert successful_panos == 2
    assert output_dir == str(tmp_path)

    assert (tmp_path / "panos_z3" / "panoid1.jpg").exists()
    assert (tmp_path / "panos_z3" / "panoid3.jpg").exists()
    assert not (tmp_path / "panos_z3" / "panoid2.jpg").exists()


@pytest.mark.asyncio
async def test_fetch_panos_empty_dataset(tmp_path):
    panoids = []

    sem_pano = asyncio.Semaphore(10)
    sem_tile = asyncio.Semaphore(20)
    connector = core.aiohttp.TCPConnector(limit=10, limit_per_host=10)

    total_panos, successful_panos, output_dir = await core.fetch_panos(
        sem_pano,
        sem_tile,
        connector,
        max_workers=2,
        zoom_level=3,
        panoids=panoids,
        output_dir=str(tmp_path)
    )

    assert total_panos == 0
    assert successful_panos == 0
    assert output_dir == str(tmp_path)


@pytest.mark.asyncio
async def test_fetch_panos_all_failures(tmp_path, monkeypatch):
    async def fake_fetch_tile(session, panoid, x, y, sem_tile, zoom_level, **kwargs):
        return None

    monkeypatch.setattr(core, "fetch_tile", fake_fetch_tile)
    panoids = ["fail1", "fail2", "fail3"]

    sem_pano = asyncio.Semaphore(10)
    sem_tile = asyncio.Semaphore(20)
    connector = core.aiohttp.TCPConnector(limit=10, limit_per_host=10)

    total_panos, successful_panos, output_dir = await core.fetch_panos(
        sem_pano,
        sem_tile,
        connector,
        max_workers=2,
        zoom_level=3,
        panoids=panoids,
        output_dir=str(tmp_path)
    )

    assert total_panos == 3
    assert successful_panos == 0
    assert output_dir == str(tmp_path)


@pytest.mark.asyncio
async def test_determine_dimensions_fallback():
    img = Image.open(BytesIO(dummy_image_bytes()))
    tiles = [(0, 0, img)]
    result = await core.determine_dimensions(None, tiles, 3, 2, 2)
    assert result == TILE_COUNT_TO_SIZE.get((2, 2))