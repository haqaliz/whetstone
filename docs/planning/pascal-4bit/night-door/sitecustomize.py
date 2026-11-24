"""Pascal (sm_61) shim: chunk the query axis of SDPA.

Torch ships only the math SDPA kernel for compute capability 6.1, so a 10k-token
prefill materialises (heads x 10k x 10k) and OOMs an 8 GB card. Chunking the
query axis is the same arithmetic with a bounded temporary. Gated by
WHETSTONE_PASCAL_SDPA=1 so it is inert everywhere else.
"""
import os

if os.environ.get("WHETSTONE_PASCAL_SDPA") == "1":
    try:
        import torch
    except Exception:
        pass
    else:
        _orig = torch.nn.functional.scaled_dot_product_attention
        _CHUNK = 256

        def _chunked(
            query,
            key,
            value,
            attn_mask=None,
            dropout_p=0.0,
            is_causal=False,
            scale=None,
            enable_gqa=False,
            **kwargs,
        ):
            if query.shape[-2] <= _CHUNK:
                return _orig(
                    query,
                    key,
                    value,
                    attn_mask=attn_mask,
                    dropout_p=dropout_p,
                    is_causal=is_causal,
                    scale=scale,
                    enable_gqa=enable_gqa,
                    **kwargs,
                )
            outs = []
            for start in range(0, query.shape[-2], _CHUNK):
                end = min(start + _CHUNK, query.shape[-2])
                q = query[..., start:end, :]
                if attn_mask is not None:
                    outs.append(
                        _orig(
                            q,
                            key,
                            value,
                            attn_mask=attn_mask[..., start:end, :],
                            dropout_p=dropout_p,
                            is_causal=False,
                            scale=scale,
                            enable_gqa=enable_gqa,
                            **kwargs,
                        )
                    )
                elif is_causal:
                    qi = torch.arange(start, end, device=query.device)
                    ki = torch.arange(key.shape[-2], device=query.device)
                    outs.append(
                        _orig(
                            q,
                            key,
                            value,
                            attn_mask=ki.unsqueeze(0) <= qi.unsqueeze(1),
                            dropout_p=dropout_p,
                            is_causal=False,
                            scale=scale,
                            enable_gqa=enable_gqa,
                            **kwargs,
                        )
                    )
                else:
                    outs.append(
                        _orig(
                            q,
                            key,
                            value,
                            attn_mask=None,
                            dropout_p=dropout_p,
                            is_causal=False,
                            scale=scale,
                            enable_gqa=enable_gqa,
                            **kwargs,
                        )
                    )
            return torch.cat(outs, dim=-2)

        torch.nn.functional.scaled_dot_product_attention = _chunked
