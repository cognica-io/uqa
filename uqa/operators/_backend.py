#
# Unified Query Algebra
#
# Copyright (c) 2023-2026 Cognica, Inc.
#

"""Compute backend: PyTorch when available, numpy fallback.

All tensor operations stay on GPU throughout the pipeline.
numpy conversion happens only at the final boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

try:
    import torch  # pyright: ignore[reportMissingImports]
    import torch.nn.functional as F  # pyright: ignore[reportMissingImports]

    HAS_TORCH = True

    if torch.cuda.is_available():
        DEVICE = torch.device("cuda")
    elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
        DEVICE = torch.device("mps")
    else:
        DEVICE = torch.device("cpu")
except ImportError:
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    HAS_TORCH = False
    DEVICE = None


def device_name() -> str:
    if DEVICE is not None:
        return str(DEVICE)
    return "cpu (numpy)"


# -- Kernel builder --------------------------------------------------------


def _build_kernel_np(hop_weights: list[float]) -> NDArray[np.float32]:
    total = sum(hop_weights)
    if total <= 0:
        return np.zeros((3, 3), dtype=np.float32)
    w_s = hop_weights[0] / total
    w_n = hop_weights[1] / total if len(hop_weights) > 1 else 0.0
    k = np.zeros((3, 3), dtype=np.float32)
    k[1, 1] = w_s
    k[0, 1] = k[2, 1] = k[1, 0] = k[1, 2] = w_n / 4
    return k


# -- Ridge regression ------------------------------------------------------


def ridge_solve(
    X: np.ndarray, Y: np.ndarray, lam: float
) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    """Ridge regression: W = (X^T X + lambda I)^{-1} X^T Y.

    Returns (W, bias) where W is (n_classes, n_features).
    """
    if HAS_TORCH and X.shape[0] >= 32:
        X_t = torch.tensor(X, dtype=torch.float32, device=DEVICE)
        Y_t = torch.tensor(Y, dtype=torch.float32, device=DEVICE)
        n = X_t.shape[1]
        XtX = X_t.T @ X_t + lam * torch.eye(n, dtype=torch.float32, device=DEVICE)
        XtY = X_t.T @ Y_t
        W_raw = torch.linalg.solve(XtX, XtY)
        bias = torch.mean(Y_t - X_t @ W_raw, dim=0)
        return (
            W_raw.T.cpu().numpy().astype(np.float64),
            bias.cpu().numpy().astype(np.float64),
        )

    n = X.shape[1]
    XtX = X.T @ X + lam * np.eye(n)
    XtY = X.T @ Y
    W_raw = np.linalg.solve(XtX, XtY)
    bias = np.mean(Y - X @ W_raw, axis=0)
    return W_raw.T, bias


# -- Grid forward (stays on GPU) -------------------------------------------


def grid_forward(
    embeddings: np.ndarray,
    grid_h: int,
    grid_w: int,
    stages: list[tuple[np.ndarray, int, str]],
    gating: str = "none",
) -> np.ndarray:
    """Full conv+pool pipeline. One GPU upload, one download.

    Parameters
    ----------
    embeddings : (batch, n_features) flat features
    grid_h, grid_w : spatial dims of current feature map
    stages : [(kernel_array, pool_size, pool_method), ...]
        kernel_array: (out_ch, in_ch, kH, kW) conv kernel weights
    gating : activation function

    Returns (batch, n_features) flattened feature matrix.
    """
    if HAS_TORCH:
        n_in_ch = embeddings.shape[1] // (grid_h * grid_w)
        if n_in_ch < 1:
            n_in_ch = 1
        x = torch.tensor(
            embeddings.reshape(-1, n_in_ch, grid_h, grid_w),
            dtype=torch.float32,
            device=DEVICE,
        )

        for kernel_np, pool_size, pool_method in stages:
            kernel = torch.tensor(kernel_np, dtype=torch.float32, device=DEVICE)
            x = F.conv2d(x, kernel, padding=1)
            if gating == "relu":
                x = F.relu(x)
            elif gating == "swish":
                x = x * torch.sigmoid(x)
            if pool_size > 1:
                if pool_method == "max":
                    x = F.max_pool2d(x, pool_size)
                else:
                    x = F.avg_pool2d(x, pool_size)

        return x.reshape(x.shape[0], -1).cpu().numpy()

    # numpy fallback (single-channel only)
    batch = embeddings.reshape(-1, grid_h, grid_w).astype(np.float32)
    for kernel_np, pool_size, pool_method in stages:
        if kernel_np.ndim == 4 and kernel_np.shape[0] == 1:
            kernel_2d = kernel_np[0, 0]
        else:
            kernel_2d = (
                kernel_np.reshape(3, 3) if kernel_np.size == 9 else kernel_np[0, 0]
            )
        h, w = batch.shape[1], batch.shape[2]
        padded = np.pad(batch, ((0, 0), (1, 1), (1, 1)), mode="constant")
        out = np.zeros_like(batch)
        for di in range(3):
            for dj in range(3):
                if kernel_2d[di, dj] != 0:
                    out += padded[:, di : di + h, dj : dj + w] * kernel_2d[di, dj]
        if gating == "relu":
            out = np.maximum(0.0, out)
        elif gating == "swish":
            sig = 1.0 / (1.0 + np.exp(-np.clip(out, -50, 50)))
            out = out * sig
        if pool_size > 1:
            new_h = h // pool_size
            new_w = w // pool_size
            cropped = out[:, : new_h * pool_size, : new_w * pool_size]
            reshaped = cropped.reshape(
                batch.shape[0], new_h, pool_size, new_w, pool_size
            )
            if pool_method == "max":
                batch = reshaped.max(axis=(2, 4))
            else:
                batch = reshaped.mean(axis=(2, 4))
        else:
            batch = out
    return batch.reshape(batch.shape[0], -1)


# -- Conv weight search (stays on GPU) ------------------------------------


def hop_weights_to_kernel(hop_weights: list[float]) -> NDArray[np.float32]:
    """Convert [w_self, w_neighbor] to (1, 1, 3, 3) kernel array."""
    k = _build_kernel_np(hop_weights)
    return k.reshape(1, 1, 3, 3)


# -- Batch dense / softmax / batchnorm ------------------------------------


def batch_dense(
    X: np.ndarray,
    weights: np.ndarray,
    bias: np.ndarray,
    gating: str = "none",
) -> np.ndarray:
    """Batch dense layer: out = X @ W^T + bias, then gating."""
    if HAS_TORCH and X.shape[0] >= 4:
        X_t = torch.tensor(X, dtype=torch.float32, device=DEVICE)
        W_t = torch.tensor(weights, dtype=torch.float32, device=DEVICE)
        b_t = torch.tensor(bias, dtype=torch.float32, device=DEVICE)
        out = X_t @ W_t.T + b_t
        if gating == "relu":
            out = F.relu(out)
        elif gating == "swish":
            out = out * torch.sigmoid(out)
        return out.cpu().numpy()

    out = X @ weights.T + bias
    if gating == "relu":
        out = np.maximum(0.0, out)
    elif gating == "swish":
        sig = 1.0 / (1.0 + np.exp(-np.clip(out, -50, 50)))
        out = out * sig
    return out


def batch_softmax(X: np.ndarray) -> np.ndarray:
    """Batch softmax."""
    if HAS_TORCH and X.shape[0] >= 4:
        X_t = torch.tensor(X, dtype=torch.float32, device=DEVICE)
        return F.softmax(X_t, dim=-1).cpu().numpy()

    shifted = X - X.max(axis=-1, keepdims=True)
    exp_vals = np.exp(shifted)
    return exp_vals / exp_vals.sum(axis=-1, keepdims=True)


def batch_batchnorm(X: np.ndarray, epsilon: float = 1e-5) -> np.ndarray:
    """Batch normalization."""
    if X.shape[0] < 2:
        return X

    if HAS_TORCH and X.shape[0] >= 4:
        X_t = torch.tensor(X, dtype=torch.float32, device=DEVICE)
        mean = X_t.mean(dim=0)
        var = X_t.var(dim=0, unbiased=False)
        out = (X_t - mean) / torch.sqrt(var + epsilon)
        return out.cpu().numpy()

    mean = X.mean(axis=0)
    var = X.var(axis=0)
    return (X - mean) / np.sqrt(var + epsilon)
