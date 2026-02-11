# Copilot Instructions for Timbre-Slider

## Project Overview
- **Timbre-Slider** enables example- and semantic-driven timbre interpolation in latent space, adapting the University of Edinburgh's Slider project.
- Integrates with the `streamable-stable-audio-open` submodule for real-time audio autoencoding using Stable Audio Open 1.0 models.
- Main workflows involve extracting features from audio, encoding/decoding with VAE/autoencoders, and manipulating latent representations for creative sound design.

## Key Components
- **Top-level scripts:**
  - `vae_train.py`, `learn_subspace.py`, `features.py`, `export.py`: Core scripts for training, feature extraction, and exporting models.
  - `interface.py`, `interaction.py`: User interaction and interface logic.
- **Audio models:**
  - `models/`: Custom autoencoders, blocks, and utilities for neural audio processing.
  - `generative_models/`: TorchScript-exported models for use in MaxMSP/PureData.
- **Feature extraction:**
  - `features/`: Audio feature computation modules.
- **Data:**
  - `sounds/`: Example audio files for training and testing.
  - `features/preprocessed_sound_data.npz` or `.pkl`: Cached feature/latent data (use pickle for complex objects).

## Developer Workflows
- **Feature extraction:**
  - Use `batch_compute_features` and `get_features` to process audio files. If caching, prefer pickle over npz for non-uniform data.
- **Model training:**
  - Run `vae_train.py` to train VAEs on extracted features. Adjust `input_dim` and `latent_dim` as needed.
- **Exporting models:**
  - Use `streamable-stable-audio-open/export.py` with `--streaming` for TorchScript export. Example:
    ```bash
    python export.py --output generative_models/vae.ts --streaming
    ```
- **Testing:**
  - No unified test suite; test by running scripts and inspecting outputs. For model export, use the `--test` flag.

## Conventions & Patterns
- **Data serialization:**
  - Use `pickle` for saving lists of dicts or non-uniform arrays. Always convert `dict_keys` to `list` before pickling.
- **Device selection:**
  - Scripts support `--test-device` and `--export-device` flags (`cpu`, `cuda`, `mps`).
- **MaxMSP/PureData integration:**
  - Exported TorchScript models are intended for use with `nn~` objects. Use buffer sizes >4096 to avoid artifacts.

## Integration Points
- **External dependencies:**
  - HuggingFace for model weights, PyTorch for neural models, and MaxMSP/PureData for downstream audio applications.
- **Submodules:**
  - `streamable-stable-audio-open` is a key submodule for autoencoder logic and export scripts.

## Examples
- Export a streaming autoencoder:
  ```bash
  cd streamable-stable-audio-open
  python export.py --output ../generative_models/vae.ts --streaming
  ```
- Extract features and train VAE:
  ```python
  sound_files = [f for f in os.listdir('sounds') if f.endswith('.aif')]
  sound_data = get_features(sound_files, feature_type, model=model)
  vae = VAE(input_dim=..., latent_dim=...)
  vae.train(sound_data)
  ```

## Troubleshooting
- If you see `ValueError: setting an array element with a sequence`, use pickle for saving data.
- If you see `TypeError: cannot pickle 'dict_keys' object`, convert all `dict_keys` to `list` before pickling.
- If you see `EOFError: Ran out of input`, delete the corrupted cache file and rerun the script.

---
For more details, see the top-level and submodule `README.md` files.
