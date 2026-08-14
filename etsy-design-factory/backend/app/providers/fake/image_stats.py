"""Cheap, real pixel statistics used by fake providers to derive
deterministic, image-content-driven scores and hashes — no network calls."""

from __future__ import annotations

import hashlib
import io

import imagehash
import numpy as np
from PIL import Image


def load_array(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return np.asarray(img, dtype=np.float32)


def luminance_contrast(arr: np.ndarray) -> float:
    lum = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    return float(lum.std() / 128.0)


def saturation_level(arr: np.ndarray) -> float:
    mx = arr.max(axis=-1)
    mn = arr.min(axis=-1)
    sat = np.where(mx > 0, (mx - mn) / np.clip(mx, 1, 255), 0)
    return float(sat.mean())


def edge_density(arr: np.ndarray) -> float:
    gray = arr.mean(axis=-1)
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    return float((gx.mean() + gy.mean()) / 255.0)


def outlier_pixel_ratio(arr: np.ndarray, expected_colors: list[tuple[int, int, int]], tolerance: float = 40.0) -> float:
    if not expected_colors:
        return 0.0
    flat = arr.reshape(-1, 3)
    expected = np.array(expected_colors, dtype=np.float32)
    dists = np.linalg.norm(flat[:, None, :] - expected[None, :, :], axis=-1)
    min_dist = dists.min(axis=1)
    return float((min_dist > tolerance).mean())


def checksum_sha256(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def perceptual_hash(image_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return str(imagehash.phash(img))
