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
        # MPS does not support tensors with total elements > INT_MAX;
        # fall back to CPU torch (still faster than numpy for large matrices).
        n_elems = X.shape[0] * X.shape[1]
        dev = DEVICE if n_elems < 2**31 else torch.device("cpu")
        X_t = torch.tensor(X, dtype=torch.float32, device=dev)
        Y_t = torch.tensor(Y, dtype=torch.float32, device=dev)
        n = X_t.shape[1]
        XtX = X_t.T @ X_t + lam * torch.eye(n, dtype=torch.float32, device=dev)
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
        n_total = embeddings.shape[0]
        batch_size = min(n_total, 4096)
        results = []
        for start in range(0, n_total, batch_size):
            end = min(start + batch_size, n_total)
            x = torch.tensor(
                embeddings[start:end].reshape(-1, n_in_ch, grid_h, grid_w),
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
            results.append(x.reshape(x.shape[0], -1).cpu().numpy())
        return np.concatenate(results, axis=0)

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


# -- Self-attention (Theorem 8.3, Paper 4) ---------------------------------


def generate_qk_projections(
    d_model: int,
    seed: int = 42,
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Generate random Q, K projection matrices (Kaiming init).

    Returns (W_q, W_k) each of shape (d_model, d_model).
    """
    rng = np.random.RandomState(seed)
    std = (2.0 / d_model) ** 0.5
    W_q = (rng.randn(d_model, d_model) * std).astype(np.float32)
    W_k = (rng.randn(d_model, d_model) * std).astype(np.float32)
    return W_q, W_k


def _torch_gating(x: object, gating: str) -> object:
    """Apply gating to a torch tensor (in-place safe)."""
    if gating == "relu":
        return F.relu(x)  # pyright: ignore[reportArgumentType]
    if gating == "swish":
        return x * torch.sigmoid(x)  # pyright: ignore[reportOperatorIssue,reportArgumentType]
    return x


def batch_self_attention(
    X: np.ndarray,
    n_heads: int = 1,
    W_q: np.ndarray | None = None,
    W_k: np.ndarray | None = None,
    W_v: np.ndarray | None = None,
    gating: str = "none",
) -> np.ndarray:
    """Self-attention over spatial positions (Theorem 8.3, Paper 4).

    Context-dependent Logarithmic Opinion Pooling: attention weights
    are the expert reliability coefficients in a Product of Experts.

    Parameters
    ----------
    X : (batch, seq_len, d_model) input features
    n_heads : parallel PoE aggregators (Remark 8.6)
    W_q, W_k : (d_model, d_model) projections, None = identity
    W_v : (d_model, d_model) value projection, None = identity
    gating : activation after attention ("none", "relu", "swish")

    Returns (batch, seq_len, d_model).
    """
    n_total, seq_len, d_model = X.shape

    if d_model % n_heads != 0:
        n_heads = 1
    d_head = d_model // n_heads

    # Adaptive chunk size: keep attention matrix under ~512 MB.
    # MPS lacks flash attention, so the full (batch, heads, seq, seq)
    # matrix is materialised. Without this cap the GPU memory pressure
    # causes throttling and kills throughput.
    _MAX_ATTN_BYTES = 512 * 1024 * 1024
    _per_sample = n_heads * seq_len * seq_len * 4
    _chunk_cap = max(1, _MAX_ATTN_BYTES // _per_sample) if _per_sample > 0 else 4096

    if HAS_TORCH:
        chunk_size = min(n_total, _chunk_cap)
        results: list[np.ndarray] = []

        # Single upload: X and projection matrices
        X_t = torch.tensor(X, dtype=torch.float32, device=DEVICE)
        W_q_t = (
            torch.tensor(W_q, dtype=torch.float32, device=DEVICE)
            if W_q is not None
            else None
        )
        W_k_t = (
            torch.tensor(W_k, dtype=torch.float32, device=DEVICE)
            if W_k is not None
            else None
        )
        W_v_t = (
            torch.tensor(W_v, dtype=torch.float32, device=DEVICE)
            if W_v is not None
            else None
        )

        for start in range(0, n_total, chunk_size):
            end = min(start + chunk_size, n_total)
            n = end - start
            x = X_t[start:end]  # slice, zero-copy on GPU

            Q = x @ W_q_t if W_q_t is not None else x
            K = x @ W_k_t if W_k_t is not None else x
            V = x @ W_v_t if W_v_t is not None else x

            Q = Q.reshape(n, seq_len, n_heads, d_head).transpose(1, 2)
            K = K.reshape(n, seq_len, n_heads, d_head).transpose(1, 2)
            V = V.reshape(n, seq_len, n_heads, d_head).transpose(1, 2)

            out = F.scaled_dot_product_attention(Q, K, V)
            out = out.transpose(1, 2).reshape(n, seq_len, d_model)
            out = _torch_gating(out, gating)
            results.append(out.cpu().numpy())

        return np.concatenate(results, axis=0)

    # numpy fallback
    Q = X @ W_q if W_q is not None else X.copy()
    K = X @ W_k if W_k is not None else X.copy()
    V = X @ W_v if W_v is not None else X.copy()

    Q = Q.reshape(n_total, seq_len, n_heads, d_head).transpose(0, 2, 1, 3)
    K = K.reshape(n_total, seq_len, n_heads, d_head).transpose(0, 2, 1, 3)
    V = V.reshape(n_total, seq_len, n_heads, d_head).transpose(0, 2, 1, 3)

    scale = np.float32(1.0 / np.sqrt(d_head))
    scores = np.einsum("bhid,bhjd->bhij", Q, K) * scale

    scores -= scores.max(axis=-1, keepdims=True)
    exp_scores = np.exp(scores)
    attn = exp_scores / exp_scores.sum(axis=-1, keepdims=True)

    out = np.einsum("bhij,bhjd->bhid", attn, V)
    out = out.transpose(0, 2, 1, 3).reshape(n_total, seq_len, d_model)

    if gating == "relu":
        out = np.maximum(0.0, out)
    elif gating == "swish":
        sig = 1.0 / (1.0 + np.exp(-np.clip(out, -50, 50)))
        out = out * sig

    return out


def search_v_projection(
    X: np.ndarray,
    n_heads: int,
    W_q: np.ndarray | None,
    W_k: np.ndarray | None,
    Y: np.ndarray,
    lam: float,
    gating: str = "none",
    n_candidates: int = 20,
    seed: int = 42,
) -> tuple[NDArray[np.float32], np.ndarray]:
    """GPU-optimized V projection search.

    Key optimizations over naive per-candidate batch_self_attention calls:
    1. X uploaded to GPU once (not 20 times)
    2. Q = X @ W_q, K = X @ W_k computed once (not 20 times)
    3. Ridge regression (XtX, linalg.solve) stays on GPU
    4. Accuracy evaluation stays on GPU
    5. Only the best candidate's output is downloaded to CPU

    Returns (best_W_v, best_output_flat).
    """
    n_total, seq_len, d_model = X.shape

    if d_model % n_heads != 0:
        n_heads = 1
    d_head = d_model // n_heads
    n_flat = d_model * seq_len

    # Generate candidate V projections
    rng = np.random.RandomState(seed + 1000)
    candidates: list[NDArray[np.float32]] = [np.eye(d_model, dtype=np.float32)]
    if d_model == 1:
        for s in np.arange(0.2, 2.1, 0.2):
            candidates.append(np.array([[s]], dtype=np.float32))
    else:
        for _ in range(n_candidates - 1):
            M = rng.randn(d_model, d_model).astype(np.float32)
            Q_orth, _ = np.linalg.qr(M)
            candidates.append(Q_orth.astype(np.float32))

    best_acc = -1.0
    best_W_v = candidates[0]
    best_out_flat: np.ndarray = np.zeros((n_total, n_flat), dtype=np.float32)

    if HAS_TORCH:
        n_elems = n_total * n_flat
        dev = DEVICE if n_elems < 2**31 else torch.device("cpu")
        _max_bytes = 512 * 1024 * 1024
        _per_samp = n_heads * seq_len * seq_len * 4
        _cap = max(1, _max_bytes // _per_samp) if _per_samp > 0 else 4096
        chunk_size = min(n_total, _cap)

        # Upload data to GPU once
        X_t = torch.tensor(X, dtype=torch.float32, device=dev)
        Y_t = torch.tensor(Y, dtype=torch.float32, device=dev)
        true_labels = torch.argmax(Y_t, dim=1)

        # Upload projection matrices once
        W_q_t = (
            torch.tensor(W_q, dtype=torch.float32, device=dev)
            if W_q is not None
            else None
        )
        W_k_t = (
            torch.tensor(W_k, dtype=torch.float32, device=dev)
            if W_k is not None
            else None
        )

        # Precompute Q = X @ W_q, K = X @ W_k (same for all candidates)
        Q_full = X_t @ W_q_t if W_q_t is not None else X_t
        K_full = X_t @ W_k_t if W_k_t is not None else X_t

        # Ridge regularization matrix (reused)
        eye_reg = lam * torch.eye(n_flat, dtype=torch.float32, device=dev)

        for W_v_cand in candidates:
            W_v_t = torch.tensor(W_v_cand, dtype=torch.float32, device=dev)

            # Forward pass in chunks; Q and K are pre-computed slices
            out_chunks: list[object] = []  # pyright: ignore[reportAssignmentType]
            for start in range(0, n_total, chunk_size):
                end = min(start + chunk_size, n_total)
                n = end - start

                Q = (
                    Q_full[start:end]
                    .reshape(n, seq_len, n_heads, d_head)
                    .transpose(1, 2)
                )
                K = (
                    K_full[start:end]
                    .reshape(n, seq_len, n_heads, d_head)
                    .transpose(1, 2)
                )
                V = (
                    (X_t[start:end] @ W_v_t)
                    .reshape(n, seq_len, n_heads, d_head)
                    .transpose(1, 2)
                )

                out = F.scaled_dot_product_attention(Q, K, V)
                out = out.transpose(1, 2).reshape(n, seq_len, d_model)
                out = _torch_gating(out, gating)
                out_chunks.append(out.transpose(1, 2).reshape(n, -1))

            full_out = torch.cat(out_chunks, dim=0)  # pyright: ignore[reportCallIssue,reportArgumentType]

            # Hybrid ridge: XtX matmul on GPU, linalg.solve on CPU
            # (GPU excels at large matmul; CPU LAPACK excels at small solve)
            XtX_gpu = full_out.T @ full_out + eye_reg
            XtY_gpu = full_out.T @ Y_t
            XtX_cpu = XtX_gpu.cpu()
            XtY_cpu = XtY_gpu.cpu()
            W_raw = torch.linalg.solve(XtX_cpu, XtY_cpu)

            # Accuracy: push small W_raw back to GPU for batched predict
            W_raw_gpu = W_raw.to(dev)
            bias = torch.mean(Y_t - full_out @ W_raw_gpu, dim=0)
            preds = torch.argmax(full_out @ W_raw_gpu + bias, dim=1)
            acc = float((preds == true_labels).float().mean())

            if acc > best_acc:
                best_acc = acc
                best_W_v = W_v_cand
                # Download only the best candidate's features
                best_out_flat = full_out.cpu().numpy()
    else:
        # numpy fallback: compute Q, K, attention weights once
        Q_np = X @ W_q if W_q is not None else X.copy()
        K_np = X @ W_k if W_k is not None else X.copy()

        Q_h = Q_np.reshape(n_total, seq_len, n_heads, d_head).transpose(0, 2, 1, 3)
        K_h = K_np.reshape(n_total, seq_len, n_heads, d_head).transpose(0, 2, 1, 3)

        sc = np.float32(1.0 / np.sqrt(d_head))
        scores = np.einsum("bhid,bhjd->bhij", Q_h, K_h) * sc
        scores -= scores.max(axis=-1, keepdims=True)
        exp_scores = np.exp(scores)
        attn_w = exp_scores / exp_scores.sum(axis=-1, keepdims=True)

        for W_v_cand in candidates:
            V_np = X @ W_v_cand
            V_h = V_np.reshape(n_total, seq_len, n_heads, d_head).transpose(0, 2, 1, 3)
            out = np.einsum("bhij,bhjd->bhid", attn_w, V_h)
            out = out.transpose(0, 2, 1, 3).reshape(n_total, seq_len, d_model)
            if gating == "relu":
                out = np.maximum(0.0, out)
            elif gating == "swish":
                sig = 1.0 / (1.0 + np.exp(-np.clip(out, -50, 50)))
                out = out * sig

            out_flat = out.transpose(0, 2, 1).reshape(n_total, -1)
            W_t, b_t = ridge_solve(out_flat.astype(np.float64), Y, lam)
            preds = np.argmax(out_flat.astype(np.float64) @ W_t.T + b_t, axis=1)
            acc = float(np.mean(preds == np.argmax(Y, axis=1)))

            if acc > best_acc:
                best_acc = acc
                best_W_v = W_v_cand
                best_out_flat = out_flat

    return best_W_v, best_out_flat
