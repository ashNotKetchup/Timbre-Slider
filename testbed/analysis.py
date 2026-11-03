"""Analysis of a trained control VAE on its folder, for the testbed's Dataset and Model tabs.

Everything here works on the data the backend trained on (captured from `prepare_data`):
the generative model's latent frames, standardised as the VAE sees them (X), the attribute
values per frame (A, standardised), and which clip each frame came from.

"Re-measuring" an attribute on an edited latent uses a linear predictor from latent frame to
attribute, fitted on the folder. That stands in for decoding to audio and running the feature
extractor, which is far too slow to do for every frame. How far that stand-in can be trusted is
itself reported in the Dataset tab (held-out R² and rank correlation).
"""
import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d
from scipy.stats import spearmanr, t as t_dist
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mutual_info_score, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors

SELF_WINDOW = 5      # frames either side of a frame that count as "the same moment" for distance-to-data
N_STEPS = 9          # points along each slider traversal
MAX_SRC = 400        # frames used for traversal statistics
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
        self.predictor = Ridge(1.0).fit(X, A)        # latent frame -> attributes, the re-measuring stand-in
        self.nn = NearestNeighbors(n_neighbors=2 * SELF_WINDOW + 3).fit(X)
        rng = np.random.default_rng(0)
        probe = rng.choice(len(X), min(800, len(X)), replace=False)
        self.base_dist = float(np.median(self.dist_to_data(X[probe], data.clip[probe], data.pos[probe], scale=False)))
        self.z_std = self.Z.std(0) + 1e-8
        self._cache = {}

    # ------------------------------------------------------------------ helpers
    def dec(self, z):
        with torch.no_grad():
            return self.vae.decode(torch.from_numpy(np.ascontiguousarray(z, dtype=np.float32))).numpy()

    def dist_to_data(self, Y, src_clip=None, src_pos=None, scale=True):
        """Distance from each row of Y to the nearest folder frame, ignoring the source frame's own
        moment (same clip, within SELF_WINDOW frames). In units of the typical gap between real frames
        when scale=True, so 1.0 means "as close as real frames are to each other"."""
        d, i = self.nn.kneighbors(np.asarray(Y, dtype=np.float32))
        if src_clip is not None:
            same = (self.d.clip[i] == np.asarray(src_clip)[:, None]) & \
                   (np.abs(self.d.pos[i] - np.asarray(src_pos)[:, None]) <= SELF_WINDOW)
            d = np.where(same, np.inf, d)
            out = d.min(1)
            # all neighbours were the frame's own moment: fall back to a direct search
            bad = ~np.isfinite(out)
            if bad.any():
                for r in np.where(bad)[0]:
                    ok = ~((self.d.clip == src_clip[r]) & (np.abs(self.d.pos - src_pos[r]) <= SELF_WINDOW))
                    out[r] = np.sqrt(((self.d.X[ok] - Y[r]) ** 2).sum(1)).min()
        else:
            out = d[:, 0]
        return out / self.base_dist if scale else out

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

    # ------------------------------------------------------------------ Model tab
    def disentanglement(self):
        """Standard scores of the VAE code against the attributes (all frames; the VAE was trained on them)."""
        Z, A = self.Z, self.d.A
        K, J = self.K, self.J
        # SCC (Pati & Lerch): best |Spearman| between the attribute and any single dim
        S = np.array([[abs(_spearman(Z[:, k], A[:, j])) for j in range(J)] for k in range(K)])
        # SAP (Kumar et al. 2018), continuous: R² of a 1-D linear fit per dim; gap between the top two
        R2 = np.array([[np.corrcoef(Z[:, k], A[:, j])[0, 1] ** 2 for j in range(J)] for k in range(K)])
        # MIG (Chen et al. 2018): MI on 20-bin histograms, gap between top two dims / H(attribute)
        def bins(v):
            edges = np.histogram_bin_edges(v, 20)
            return np.digitize(v, edges[1:-1])
        Zb = [bins(Z[:, k]) for k in range(K)]
        Ab = [bins(A[:, j]) for j in range(J)]
        MI = np.array([[mutual_info_score(Ab[j], Zb[k]) for j in range(J)] for k in range(K)])
        H = np.array([mutual_info_score(Ab[j], Ab[j]) for j in range(J)])
        # DCI (Eastwood & Williams 2018) with linear-regression importances on standardised codes
        Zs = (Z - Z.mean(0)) / (Z.std(0) + 1e-8)
        W = np.abs(LinearRegression().fit(Zs, A).coef_.T)         # (K, J)
        Pk = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
        D_k = 1 + (Pk * np.log(np.maximum(Pk, 1e-12))).sum(1) / np.log(J) if J > 1 else np.ones(K)
        rho = W.sum(1) / max(W.sum(), 1e-12)
        Pj = W / np.maximum(W.sum(0, keepdims=True), 1e-12)
        C_j = 1 + (Pj * np.log(np.maximum(Pj, 1e-12))).sum(0) / np.log(K)
        p_code, _ = self._heldout(Z)
        info = [r2_score(A[:, j], p_code[:, j]) if p_code is not None else np.nan for j in range(J)]
        per_attr = []
        for j in range(J):
            s2 = np.sort(R2[:, j])[::-1]
            m2 = np.sort(MI[:, j])[::-1]
            per_attr.append({'scc': S[:, j].max(), 'scc_dim': int(S[:, j].argmax()),
                             'sap': s2[0] - s2[1], 'mig': (m2[0] - m2[1]) / max(H[j], 1e-12),
                             'completeness': C_j[j], 'informativeness': info[j]})
        return {'per_attr': per_attr, 'importance': W, 'disentanglement_per_dim': D_k, 'rho': rho,
                'overall': {'scc': float(np.mean(S.max(0))), 'sap': float(np.mean([p['sap'] for p in per_attr])),
                            'mig': float(np.mean([p['mig'] for p in per_attr])),
                            'disentanglement': float((rho * D_k).sum()), 'completeness': float(np.mean(C_j)),
                            'informativeness': float(np.nanmean(info)) if np.isfinite(info).any() else None}}

    def traversals(self):
        """Move each dim from -2 to +2 of its spread, from many frames, and follow the edit through
        delta decoding into the generative latent: what the attributes do, and the path's shape."""
        X, Z, clip, pos = self.d.X, self.Z, self.d.clip, self.d.pos
        rng = np.random.default_rng(1)
        src = rng.choice(len(X), min(MAX_SRC, len(X)), replace=False)
        z0, x0 = Z[src], X[src]
        d0 = self.dec(z0)
        p0 = self.predictor.predict(x0)
        sliders = []
        for k in range(self.K):
            r = 2 * self.z_std[k]
            ts = np.linspace(-r, r, N_STEPS)
            P = np.stack([x0 + self.dec(z0 + np.eye(self.K)[k] * t) - d0 for t in ts])  # (T, n, D)
            pred = np.stack([self.predictor.predict(p) for p in P]) - p0                  # (T, n, J)
            curves = np.median(pred, axis=1)                                              # (T, J)
            resp = curves[-1] - curves[0]
            target = k if k < self.J else int(np.argmax(np.abs(resp)))
            mono = np.nanmedian([_spearman(ts, pred[:, i, target]) for i in range(len(src))])
            steps = np.linalg.norm(np.diff(P, axis=0), axis=2)                           # (T-1, n)
            length = steps.sum(0)
            chord = np.linalg.norm(P[-1] - P[0], axis=1)
            first, last = P[1] - P[0], P[-1] - P[-2]
            cosb = (first * last).sum(1) / (np.linalg.norm(first, axis=1) * np.linalg.norm(last, axis=1) + 1e-12)
            dist = [np.median(self.dist_to_data(P[i], clip[src], pos[src])) for i in (0, N_STEPS // 2, N_STEPS - 1)]
            sel = abs(resp[k]) / max(np.abs(resp).sum(), 1e-12) if k < self.J else None
            sliders.append({
                'range': float(r), 'ts': ts / r, 'curves': curves, 'response': resp, 'target': target,
                'gain': resp[target], 'selectivity': sel, 'monotonic': mono,
                'speed': float(np.median(length / (2 * r))),
                'length': float(np.median(length)), 'tortuosity': float(np.median(length / np.maximum(chord, 1e-9))),
                'bend': float(np.median(cosb)), 'unevenness': float(np.median(steps.std(0) / np.maximum(steps.mean(0), 1e-12))),
                'dist': dist,
            })
        return sliders

    def landscape(self):
        """The folder's frames in 2-D, plus each slider's paths from moments of the sample. Two views:
        PCA of the generative latent, and the attribute plane (attributes as the predictor reads them,
        for the frames and the paths alike, so both are placed by the same rule)."""
        X, A, clip = self.d.X, self.d.A, self.d.clip
        pca = PCA(2).fit(X)
        rng = np.random.default_rng(2)
        pts = rng.choice(len(X), min(2500, len(X)), replace=False)
        sc = self.sample_clip if self.sample_clip is not None else 0
        sidx = np.where(clip == sc)[0]
        picks = sidx[np.linspace(0, len(sidx) - 1, min(10, len(sidx))).astype(int)]
        z0, x0 = self.Z[picks], X[picks]
        d0 = self.dec(z0)
        paths_pca, paths_attr = [], []
        for k in range(self.K):
            r = 2 * self.z_std[k]
            P = np.stack([x0 + self.dec(z0 + np.eye(self.K)[k] * t) - d0 for t in np.linspace(-r, r, N_STEPS)])
            paths_pca.append(np.stack([pca.transform(p) for p in P], axis=1))           # (n_frames, T, 2)
            paths_attr.append(np.stack([self.predictor.predict(p) for p in P], axis=1))  # (n_frames, T, J)
        smooth = lambda v: gaussian_filter1d(v, 3, axis=0)   # the sample's track, smoothed for display
        return {'pca': pca.transform(X[pts]), 'pred': self.predictor.predict(X[pts]), 'attrs': A[pts], 'clip': clip[pts],
                'sample_pca': smooth(pca.transform(X[sidx])), 'sample_pred': smooth(self.predictor.predict(X[sidx])),
                'paths_pca': paths_pca, 'paths_attr': paths_attr,
                'explained': pca.explained_variance_ratio_, 'sample_clip': sc}

    def model(self):
        if 'model' not in self._cache:
            K, J = self.K, self.J
            labels = self.d.labels + [f'Dimension {k + 1}' for k in range(J, K)]
            self._cache['model'] = _round({
                'slider_labels': labels[:K], 'attr_labels': self.d.labels, 'n_attr': J,
                'base_dist': self.base_dist, 'disentanglement': self.disentanglement(),
                'sliders': self.traversals(), 'landscape': self.landscape(), 'files': self.d.files,
            })
        return self._cache['model']
