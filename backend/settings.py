"""Backend settings: backend/settings.yaml over the defaults below.

Read a value with setting('devices', 'training'). The file is read once, the first time a value
is needed; restart the server after editing it. The testbed overrides values per experiment
with override(). In the PyInstaller build, a settings.yaml next to the executable is used if
there is one.
"""
import copy
import os
import sys

DEFAULTS = {
    'devices': {'generative_model': 'auto', 'training': 'auto', 'feature_workers': 'auto'},
    'training': {'num_epochs': 4000, 'batch_size': 1024, 'learning_rate': 0.01,
                 'alpha_max': 10.0, 'beta_max': 0.1, 'theta_max': 10.0},
    'decoding': {'delta': True, 'smoothing': 1.5},
}

_current = None


def _paths():
    paths = [os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.yaml')]
    if getattr(sys, 'frozen', False):
        paths.insert(0, os.path.join(os.path.dirname(sys.executable), 'settings.yaml'))
    return paths


def _merge(base, over):
    out = copy.deepcopy(base)
    for key, value in (over or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load():
    """(Re)read settings.yaml over the defaults."""
    global _current
    data = {}
    for path in _paths():
        if os.path.exists(path):
            try:
                import yaml
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                print(f"[settings] {path}")
            except Exception as e:
                print(f"[settings] could not read {path} ({e}); using the defaults")
            break
    _current = _merge(DEFAULTS, data)
    return _current


def setting(*keys):
    """The value at keys, e.g. setting('decoding', 'smoothing') or setting('training')."""
    value = _current if _current is not None else load()
    for key in keys:
        value = value[key]
    return copy.deepcopy(value)


def override(updates):
    """Merge updates (same structure as settings.yaml) over the current settings."""
    global _current
    _current = _merge(_current if _current is not None else load(), updates)
