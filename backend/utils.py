"""
Utility functions for the backend package.
"""
import torch


def remove_parametrizations(module: torch.nn.Module) -> None:
    """Remove parametrizations from a PyTorch module (for TorchScript export)."""
    try:
        from torch.nn.utils import parametrize as _parametrize
    except Exception:
        return
    for m in module.modules():
        if hasattr(m, "parametrizations"):
            names = list(getattr(m, "parametrizations").keys())
            for pname in names:
                try:
                    _parametrize.remove_parametrizations(m, pname, leave_parametrized=True)
                except Exception:
                    pass
