# VAE testbed

A small harness for trying control-VAE architectures on the MALT backend. Set a folder in `config.yaml` and run it. A browser page then shows:

- the training losses, live
- the first sample in the folder, encoded and decoded
- one editable row per latent dimension; drawing on a row sends the edited latent back to the backend and plays the result

## Run

From the repo root, one command loads the model, trains, and opens the page:

```bash
make testbed                                # uses testbed/config.yaml
make testbed FOLDER=~/samples/foley         # override the folder for this run
make testbed CONFIG=testbed/other.yaml      # use another config
```

`make testbed` is the same as `.venv/bin/python -m testbed.run [config] [--folder PATH]`.

The page opens at http://127.0.0.1:8765. Running the command again stops the testbed that is already running and starts a new run, and an open page switches to the new run by itself. Stop with Ctrl-C.

## How it talks to the backend

The testbed imports `backend/run_server.py` and passes it the same message dicts the Max patch sends. They are round-tripped through JSON, so they are exactly what its HTTP server would receive:

| step | message |
|---|---|
| 1 | `{"type": "load_model", "content": <generative_model>}` |
| 2 | `{"type": "set_regularisation", "content": <feature_type>}` |
| 3 | `{"type": "request_load_folder", "content": <folder>}` |
| 4 | `{"type": "request_retrain_vae"}` |
| 5 | `{"type": "request_latent", "content": <sample>}` |
| 6 | `{"type": "request_audio", "content": <latent json>}` (first unedited, then once per edit) |

The trajectories you edit are the `vector` data from the `request_latent` reply. That data is scaled to about ±2 and decimated in time by the backend's `LatentRepresentation`, the same as in the Max UI. The page's **Backend messages** panel lists every request and reply.

No files in `backend/` or `frontend/` are changed. While `request_retrain_vae` runs, the testbed swaps a few backend names in memory and restores them afterwards:

- `run_server.VAE` → builds the class from `vae.class` in the config
- `run_server.train_vae` → passes the `train:` values from the config, then saves the run
- `vae_train.vae_loss` and `vae_train.increment_progress_bar` → read each batch's losses, so the chart updates live. The numbers are the per-epoch sums that `train_vae` records.

## Trying a new architecture

Put the class anywhere importable, e.g. `testbed/models/my_vae.py`, then set:

```yaml
vae:
  class: testbed.models.my_vae.MyVAE
  kwargs: {hidden: 256}
```

The backend builds it as `MyVAE(input_dim=..., latent_dim=..., **kwargs)`. It must have the same interface as `backend.timbre_VAE.vae_train.VAE`:

- `forward(x) -> (recon, mu, logvar)`
- `reparameterize(mu, logvar)`
- `encode_mu(x)`
- `decode(z)`

`latent_dim` is the number of attribute dimensions plus 4, which is set in `prepare_data`.

The backend currently feeds the VAE single frames, not sequences. `train_vae` draws random frames of shape `(batch, input_dim)`, and `Model.encode`/`decode` pass one clip as `(T, dim)`. A conv or recurrent model will run on that unchanged, but it only sees time if you add sequence batching to `train_vae`.

## Each run

Each run creates `testbed/runs/<timestamp>_<name>/` containing:

- `config.yaml`: a copy of the config used
- `losses.json`: per-epoch losses and loss weights
- `vae.pt`: the state dict, class, dimensions and history
- `audio/`: `original.wav`, `vae_recon.wav`, and `edit_###.wav` with its edited latent JSON and the backend's spectrogram PNGs

Features are cached by the backend, as `.pkl` files in the sample folder, the same way the app caches them.

## Feature-cache warning

After `request_load_folder` the testbed reads the backend's feature cache. If the reconstructions the attributes were computed from are under half the input length, it shows a warning.

This can happen because of how `batch_compute_features` decodes. It calls `Model.decode(enc)` with `enc` shaped `(1, C, T)`. `Model.decode` first tries `latent.T`, which is `(T, C, 1)`. With a convolutional decoder that call can succeed, returning a batch of T one-frame clips instead of one clip. Their average is then used as `recon_audio`, which is 2048 samples long. A stand-in conv model reproduced this.

Whether the real SAO export does the same depends on whether it accepts a batch larger than 1. The warning tells you on the first run.
