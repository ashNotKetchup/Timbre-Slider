# Timbre-Slider

Example- and semantic-driven timbre interpolation in latent space. Adapted from the [Slider project](https://www.eca.ed.ac.uk/) at the University of Edinburgh.

Timbre-Slider encodes audio into a neural latent space (via RAVE or Stable Audio Open 1.0), extracts perceptual timbre features, trains a lightweight VAE to learn a control subspace, and exposes interactive sliders — in a Jupyter notebook or a Max/MSP frontend — to manipulate timbral qualities in real time.

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10+** | Tested on 3.12–3.14 |
| **Git** | With submodule support |
| **Max/MSP** (optional) | For the frontend patch in `frontend/` |
| **HuggingFace account** | Free — needed for Stable Audio Open model weights |

## Quick Start

```bash
# 1. Clone with submodule
git clone --recursive https://github.com/ashNotKetchup/Timbre-Slider.git
cd Timbre-Slider

# 2. Set up environment & install deps
make setup

# 3. Add your HuggingFace token
#    (make setup creates .env from .env.example if it doesn't exist)
#    Edit .env and replace the placeholder with your real token
#    Get one at https://huggingface.co/settings/tokens
nano .env

# 4. Download the Stable Audio Open model (~1.2 GB, cached in ~/.cache/huggingface)
make download-model

# 5. Launch the interface (starts server + opens Max/MSP)
make launch-interface
```

If you already cloned without `--recursive`:
```bash
git submodule update --init --recursive
```

## Project Structure

```
Timbre-Slider/
├── udp_communication.py       # HTTP server — main entry point
├── learn_subspace.py           # Notebook-style subspace learning script
├── export.py                   # TorchScript export for Stable Audio autoencoder
├── mass_preprocess.py          # Batch feature preprocessing
├── Makefile                    # Setup & run commands
├── requirements.txt            # Direct Python dependencies
├── requirements-lock.txt       # Full pinned versions (pip freeze)
├── .env.example                # Template for environment variables
│
├── timbre_VAE/                 # Core library
│   ├── load_generative_model.py  # Loads RAVE / Stable Audio models
│   ├── features.py               # Audio feature extraction
│   ├── vae_train.py              # VAE training logic
│   ├── interface.py              # Jupyter slider interface
│   ├── interaction.py            # Slider-to-audio helpers
│   ├── load_audio.py             # Audio buffer management
│   ├── plotting.py               # Loss & correlation plots
│   ├── logger.py                 # Request logging
│   ├── global_scaler.py          # Latent scaling/compression
│   └── models/                   # Model definitions & pretrained loading
│
├── control_models/             # VAE control model wrapper
├── frontend/                   # Max/MSP patches for the GUI
├── sounds/                     # Your audio samples go here
├── precomputed/                # Cached features & trained control models
│
└── streamable-stable-audio-open/  # Submodule: streaming autoencoder
```

## How It Works

1. **Encode** — Audio files are encoded into latent representations using a generative model (RAVE `.ts` models or Stable Audio Open via HuggingFace).
2. **Extract features** — Perceptual timbre features (spectral centroid, flatness, loudness, etc. or AudioCommons descriptors) are computed for each sound.
3. **Train VAE** — A small VAE maps between timbre feature space and the latent space, learning a semantically meaningful control subspace.
4. **Interact** — Sliders in Jupyter or Max/MSP let you move through the learned subspace, decoding new audio in real time.

## Generative Models

### RAVE models (`.ts` TorchScript)
Place RAVE `.ts` models in `timbre_VAE/models/RAVE_models/generative_models/`. These are available from the [RAVE model collection](https://acids-ircam.github.io/rave_models_music/).

### Stable Audio Open
Uses `stabilityai/stable-audio-open-1.0` from HuggingFace (downloaded automatically with your `HF_TOKEN`). See [timbre_VAE/README_streamable_stable_audio_open.md](timbre_VAE/README_streamable_stable_audio_open.md) for details on the streaming autoencoder.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `HF_TOKEN` | HuggingFace access token ([get one here](https://huggingface.co/settings/tokens)) |

## Make Targets

| Command | Description |
|---|---|
| `make setup` | Create venv, install deps, init submodule, create `.env` |
| `make download-model` | Download & cache Stable Audio Open weights (~1.2 GB) |
| `make launch-interface` | Start server + open Max/MSP frontend |
| `make run-udp` | Start the HTTP server only |
| `make open-frontend` | Open the Max/MSP patch only |
| `make preprocess` | Batch-compute features for audio in `sounds/` |
| `make install` | Reinstall deps in existing venv |
| `make check-env` | Verify `.env` is configured |

## Adding Your Own Sounds

1. Place `.wav`, `.aif`, or `.mp3` files in a folder (e.g. `sounds/my_sounds/`)
2. The system computes features automatically when you load the folder through the Max/MSP frontend, or run `make preprocess`
3. Features are cached as `.pkl` files alongside the audio

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'models'` | Submodule not initialised — run `git submodule update --init --recursive` |
| `EnvironmentError: HF_TOKEN not set` | Create `.env` with your token — see [Environment Variables](#environment-variables) |
| `FileNotFoundError: ...generative_models/xyz.ts` | Download RAVE models to `timbre_VAE/models/RAVE_models/generative_models/` |
| `ValueError: setting an array element with a sequence` | Use pickle for saving data (see `.github/copilot-instructions.md`) |
| `EOFError: Ran out of input` | Delete the corrupted `.pkl` cache file and rerun |

## License

TBC
