"""VAE testbed: drive the MALT backend with the same messages the Max frontend sends,
and show what happens in a browser.

Point testbed/config.yaml at a folder, then from the repo root:

    .venv/bin/python -m testbed.run [path/to/config.yaml]

Sequence (each step is a message dict handed to backend/run_server.py's handlers,
exactly as its HTTP server would receive it):

    load_model -> set_regularisation -> request_load_folder -> request_retrain_vae
    -> request_latent (first sample) -> request_audio (unedited, then every edit)

Nothing in backend/ or frontend/ is modified. While training, the testbed temporarily
wraps a few backend functions in memory to read the losses and to swap the VAE class.
"""
import os

os.environ.setdefault('MPLBACKEND', 'Agg')  # backend saves spectrograms off the main thread

import copy  # noqa: E402
import importlib  # noqa: E402
import json  # noqa: E402
import pickle  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
import webbrowser  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

TESTBED_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTBED_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import librosa as li  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402

import backend.run_server as rs  # noqa: E402  (importing does not start its HTTP server)
from backend.timbre_VAE import features as features_mod  # noqa: E402
from backend.timbre_VAE import vae_train  # noqa: E402
from backend.timbre_VAE.plotting import save_spectrogram  # noqa: E402

AUDIO_EXTS = ('.wav', '.aif', '.mp3', '.ogg')  # same filter as backend/run_server.py
LOSS_KEYS = ('total', 'recon', 'kl', 'attr')    # order of train_vae's loss_lists

DEFAULTS = {
    'name': 'run', 'folder': None, 'sample': None, 'feature_type': 'pca',
    'generative_model': 'data/models/StableAudio/stable-ae-float32-torch25x.ts',
    'vae': {'class': 'backend.timbre_VAE.vae_train.VAE', 'kwargs': {}},
    'train': {'num_epochs': 4000, 'batch_size': 1024, 'learning_rate': 0.01,
              'alpha_max': 10.0, 'beta_max': 0.1, 'theta_max': 10.0},
    'decode': {'delta': True, 'smoothing': 1.5},
    'server': {'port': 8765, 'open_browser': True},
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def resolve_path(p):
    if p is None:
        return None
    p = Path(os.path.expanduser(str(p)))
    return p if p.is_absolute() else (REPO_ROOT / p)


def import_class(path):
    module, _, name = path.rpartition('.')
    return getattr(importlib.import_module(module), name)


class BackendError(RuntimeError):
    pass


class StopTraining(Exception):
    pass


# ---------------------------------------------------------------------------
# Shared state (written by the worker thread, read by the web server)
# ---------------------------------------------------------------------------
class State:
    def __init__(self):
        self.stage, self.message, self.error = 'starting', '', None
        self.epoch = self.epochs = 0
        self.stop_requested = False
        self.history = {'epoch': [], 'loss': {k: [] for k in LOSS_KEYS},
                        'weights': {'alpha': [], 'beta': [], 'theta': []}}
        self.info = {}
        self.sample = {}
        self.messages = []   # recent request/response pairs, for the UI
        self.decode_count = 0

    def set(self, stage, message=''):
        self.stage, self.message = stage, message
        print(f'\n[testbed] {stage}{": " + message if message else ""}')


# ---------------------------------------------------------------------------
# Transport: the backend's message protocol, in process
# ---------------------------------------------------------------------------
class Backend:
    """Hands message dicts to backend/run_server.py's handlers, as SimpleHandler.do_POST does.

    Messages and replies are round-tripped through JSON so they are exactly what HTTP would carry.
    """

    def __init__(self, state):
        self.state = state
        self.lock = threading.Lock()

    def send(self, message, raise_on_error=True):
        message = json.loads(json.dumps(message))
        t0 = time.time()
        with self.lock:
            handler = rs.handlers.get(message['type'])
            reply = handler(message) if handler else {'type': 'error',
                                                      'content': f"Unknown message type: {message['type']}"}
            rs.request_logger.log(request=message, response=reply)
        reply = json.loads(json.dumps(reply))
        content = message.get('content')
        self.state.messages.append({
            'time': datetime.now().strftime('%H:%M:%S'), 'type': message['type'], 'reply': reply.get('type'),
            'detail': content if isinstance(content, str) else ('{…}' if content is not None else ''),
            'note': reply.get('content') if isinstance(reply.get('content'), str) else '',
            'ms': int(1000 * (time.time() - t0))})
        del self.state.messages[:-50]
        if raise_on_error and reply.get('type') in ('error', 'warning'):
            raise BackendError(f"{message['type']} → {reply.get('type')}: {reply.get('content')}")
        return reply


# ---------------------------------------------------------------------------
# Training hooks: read losses live and swap the VAE class, without editing backend files
# ---------------------------------------------------------------------------
class TrainingHooks:
    def __init__(self, tb):
        self.tb, self.state, self.cfg = tb, tb.state, tb.cfg
        self.cls_path = self.cfg['vae']['class']
        self.cls = import_class(self.cls_path)
        self.kwargs = self.cfg['vae']['kwargs'] or {}
        self._reset_epoch()
        self.cur_epoch = 0

    def __enter__(self):
        self.orig = (rs.train_vae, rs.VAE, vae_train.vae_loss, vae_train.increment_progress_bar)
        rs.train_vae = self.train
        rs.VAE = self.make_vae
        vae_train.vae_loss = self.loss
        vae_train.increment_progress_bar = self.progress
        return self

    def __exit__(self, *exc):
        rs.train_vae, rs.VAE, vae_train.vae_loss, vae_train.increment_progress_bar = self.orig

    # rs.VAE(input_dim=..., latent_dim=...) is called inside handle_request_retrain_vae
    def make_vae(self, input_dim, latent_dim):
        self.vae = self.cls(input_dim=input_dim, latent_dim=latent_dim, **self.kwargs)
        self.dims = (int(input_dim), int(latent_dim))
        self.state.info.update(input_dim=int(input_dim), latent_dim=int(latent_dim),
                               n_params=int(sum(p.numel() for p in self.vae.parameters())))
        return self.vae

    # rs.train_vae(vae, latent_data, metadata_vectors, num_epochs=4000, batch_size=1024, learning_rate=1e-2, ...)
    def train(self, vae, latent_data, metadata_vectors, **kw):
        overrides = {k: v for k, v in (self.cfg['train'] or {}).items() if v is not None}
        kw.update(overrides)
        self.state.epochs = int(kw.get('num_epochs', 4000))
        self.state.info['frames'] = int(latent_data.shape[0])
        self.state.info['train_args'] = {k: v for k, v in kw.items() if k != 'plot_loss'}
        self.state.set('training', f'{latent_data.shape[0]:,} frames')
        h = self.state.history
        try:
            vae, loss_lists, labels = self.orig[0](vae, latent_data, metadata_vectors, **kw)
            self._close_epoch()
            for k, values in zip(LOSS_KEYS, loss_lists):  # the backend's own per-epoch numbers
                h['loss'][k] = list(map(float, values))
        except StopTraining:
            self._close_epoch()
            self.state.message = f'stopped at epoch {self.cur_epoch - 1}'
            loss_lists = [h['loss'][k] for k in LOSS_KEYS]
            labels = ['Total Loss', 'Recon Loss', 'KL Loss', 'Attr Loss']
        self.tb.save_run(vae, self)
        return vae, loss_lists, labels

    # called by train_vae at the start of every epoch
    def progress(self, current, total, description=''):
        self._close_epoch()
        if self.state.stop_requested and self.state.history['epoch']:
            raise StopTraining()
        self.cur_epoch = current
        self.orig[3](current, total, description=description)

    # called by train_vae for every batch: vae_loss(recon, x, mu, logvar, x_attr, vae, alpha, beta, theta)
    def loss(self, *args, **kw):
        res = self.orig[2](*args, **kw)
        total, (recon, kl, attr) = res
        self.sums['total'] += total.item()
        self.sums['recon'] += recon.item()
        self.sums['kl'] += kl.item()
        self.sums['attr'] += attr.item()
        self.nb += 1
        names = ('alpha', 'beta', 'theta')
        self.w = {n: float(args[6 + i]) if len(args) > 6 + i else float(kw.get(n, 0)) for i, n in enumerate(names)}
        return res

    def _reset_epoch(self):
        self.sums = {k: 0.0 for k in LOSS_KEYS}
        self.nb = 0
        self.w = {}

    def _close_epoch(self):
        if not self.nb:
            return
        h = self.state.history
        for k in LOSS_KEYS:  # means over the epoch's batches, as train_vae records them
            h['loss'][k].append(self.sums[k] / self.nb)
        for k in h['weights']:
            h['weights'][k].append(self.w.get(k, 0.0))
        h['epoch'].append(self.cur_epoch)
        self.state.epoch = self.cur_epoch
        self._reset_epoch()


# ---------------------------------------------------------------------------
# The testbed run
# ---------------------------------------------------------------------------
class Testbed:
    def __init__(self, cfg, config_path, state):
        self.cfg, self.state = cfg, state
        self.config_path = Path(config_path)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.run_dir = TESTBED_DIR / 'runs' / f'{stamp}_{cfg["name"]}'
        self.audio_dir = self.run_dir / 'audio'
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.config_path, self.run_dir / 'config.yaml')
        self.backend = Backend(state)
        self.latent_json = None
        state.info.update(name=cfg['name'], run_dir=str(self.run_dir.relative_to(REPO_ROOT)))

    def run(self):
        try:
            self._check_config()
            send = self.backend.send

            model_path = resolve_path(self.cfg['generative_model'])
            self.state.set('loading generative model', model_path.name)
            send({'type': 'load_model', 'content': str(model_path)})
            dec = self.cfg['decode'] or {}
            rs.gen_model.delta_decoding = bool(dec.get('delta', True))
            rs.gen_model.delta_smoothing = float(dec.get('smoothing') or 0)
            self.state.info['decode'] = (f"delta, smoothing {rs.gen_model.delta_smoothing:g}"
                                         if rs.gen_model.delta_decoding else 'full VAE decode')

            send({'type': 'set_regularisation', 'content': self.cfg['feature_type']})

            self.state.set('computing features', f'{len(self.files)} files (cached in the folder after the first run)')
            with self._feature_progress():
                send({'type': 'request_load_folder', 'content': str(self.folder)})
            self._check_feature_cache()

            with TrainingHooks(self):
                send({'type': 'request_retrain_vae'})
            self._save_stats()

            self.state.set('encoding sample', self.sample_path.name)
            reply = send({'type': 'request_latent', 'content': str(self.sample_path)})
            self.latent_json = reply['content']
            self._publish_sample()

            self.state.set('decoding unedited sample')
            # Always the full VAE decode here, so this player shows the VAE's own reconstruction
            # (with delta decoding on, an unedited decode is just the generative reconstruction).
            delta = rs.gen_model.delta_decoding
            rs.gen_model.delta_decoding = False
            try:
                url, spec = self.decode(self.latent_json, 'vae_recon')
            finally:
                rs.gen_model.delta_decoding = delta
            self.state.sample['audio']['vae_recon'] = url
            self.state.sample['spectrogram']['vae_recon'] = spec
            self.state.set('ready', 'draw on a trajectory to edit it')
        except Exception as e:
            self.state.error = traceback.format_exc()
            self.state.set('error', str(e))
            print(self.state.error)

    def _check_config(self):
        folder = resolve_path(self.cfg['folder'])
        if folder is None or not folder.is_dir():
            raise ValueError(f'folder not found: {folder}. Set `folder:` in {self.config_path.name} '
                             f'or run `make testbed FOLDER=/path/to/samples`')
        self.folder = folder
        self.files = sorted(f for f in os.listdir(folder) if f.endswith(AUDIO_EXTS))
        if not self.files:
            raise ValueError(f'no audio files ({", ".join(AUDIO_EXTS)}) in {folder}')
        if self.cfg['sample']:
            sp = Path(os.path.expanduser(str(self.cfg['sample'])))
            if not sp.is_absolute():
                sp = folder / sp if (folder / sp).exists() else resolve_path(sp)
            if not sp.is_file():
                raise ValueError(f'sample not found: {sp}')
            self.sample_path = sp
        else:
            self.sample_path = folder / self.files[0]
        self.state.info.update(folder=str(folder), n_files=len(self.files), sample=self.sample_path.name,
                               feature_type=self.cfg['feature_type'], vae_class=self.cfg['vae']['class'],
                               generative_model=Path(self.cfg['generative_model']).name)

    def _feature_progress(self):
        """Mirror the backend's per-file progress bar into the UI."""
        state = self.state

        class _Ctx:
            def __enter__(self_):
                self_.orig = features_mod.increment_progress_bar

                def progress(cur, total, description=''):
                    state.message = f'{description.lower()} {cur}/{total}'
                    self_.orig(cur, total, description=description)
                features_mod.increment_progress_bar = progress

            def __exit__(self_, *exc):
                features_mod.increment_progress_bar = self_.orig
        return _Ctx()

    def _check_feature_cache(self):
        """Warn if the reconstructions the attributes were computed from look truncated."""
        try:
            path = (rs.feature_paths or {}).get('raw_features')
            if not path or not os.path.exists(path):
                return
            with open(path, 'rb') as f:
                items = pickle.load(f)
            short = [d['filename'] for d in items if d.get('recon_audio') is not None
                     and len(d['recon_audio']) < 0.5 * len(d['raw_audio'])]
            if short:
                warn = (f'{len(short)}/{len(items)} reconstructions used for feature extraction are under half '
                        f'the input length (e.g. {short[0]}), so the attribute targets may not describe the sounds.')
                self.state.info['warning'] = warn
                print('[testbed] WARNING', warn)
        except Exception as e:  # diagnostic only
            print(f'[testbed] feature cache check skipped: {e}')

    def _publish_sample(self):
        lj = self.latent_json
        items = sorted(lj['vector'].items(), key=lambda kv: int(kv[0]))
        keys = lj.get('metadata_keys') or []
        labels = [keys[i] if i < len(keys) else v['label'] for i, (_, v) in enumerate(items)]
        y, sr = li.load(str(self.sample_path), sr=44100)  # for the browser player (it can't play .aif)
        orig = self.audio_dir / 'original.wav'
        sf.write(orig, y, sr)
        spec = self._spectrogram(orig)
        self.state.sample = {
            'filename': self.sample_path.name, 'duration': len(y) / sr,
            'labels': labels, 'n_attr': len(keys), 'data': [v['data'] for _, v in items],
            'bias': lj.get('bias'), 'scale': lj.get('scale'),
            'audio': {'original': f'/audio/original.wav?v={time.time():.0f}'},
            'spectrogram': {'original': spec},
        }

    def _spectrogram(self, wav_path):
        try:
            png = Path(save_spectrogram(str(wav_path)))
            return f'/audio/{png.name}?v={time.time():.0f}'
        except Exception as e:
            print(f'[testbed] spectrogram skipped: {e}')
            return None

    def decode(self, latent_json, name):
        """request_audio -> copy the backend's temp wav (+ its spectrogram) into the run folder."""
        reply = self.backend.send({'type': 'request_audio', 'content': latent_json})
        src = Path(reply['audio_path'])
        dst = self.audio_dir / f'{name}.wav'
        shutil.copy(src, dst)
        spec_src = src.with_name(src.stem + '_spectrogram.png')
        spec = None
        if spec_src.exists():
            shutil.copy(spec_src, self.audio_dir / f'{name}_spectrogram.png')
            spec = f'/audio/{name}_spectrogram.png?v={time.time():.0f}'
        return f'/audio/{dst.name}?v={time.time():.0f}', spec

    def decode_edit(self, data):
        if self.latent_json is None:
            raise BackendError('no sample encoded yet')
        lj = copy.deepcopy(self.latent_json)
        items = sorted(lj['vector'].items(), key=lambda kv: int(kv[0]))
        if len(data) != len(items) or any(len(d) != len(v['data']) for d, (_, v) in zip(data, items)):
            raise BackendError('edited trajectories do not match the encoded shape')
        for d, (_, v) in zip(data, items):
            v['data'] = [float(x) for x in d]
        self.state.decode_count += 1
        name = f'edit_{self.state.decode_count:03d}'
        url, spec = self.decode(lj, name)
        with open(self.audio_dir / f'{name}.json', 'w') as f:
            json.dump(lj, f)
        return {'audio': url, 'spectrogram': spec, 'name': name}

    def _save_stats(self):
        """Add the latent mean/std the backend now keeps (Model.control_stats) to the run's vae.pt."""
        path = self.run_dir / 'vae.pt'
        stats = getattr(rs.gen_model, 'control_stats', None)
        if stats is None or not path.exists():
            return
        ck = torch.load(path, weights_only=False)
        ck['latent_mean'], ck['latent_std'] = stats
        torch.save(ck, path)

    def save_run(self, vae, hooks):
        h = self.state.history
        with open(self.run_dir / 'losses.json', 'w') as f:
            json.dump(h, f)
        try:
            torch.save({'state_dict': vae.state_dict(), 'class': hooks.cls_path, 'kwargs': hooks.kwargs,
                        'input_dim': hooks.dims[0], 'latent_dim': hooks.dims[1],
                        'history': h, 'config': self.cfg}, self.run_dir / 'vae.pt')
        except Exception as e:
            print(f'[testbed] could not save vae.pt: {e}')


def load_config(path):
    with open(path) as f:
        return _merge(DEFAULTS, yaml.safe_load(f) or {})


def replace_previous(port):
    """If an earlier testbed is still serving on `port`, ask it to exit so this run takes over.

    Returns True if one was replaced (its open browser tab reloads onto this run by itself).
    """
    import urllib.request
    base = f'http://127.0.0.1:{port}'
    try:
        with urllib.request.urlopen(base + '/api/status', timeout=1) as r:
            if 'stage' not in json.load(r):
                return False
    except Exception:
        return False
    print(f'[testbed] stopping the testbed already running on :{port}')
    try:
        urllib.request.urlopen(urllib.request.Request(base + '/api/shutdown', data=b'{}', method='POST'), timeout=2)
    except Exception:
        pass
    for _ in range(50):
        time.sleep(0.1)
        try:
            urllib.request.urlopen(base + '/api/status', timeout=0.3)
        except Exception:
            return True
    return True


def main():
    import argparse
    ap = argparse.ArgumentParser(description='VAE testbed: train on a folder and edit a sample in the browser.')
    ap.add_argument('config', nargs='?', default=str(TESTBED_DIR / 'config.yaml'), help='config yaml')
    ap.add_argument('--folder', help='overrides `folder:` in the config')
    args = ap.parse_args()

    config_path = Path(args.config)
    if not config_path.exists() and (REPO_ROOT / config_path).exists():
        config_path = REPO_ROOT / config_path
    cfg = load_config(config_path)
    if args.folder:
        cfg['folder'] = args.folder
    state = State()

    replaced = replace_previous(cfg['server']['port'])
    tb = Testbed(cfg, config_path, state)

    from testbed.server import make_server
    server, port = make_server(tb, state, cfg['server']['port'])
    url = f'http://127.0.0.1:{port}/'
    print(f'\n[testbed] UI at {url}   (run folder: {tb.run_dir.relative_to(REPO_ROOT)})\n')
    threading.Thread(target=tb.run, daemon=True).start()
    if cfg['server']['open_browser'] and not (replaced and port == cfg['server']['port']):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[testbed] bye')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
