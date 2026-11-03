"""Check what the sliders do to real decoded audio, every so often during training.

A few short excerpts of the folder (the probes) are edited the way the app edits them: one attribute
dim of the control VAE's code is moved up and down, the change is delta-decoded into the generative
model's latent and decoded to audio by the generative model. The attributes are then measured on that
audio with the same feature pipeline the VAE's targets came from. The result says how much each
slider moves its own attribute (gain) and the others (leak), in std units of the folder.

train_vae calls it with (vae, epoch) and can keep the weights from the best check.
"""
import time

import numpy as np
import torch
from scipy.ndimage import gaussian_filter1d

from .features import measure_attributes


class DecoderCheck:
    def __init__(self, model, sound_data, metadata_keys, attr_std, latent_mean, latent_std, latent_frames,
                 pca=None, feature_type='raw_features', clips=2, seconds=2.0, shift=1.0, smoothing=1.5):
        self.model, self.keys, self.pca, self.feature_type = model, list(metadata_keys), pca, feature_type
        self.attr_std = np.asarray(attr_std, dtype=np.float64).reshape(-1)
        self.mean = np.asarray(latent_mean, dtype=np.float32).reshape(1, -1)
        self.std = np.asarray(latent_std, dtype=np.float32).reshape(1, -1)
        self.shift, self.smoothing = float(shift), float(smoothing)
        n = latent_frames.shape[0]
        idx = torch.randperm(n)[:min(n, 2000)]
        self.spread_frames = latent_frames[idx].detach().cpu().float()  # for each dim's spread in the code
        # probes: the middle `seconds` of `clips` different files
        unique, seen = [], set()
        for d in sound_data:
            if d.get('filename') not in seen:
                seen.add(d.get('filename'))
                unique.append(d)
        picks = [unique[i] for i in np.linspace(0, len(unique) - 1, min(clips, len(unique))).astype(int)]
        t0 = time.time()
        self.probes = []
        for d in picks:
            enc = np.asarray(d['encoding'])[0].T.astype(np.float32)          # (frames, channels)
            sr = int(d.get('sr', 44100))
            hop = len(np.asarray(d['raw_audio']).reshape(-1)) / max(1, len(enc))
            m = max(4, int(round(seconds * sr / hop)))
            a = max(0, (len(enc) - m) // 2)
            raw = enc[a:a + m]
            audio = self.model.decode_latent(raw.T[np.newaxis])
            self.probes.append({'file': d.get('filename'), 'raw': raw, 'sr': sr,
                                'base': self.measure(audio, sr)})
        print(f"[check] {len(self.probes)} probe(s) of {seconds:g} s: "
              + ", ".join(p['file'] for p in self.probes) + f" ({time.time() - t0:.1f} s)")

    def measure(self, audio, sr):
        return np.asarray(measure_attributes(audio, sr, self.keys, self.pca, self.feature_type), dtype=np.float64)

    @torch.no_grad()
    def __call__(self, vae, epoch):
        t0 = time.time()
        was_training = vae.training
        vae.eval()
        dev = next(vae.parameters()).device
        n_attr = len(self.keys)
        spread = vae.encode_mu(self.spread_frames.to(dev)).std(0).cpu().numpy()
        moves = np.zeros((len(self.probes), n_attr, n_attr))       # (probe, slider, attribute)
        for p_i, p in enumerate(self.probes):
            x = torch.from_numpy((p['raw'] - self.mean) / self.std).to(dev)
            z0 = vae.encode_mu(x)
            d0 = vae.decode(z0)
            for k in range(n_attr):
                ends = []
                for sign in (-1, 1):
                    z = z0.clone()
                    z[:, k] += sign * self.shift * float(spread[k])
                    change = (vae.decode(z) - d0).cpu().numpy() * self.std
                    if self.smoothing:
                        change = gaussian_filter1d(change, self.smoothing, axis=0)
                    audio = self.model.decode_latent((p['raw'] + change).T[np.newaxis])
                    ends.append((self.measure(audio, p['sr']) - p['base']) / self.attr_std)
                moves[p_i, k] = (ends[1] - ends[0]) / 2             # change per `shift` spreads
        if was_training:
            vae.train()
        m = moves.mean(0)
        gain = np.diag(m)
        leak = (np.abs(m).sum(1) - np.abs(gain)) / max(1, n_attr - 1)
        score = float(np.mean(gain - leak))
        res = {'epoch': int(epoch), 'keys': [str(k) for k in self.keys], 'gain': gain.round(3).tolist(), 'leak': leak.round(3).tolist(),
               'score': round(score, 4), 'seconds': round(time.time() - t0, 1)}
        print(f"[check] epoch {epoch}: gain " + " ".join(f"{g:+.2f}" for g in gain)
              + f" | leak {leak.mean():.2f} | score {score:+.3f} ({res['seconds']} s)")
        return res
