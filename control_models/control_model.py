import os
import torch
import numpy as np
from timbre_VAE.vae_train import VAE

class ControlModel:
    """
    Loads a VAE from a .pt file and exposes encode/decode methods for latent control.
    """
    def __init__(self, vae_path, input_dim=None, latent_dim=None, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.vae_path = vae_path
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.model = None
        self._load_vae()

    def _load_vae(self):
        if not os.path.exists(self.vae_path):
            raise FileNotFoundError(f"VAE file not found: {self.vae_path}")
        # If input_dim/latent_dim not provided, try to infer from checkpoint
        checkpoint = torch.load(self.vae_path, map_location=self.device)
        if self.input_dim is None:
            self.input_dim = checkpoint.get('input_dim', None)
        if self.latent_dim is None:
            self.latent_dim = checkpoint.get('latent_dim', None)
        if self.input_dim is None or self.latent_dim is None:
            raise ValueError("input_dim and latent_dim must be provided or present in checkpoint.")
        self.model = VAE(self.input_dim, self.latent_dim)
        if 'model_state_dict' in checkpoint:
            self.model.load_state_dict(checkpoint['model_state_dict'])
        else:
            self.model.load_state_dict(checkpoint)
        self.model.eval()
        self.model.to(self.device)
        print(f"[control] VAE loaded (in={self.input_dim}, z={self.latent_dim})")

    def encode(self, x_np):
        x = torch.tensor(x_np, dtype=torch.float32, device=self.device)
        with torch.no_grad():
            mu, logvar = self.model.encode(x)
            z = self.model.reparameterize(mu, logvar)
        return z.cpu().numpy(), mu.cpu().numpy(), logvar.cpu().numpy()

    def decode(self, z_np):
        z = torch.tensor(z_np, dtype=torch.float32, device=self.device)
        with torch.no_grad():
            x_hat = self.model.decode(z)
        return x_hat.cpu().numpy()
