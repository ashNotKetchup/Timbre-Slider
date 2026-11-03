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

## Settings and hardware

Training, decoding and hardware settings live in `backend/settings.yaml`, which the Max app uses too. To change them for one experiment, override them under `settings:` in the testbed config, with the same structure.

The `devices` defaults pick whatever runs fastest:

- **`generative_model: auto`** runs Stable Audio on the GPU when there is one (the Apple GPU on an M-series Mac). If something fails there, it switches to the CPU and says so in the console.
- **`training: auto`** times a few batches on each device the machine has, and trains on the fastest.
- **`feature_workers: auto`** extracts features with one process per CPU core but one.

To compare settings, look at the console lines `[features] ... encode + reconstruct ... s`, `[train] auto device: ...`, `[train] ... ms/epoch` and `[model] Decoded ... s`, or at the ms column of the page's Backend messages.

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
- `run_server.train_vae` → records the run's settings and saves the run
- `vae_train.vae_loss` and `vae_train.increment_progress_bar` → read each batch's losses, so the chart updates live. The numbers are per-epoch means over batches, as `train_vae` records them.

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

## Dataset tab

Once the VAE has trained, the **Dataset** tab reports on the frames the backend trained it on (captured from `prepare_data`, with the duplicate of the sample that `run_server` appends left out):

- **How much each attribute is encoded.** A ridge regression from one latent frame to each attribute, scored on clips it didn't see. It reports R², rank correlation, rank correlation within clips (what matters for editing one sound) and between clip averages. The same predictors are also scored on the latent after the VAE round trip, to show whether the VAE keeps each attribute. A third pair of columns predicts from the VAE's own code; that one is optimistic, because the VAE was trained on every clip's labels.
- **Where each attribute varies:** the share of its variance inside clips versus between them.
- **How the attributes move together:** correlation over all frames and over clip averages. Cells beyond the p < 0.05 level for that number of clips are outlined.

## Model tab

The **Model** tab moves each VAE dimension from −2 to +2 times its spread, from 400 frames across the folder, applies the edit by delta decoding as the app does, and follows it into the generative latent. Nothing is decoded to audio: the attributes of the result are re-measured with a ridge regression from latent frame to attribute, fitted on the folder (the Dataset tab shows how far it can be trusted).

- **What each slider does:** change in every attribute over the slider's travel, with gain, selectivity and monotonicity. These are latent traversals as used to evaluate attribute-regularised VAEs (Pati & Lerch; Esling et al.).
- **Response curves** for each slider.
- **Path through the generative latent:** speed (magnification along the slider, after Arvanitidis et al.), path length over straight-line distance (curvature, after Shao et al.), end-to-end turn, unevenness of step size (after perceptual path length, Karras et al.), and distance to the nearest real frame at each end (k-NN distance, Sun et al.).
- **Landscape:** the folder's frames in an attribute plane or latent PCA, with one slider's paths from moments of the sample (after the surface and density maps of Bryan-Kinns et al.).
- **Disentanglement scores** of the VAE code: SCC, MIG, SAP and DCI.

The tab lists full references. Where a measure is adapted rather than taken as published, it says so.

The numbers behind both tabs are saved to `analysis.json` in the run folder.

## Each run

Each run creates `testbed/runs/<timestamp>_<name>/` containing:

- `config.yaml`: a copy of the config used
- `losses.json`: per-epoch losses and loss weights
- `analysis.json`: the numbers behind the Dataset and Model tabs
- `vae.pt`: the state dict, class, dimensions and history
- `audio/`: `original.wav`, `vae_recon.wav`, and `edit_###.wav` with its edited latent JSON and the backend's spectrogram PNGs

Features are cached by the backend, as `.pkl` files in the sample folder, the same way the app caches them.

## Feature-cache warning

After `request_load_folder`, the testbed reads the backend's feature cache. It shows a warning if the reconstructions the attributes were computed from are under half the input length.

This used to happen with Stable Audio. `batch_compute_features` decodes `enc`, shaped (1, C, T), with `Model.decode`, which tried `enc.T` first. The transposed shape is (T, C, 1), and the Stable Audio decoder accepts it, so it decoded T one-frame clips. Their average, 2,048 samples long, then became `recon_audio`. `Model.decode` now uses a (1, C, T) latent as it is.

Caches made before that fix still hold the short reconstructions. Delete the `*_preprocessed_sound_data*.pkl` files in any sample folder you loaded before the fix; the warning flags any you miss.
