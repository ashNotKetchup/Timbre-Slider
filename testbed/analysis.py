"""Analysis of a trained control VAE on its folder, for the testbed's Dataset tab.

Everything here works on the data the backend trained on (captured from `prepare_data`):
the generative model's latent frames, standardised as the VAE sees them (X), the attribute
values per frame (A, standardised), and which clip each frame came from.
"""
import numpy as np
import torch
from scipy.stats import spearmanr, t as t_dist
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold

MIN_CLIPS_HELDOUT = 2


def _nan(x):
    return None if x is None or not np.isfinite(x) else float(x)


def _round(a, n=4):
    """JSON-friendly copy: floats rounded, NaN -> None."""
    if isinstance(a, dict):
        return {k: _round(v, n) for k, v in a.items()}
    if isinstance(a, (list, tuple)):
        return [_round(v, n) for v in a]
    if isinstance(a, np.ndarray):
        return _round(a.tolist(), n)
    if isinstance(a, (float, np.floating)):
        return None if not np.isfinite(a) else round(float(a), n)
    if isinstance(a, (np.integer,)):
        return int(a)
    return a


def _spearman(a, b):
    if len(a) < 3 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return np.nan
    return spearmanr(a, b)[0]


class FolderData:
    """The frames the VAE was trained on, de-duplicated (run_server appends the sample a second time)."""

    def __init__(self, sound_data, prepared):
        latent_data, metadata_vectors, metadata_keys = prepared[0], prepared[1], prepared[2]
        clip_ids = np.asarray(prepared[5])
        X = latent_data.detach().cpu().numpy() if torch.is_tensor(latent_data) else np.asarray(latent_data)
        A = np.concatenate([np.asarray(m) for m in metadata_vectors], axis=0)
        names = [d.get('filename', f'clip {i}') for i, d in enumerate(sound_data)]
        keep_clips, seen = [], set()
        for i, n in enumerate(names):
            if n not in seen:
                seen.add(n)
                keep_clips.append(i)
        mask = np.isin(clip_ids, keep_clips)
        remap = {c: k for k, c in enumerate(keep_clips)}
        self.X = X[mask].astype(np.float32)
        self.A = A[mask].astype(np.float64)
        self.clip = np.array([remap[c] for c in clip_ids[mask]], dtype=np.int32)
        self.files = [names[i] for i in keep_clips]
        self.keys = [str(k) for k in metadata_keys]
        self.labels = [k.replace('_', ' ').title() for k in self.keys]
        self.n_dropped = len(names) - len(keep_clips)
        # index of each frame within its clip
        self.pos = np.zeros(len(self.clip), dtype=np.int32)
        for c in range(len(self.files)):
            idx = np.where(self.clip == c)[0]
            self.pos[idx] = np.arange(len(idx))
        self.n_frames = [int((self.clip == c).sum()) for c in range(len(self.files))]

    def clip_index(self, filename):
        return self.files.index(filename) if filename in self.files else None


class Analysis:
    def __init__(self, data: FolderData, vae, latent_mean, latent_std, sample_name=None):
        self.d = data
        self.vae = vae.cpu().eval()
        self.mean = np.asarray(latent_mean, dtype=np.float32).reshape(1, -1)
        self.std = np.asarray(latent_std, dtype=np.float32).reshape(1, -1)
        self.sample_clip = data.clip_index(sample_name)
        X, A = data.X, data.A
        self.J = A.shape[1]
        with torch.no_grad():
            self.Z = self.vae.encode_mu(torch.from_numpy(X)).numpy()
        self.K = self.Z.shape[1]
        self._cache = {}

    # ------------------------------------------------------------------ helpers
    def dec(self, z):
        with torch.no_grad():
            return self.vae.decode(torch.from_numpy(np.ascontiguousarray(z, dtype=np.float32))).numpy()

    def _groups(self):
        n = len(self.d.files)
        return GroupKFold(min(5, n)) if n >= MIN_CLIPS_HELDOUT else None

    def _heldout(self, F, extra=None):
        """Held-out-clip predictions of the attributes from features F (and, optionally, the same
        fitted models applied to `extra`, e.g. the VAE's reconstruction of those frames)."""
        A, clip = self.d.A, self.d.clip
        gkf = self._groups()
        if gkf is None:
            return None, None
        p = np.zeros_like(A)
        pe = np.zeros_like(A) if extra is not None else None
        for tr, te in gkf.split(F, A, clip):
            m = Ridge(1.0).fit(F[tr], A[tr])
            p[te] = m.predict(F[te])
            if extra is not None:
                pe[te] = m.predict(extra[te])
        return p, pe

    def _scores(self, pred):
        A, clip = self.d.A, self.d.clip
        out = []
        for j in range(self.J):
            if pred is None:
                out.append({'r2': None, 'spearman': None, 'within': None, 'between': None})
                continue
            within = [_spearman(A[clip == c, j], pred[clip == c, j]) for c in range(len(self.d.files))
                      if (clip == c).sum() >= 10]
            cm = np.array([A[clip == c, j].mean() for c in range(len(self.d.files))])
            pm = np.array([pred[clip == c, j].mean() for c in range(len(self.d.files))])
            out.append({'r2': _nan(r2_score(A[:, j], pred[:, j])),
                        'spearman': _nan(_spearman(A[:, j], pred[:, j])),
                        'within': _nan(np.nanmedian(within)) if np.isfinite(within).any() else None,
                        'between': _nan(_spearman(cm, pm)) if len(cm) >= 4 else None})
        return out

    # ------------------------------------------------------------------ Dataset tab
    def dataset(self):
        if 'dataset' in self._cache:
            return self._cache['dataset']
        d, X, A, clip = self.d, self.d.X, self.d.A, self.d.clip
        n = len(d.files)
        Xr = self.dec(self.Z)                                   # full VAE round trip, standardised units
        p_lat, p_rt = self._heldout(X, Xr)
        p_code, _ = self._heldout(self.Z)
        # share of each attribute's variance that is within clips (rest = between clips)
        tot = A.var(0) * len(A)
        within_ss = sum(((A[clip == c] - A[clip == c].mean(0)) ** 2).sum(0) for c in range(n))
        within_share = within_ss / np.maximum(tot, 1e-12)
        cm = np.array([A[clip == c].mean(0) for c in range(n)])
        r_crit = None
        if n >= 4:
            tc = t_dist.ppf(0.975, n - 2)
            r_crit = float(tc / np.sqrt(n - 2 + tc ** 2))
        res = {
            'labels': d.labels, 'files': d.files, 'n_clips': n, 'n_frames': int(len(X)),
            'frames_per_clip': d.n_frames, 'n_dropped': d.n_dropped, 'latent_dim': int(X.shape[1]),
            'readable': self._scores(p_lat),               # from the generative model's latent
            'after_vae': self._scores(p_rt),               # same predictors, on the VAE's reconstruction
            'from_code': self._scores(p_code),             # from the VAE's own code (trained on these labels)
            'within_share': within_share,
            'range_within': [float(np.median([A[clip == c, j].std() for c in range(n)])) for j in range(self.J)],
            'corr_frames': np.corrcoef(A.T) if self.J > 1 else [[1.0]],
            'corr_clips': np.corrcoef(cm.T) if (self.J > 1 and n >= 3) else None,
            'r_crit': r_crit,
            'recon_r2': float(1 - ((Xr - X) ** 2).sum() / ((X - X.mean(0)) ** 2).sum()),
        }
        self._cache['dataset'] = _round(res)
        return self._cache['dataset']
