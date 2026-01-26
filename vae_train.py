import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from itertools import product
from scipy.signal import resample


def prepare_data(sound_data):
        # Prepare latent encodings as training data
        latent_encodings = [sound['encoding'].squeeze(0).T for sound in sound_data]  # shape: (time, dim)

        # Create metadata vectors from 'features_recon' for each sound, resampled to match encoding length
        metadata_vectors = []
        latent_encodings = []  # Also collect latent encodings here
        metadata_keys = list(sound_data[0]['features_recon'].keys())
        for sound in sound_data:
            features = []
            enc_len = sound['encoding'].shape[-1]
            # Collect latent encoding for this item

            # Double the encoding length (resolution) for metadata and latent encoding
            enc_len = sound['encoding'].shape[-1] * 4

            # Resample latent encoding to new length and append
            latent_enc = resample(sound['encoding'].squeeze(0).T, enc_len, axis=0)
            latent_encodings.append(latent_enc)
            for key in metadata_keys:
                # Get feature value (could be scalar or array)
                val = sound['features_recon'][key]
                # print(val.shape)
                # If scalar, make it a constant vector; if array, resample to enc_len
                if np.isscalar(val):
                    vec = np.full(enc_len, val)
                else:
                    vec = resample(val, enc_len, axis=-1)
                    # print(vec.shape)

                features.append(vec)  # Each vec is (296, 1)
                # After collecting all features, stack and transpose to (296, 5)
                features_stacked = np.stack(features, axis=-1)  # (296, 5)
            # Stack features into shape (num_features, enc_len)
            features_stacked = np.stack(features, axis=-1).squeeze()
            metadata_vectors.append(features_stacked)

        # metadata_vectors: list of arrays, each (num_features, enc_len)
        # latent_encodings: list of arrays, each (time, dim)
        # metadata_keys: list of feature names in order

        print(f'Prepared {len(latent_encodings)} latent encodings and metadata vectors. Shape of first latent encoding: {latent_encodings[0].shape}, first metadata vector: {metadata_vectors[0].shape}')
        latent_data = np.concatenate(latent_encodings, axis=0)  # shape: (total_time, dim)
        latent_data = torch.tensor(latent_data, dtype=torch.float32)

        input_dim = latent_data.shape[1]
        latent_dim = len(metadata_keys)  # Number of metadata features

        return latent_data, metadata_vectors, metadata_keys, input_dim, latent_dim

class VAE(nn.Module):
    def __init__(self, input_dim, latent_dim):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
        )
        self.fc_mu = nn.Linear(16, latent_dim)
        self.fc_logvar = nn.Linear(16, latent_dim)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, input_dim)
        )
        self.input_dim = input_dim
        self.latent_dim = latent_dim

    

    def encode(self, x):
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_logvar(h)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        recon = self.decode(z)
        return recon, mu, logvar

def attribute_distance_loss_dimwise_vectorised(z, x_attr, delta=1.0, eps=1e-8):
    """
    Vectorised dimension-wise attribute regularisation.

    Args:
        z: Latent samples, shape (B, D)
        x_attr: Attribute outputs, shape (B, D)
        delta: Tanh spread hyperparameter
        eps: Sign stabilisation constant

    Returns:
        Scalar loss
    """
    B = z.shape[0]
    device = z.device
    if z.ndim != 2 or x_attr.ndim != 2:
        raise ValueError("z and x_attr must be 2D tensors of shape (B, D)")
    if z.shape != x_attr.shape:
        raise ValueError(f"Shape mismatch: z.shape={z.shape}, x_attr.shape={x_attr.shape}")
    Dz = torch.abs(z[:, None, :] - z[None, :, :])
    Dx = torch.abs(x_attr[:, None, :] - x_attr[None, :, :])
    latent_term = torch.tanh(delta * Dz)
    attr_term = torch.sign(Dx + eps)
    loss = torch.abs(latent_term - attr_term).mean()
    return loss

def vae_loss(recon_x, x, mu, logvar, x_attr, vae, alpha=1.0, beta=0.1, theta=10.0):
    z = vae.reparameterize(mu, logvar)
    loss_fn = nn.MSELoss(reduction='sum')
    recon_loss = loss_fn(recon_x, x)
    kl = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    attr_loss = attribute_distance_loss_dimwise_vectorised(z, x_attr, delta=1.0)
    loss = alpha*recon_loss + beta*kl + theta*attr_loss
    return loss, (recon_loss, kl, attr_loss)

def train_vae(vae, latent_data, metadata_vectors, num_epochs=1000, batch_size=256, learning_rate=1e-4):
    optimizer = optim.Adam(vae.parameters(), lr=learning_rate)
    loss_fn = nn.MSELoss(reduction='sum')
    loss_history = []
    vae.train()
    epochs = num_epochs
    batch_size = batch_size
    total_loss_history = []
    recon_loss_history = []
    kl_loss_history = []
    attr_loss_history = []

    for epoch in range(epochs):
        perm = torch.randperm(latent_data.size(0))
        total_loss = 0
        recon_epoch = 0
        kl_epoch = 0
        attr_epoch = 0
        for i in range(0, latent_data.size(0), batch_size):
            idx = perm[i:i+batch_size]
            batch = latent_data[idx]
            # metadata_vectors is a list of arrays, each (num_features, enc_len)
            # We need to concatenate all metadata_vectors along the time axis to match latent_data
            metadata_data = np.concatenate([m for m in metadata_vectors], axis=0)  # shape: (total_time, num_features)
            metadata_data = torch.tensor(metadata_data, dtype=torch.float32)
            x_attr = metadata_data[idx]
            optimizer.zero_grad()
            recon, mu, logvar = vae(batch)
            loss, (recon_loss, kl, attr_loss) = vae_loss(recon, batch, mu, logvar, x_attr, vae)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            recon_epoch += recon_loss.item()
            kl_epoch += kl.item()
            attr_epoch += attr_loss.item()
        total_loss_history.append(total_loss)
        recon_loss_history.append(recon_epoch)
        kl_loss_history.append(kl_epoch)
        attr_loss_history.append(attr_epoch)
        if (epoch+1) % 10 == 0:
            print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss:.2f}")

    loss_lists = [total_loss_history, recon_loss_history, kl_loss_history, attr_loss_history]
    labels = ['Total Loss', 'Recon Loss', 'KL Loss', 'Attr Loss']

    return vae, loss_lists, labels