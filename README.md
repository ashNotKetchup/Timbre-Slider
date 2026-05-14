# MALT (Manipulating Audio with Latent Timbre)

Example- and semantic-driven timbre interpolation in latent space. 

MALT encodes audio into a neural latent space (via RAVE or Stable Audio Open 1.0), extracts perceptual timbre features, trains a lightweight VAE to learn a control subspace, and exposes interactive sliders — in a Jupyter notebook or a Max/MSP frontend — to manipulate timbral qualities of samples.

## How It Works

1. **Encode** — Audio files are encoded into latent representations using a generative model (RAVE `.ts` models or Stable Audio Open via HuggingFace).
2. **Extract features** — Perceptual timbre features (spectral centroid, flatness, loudness, etc. or AudioCommons descriptors) are computed for each sound.
3. **Train VAE** — A small VAE maps between timbre feature space and the latent space, learning a semantically meaningful control subspace.
4. **Interact** — Sliders in Jupyter or Max/MSP let you move through the learned subspace, decoding new audio in real time.

## 👤 For Users

**Want to use the app?** See our [Releases](../../releases) page for pre-built packages, then read [`how-to.md`](how-to.md) for usage instructions.

## 🛠️ For Developers

This section covers development setup and contribution guidelines.

### Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10+** | Tested on 3.12–3.14 |
| **Git** | With submodule support |
| **Max/MSP** (optional) | For the frontend patch in `frontend/` |

### Quick Start (Development)

1. Clone the repo with submodules:
   ```bash
   git clone --recursive https://github.com/ashNotKetchup/Timbre-Slider.git
   cd Timbre-Slider
   ```

2. Set up the environment:
   ```bash
   make setup  # Install dependencies
   ```

3. Add your model:
   - Place TorchScript models (`.ts` files) in `data/models/`
   - See [Generative Models](#generative-models) for model sources

4. Launch the interface:
   ```bash
   make launch-interface
   ```

If you already cloned without `--recursive`:
```bash
git submodule update --init --recursive
```

### Project Structure

### Core Files

```
Timbre-Slider/
├── how-to.md                   # 👈 User guide (simple usage)
├── README.md                   # This file
├── Makefile                    # Build & run commands
├── requirements.txt            # Python dependencies
├── requirements-lock.txt       # Pinned versions
│
├── backend/                    # Main backend code
│   ├── run_server.py           # HTTP server — main entry point
│   ├── timbre_VAE/             # Core library
│   │   ├── vae_train.py        # VAE training logic
│   │   ├── features.py         # Audio feature extraction
│   │   ├── load_generative_model.py  # Loads models
│   │   ├── interface.py        # Jupyter slider interface
│   │   ├── interaction.py      # Slider-to-audio helpers
│   │   ├── plotting.py         # Plotting utilities
│   │   ├── logger.py           # Request logging
│   │   ├── global_scaler.py    # Latent scaling/compression
│   │   └── progress.py         # Progress tracking
│   ├── utilities/              # Utilities
│   │   ├── load_audio.py       # Audio loading
│   │   └── mass_preprocess.py  # Batch preprocessing
│   └── SAO scripts/            # Stable Audio Open utilities
│       └── export.py           # TorchScript export
│
├── data/                       # Data and models
│   ├── models/                 # Place TorchScript models here
│   │   ├── RAVE_models/
│   │   │   └── generative_models/  # RAVE .ts files
│   │   └── StableAudio/        # Stable Audio .ts files
│   ├── audio/                  # Audio files
│   └── eg_sounds/              # Example sounds
│
├── frontend/                   # Max/MSP patches & UI
│   ├── frontend.maxpat         # Main interface patch
│   ├── M4L.SimplerPolyVoice~.maxpat
│   ├── Minimal sampler.maxpat
│   └── *.js                    # Supporting scripts
│
├── test sounds/                # Test audio samples
```




### Generative Models

Place TorchScript models (`.ts` files) in `data/models/`:

- **RAVE models**: Available from the [RAVE model collection](https://acids-ircam.github.io/rave_models_music/)
- **Stable Audio Open**: Export TorchScript from `streamable-stable-audio-open` submodule using `export.py`

Example:
```bash
cp path/to/model.ts data/models/
```

### Make Targets

| Command | Description |
|---|---|
| `make setup` | Create venv, install deps, init submodule |
| `make launch-interface` | Minimal mode: show only `(Re)Launchin MALT server on :5001`, then open frontend |
| `make restart-server` | Minimal mode: show only `(Re)Launchin MALT server on :5001` |
| `make run-udp` | Stop existing :5001 server, then start the HTTP server only |
| `make open-frontend` | Open the Max/MSP patch only |
| `make preprocess` | Batch-compute features for audio in `sounds/` |
| `make install` | Reinstall deps in existing venv |

### Log depth

The server supports a `LOG_DEPTH` environment flag:

- `LOG_DEPTH=minimal`: suppresses warnings and bracket-prefixed logs (for quiet live use)
- default (`normal`): standard informational logs

`make launch-interface` and `make restart-server` run with `LOG_DEPTH=minimal` automatically.

### Adding Your Own Sounds

1. Place `.wav`, `.aif`, or `.mp3` files in a folder (e.g. `sounds/my_sounds/`)
2. The system computes features automatically when you load the folder through the Max/MSP frontend, or run `make preprocess`
3. Features are cached as `.pkl` files alongside the audio

### Building a Release

To create a distributable package with the backend server bundled:

1. **Prepare the release**:
   - Ensure all models are in `data/models/`
   - Test the app with `make launch-interface`

2. **Build the executable**:
   ```bash
   make build
   ```
   This uses PyInstaller to create a standalone binary from `backend/backend.spec`. The output will be in `dist/`.

3. **Assemble the distribution**:
   - Copy `frontend/` into `dist/frontend/`
   - Copy `data/` into `dist/data/`
   - The `dist/` folder is now a complete, standalone application

4. **Create a GitHub Release**:
   - Compress the `dist/` folder: `zip -r Timbre-Slider-v1.0.0.zip dist/`
   - Tag a commit: `git tag v1.0.0`
   - Push the tag: `git push origin v1.0.0`
   - Create a release on GitHub and upload the `.zip` file
   - Include `how-to.md` in the release notes or as a text file

### Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'models'` | Submodule not initialised — run `git submodule update --init --recursive` |
| `FileNotFoundError: ...model.ts` | Place TorchScript models in `data/models/` |
| `ValueError: setting an array element with a sequence` | Use pickle for saving data (see `.github/copilot-instructions.md`) |
| `EOFError: Ran out of input` | Delete the corrupted `.pkl` cache file and rerun |

## License

TBC
