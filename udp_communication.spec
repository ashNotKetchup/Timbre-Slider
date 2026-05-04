# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect submodules for each dependency category
torch_hiddenimports = collect_submodules('torch')
torchaudio_hiddenimports = collect_submodules('torchaudio')
librosa_hiddenimports = collect_submodules('librosa')

# List of modules to collect submodules from
modules_to_collect = [
    'numpy', 'scipy', 'sklearn',  # Core ML
    'soundfile', 'einops',  # Audio
    'timbral_models',  # Audio features
    'huggingface_hub',  # HuggingFace (safetensors handled explicitly)
    'matplotlib', 'seaborn', 'pandas', 'ipywidgets', 'IPython',  # Visualisation
    'tqdm', 'packaging',  # Progress & Misc
]

# Collect submodules for all modules
hidden_imports = []
for module in modules_to_collect:
    hidden_imports.extend(collect_submodules(module))

# Combine all hidden imports
all_hiddenimports = (
    torch_hiddenimports + torchaudio_hiddenimports + librosa_hiddenimports +
    hidden_imports +
    [
        # Explicitly include modules that may not be collected properly
        'dotenv',
        'safetensors',
        'safetensors.torch',
        'soundfile',
        'cached_conv',
        'einops',
        # Backend modules
        'backend',
        'backend.udp_communication',
        'backend.timbre_VAE',
        'backend.timbre_VAE.models',
        'backend.timbre_VAE.load_generative_model',
    ]
)

torch_datas = collect_data_files('torch')
torchaudio_datas = collect_data_files('torchaudio')
matplotlib_datas = collect_data_files('matplotlib')
seaborn_datas = collect_data_files('seaborn')


a = Analysis(
    ['backend/run_server.py'],
    pathex=[],
    binaries=[],
    datas=torch_datas + torchaudio_datas + matplotlib_datas + seaborn_datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch.distributed._sharded_tensor', 'torch.distributed._sharding_spec', 'tensorboard'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='udp_communication',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='udp_communication.app',
    icon=None,
    bundle_identifier=None,
)
