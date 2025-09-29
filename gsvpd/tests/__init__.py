"""
Test suite for the `gsvpd` module.

This package contains unit and integration tests for `gsvpd` functionality, including:

- `core` module tests: fetching tiles, processing panoramas, handling errors, and stitching images.
- Utilities for generating dummy images and mocking async HTTP calls.
- Async tests using `pytest.mark.asyncio` and `unittest.mock` for patching.

Usage:

    # Run all tests in the package
    pytest gsvpd/tests

    # Run a specific test file
    pytest gsvpd/tests/test_core.py
"""