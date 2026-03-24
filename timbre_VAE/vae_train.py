import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from itertools import product
from scipy.signal import resample
from tqdm import tqdm


def prepare_data(sound_data, metadata_keys=None):
        # Prepare latent encodings as training data
        # latent_encodings = [sound['encoding'].squeeze(0).T for sound in sound_data]  # shape: (time, dim)
        print(f"[data] Preparing {len(sound_data)} items …")
        # Create metadata vectors from 'features_recon' for each sound, resampled to match encoding length
        metadata_vectors = []
        latent_encodings = []  # Also collect latent encodings here
        if metadata_keys is None:
            metadata_keys = list(sound_data[0]['features_recon'].keys())
        for sound in sound_data:
            features = []
            enc_len = sound['encoding'].shape[-1]



            # Collect latent encoding for this item

            # (optional) Double the encoding length (resolution) for metadata and latent encoding
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

                features.append(vec)  # Each vec is (296, 1)
                # After collecting all features, stack and transpose to (296, 5)
                features_stacked = np.stack(features, axis=-1)  # (296, 5)
            # Stack features into shape (num_features, enc_len)
            features_stacked = np.stack(features, axis=-1).squeeze()
            metadata_vectors.append(features_stacked)

        # metadata_vectors: list of arrays, each (num_features, enc_len)
        # latent_encodings: list of arrays, each (time, dim)
        # metadata_keys: list of feature names in order

        print(f'[data] {len(latent_encodings)} encodings, shape {latent_encodings[0].shape}')
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

    def encode_z(self, x):
            """
            Returns the latent vector z (reparameterized sample) given input x.
            """
            mu, logvar = self.encode(x)
            return self.reparameterize(mu, logvar)

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        recon = self.decode(z)
        return recon, mu, logvar

def attribute_distance_loss_dimwise_vectorised(mu, x_attr, delta=1.0, eps=1e-8):
    """
    Vectorised dimension-wise attribute regularisation.

    Args:
        mu: Latent samples, shape (B, D_mu)
        x_attr: Attribute outputs, shape (B, D_attr)
        delta: Tanh spread hyperparameter
        eps: Sign stabilisation constant

    Returns:
        Scalar loss (only over min(D_mu, D_attr) dimensions)
    """
    B, D_mu = mu.shape
    D_attr = x_attr.shape[1]
    D = min(D_mu, D_attr)
    if mu.ndim != 2 or x_attr.ndim != 2:
        raise ValueError("mu and x_attr must be 2D tensors of shape (B, D)")
    # Only compare up to the minimum number of dimensions
    Dz = mu[:, None, :D] - mu[None, :, :D]
    Dx = x_attr[:, None, :D] - x_attr[None, :, :D]
    latent_term = torch.tanh(delta * Dz)
    attr_term = torch.sign(Dx + eps)
    loss = torch.abs(latent_term - attr_term).mean()
    return loss

def vae_loss(recon_x, x, mu, logvar, x_attr, vae, alpha=1.0, beta=0.1, theta=10.0):
    z = vae.reparameterize(mu, logvar)
    loss_fn = nn.MSELoss(reduction='sum')
    recon_loss = loss_fn(recon_x, x)
    kl = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    attr_loss = attribute_distance_loss_dimwise_vectorised(mu, x_attr, delta=1.0)
    loss = alpha*recon_loss + beta*kl + theta*attr_loss
    return loss, (recon_loss, kl, attr_loss)

def train_vae(vae, latent_data, metadata_vectors, num_epochs=1000, batch_size=256, learning_rate=1e-4):
    optimizer = optim.Adam(vae.parameters(), lr=learning_rate)
    loss_fn = nn.MSELoss(reduction='sum')
    loss_history = []
    vae.train()
    epochs = num_epochs
    batch_size = batch_size

    # Pre-concatenate metadata once (was previously inside the batch loop)
    metadata_data = torch.tensor(
        np.concatenate(metadata_vectors, axis=0), dtype=torch.float32
    )

    total_loss_history = []
    recon_loss_history = []
    kl_loss_history = []
    attr_loss_history = []

    for epoch in tqdm(range(epochs), desc="Training VAE", unit="epoch", ncols=80):
        perm = torch.randperm(latent_data.size(0))
        total_loss = 0
        recon_epoch = 0
        kl_epoch = 0
        attr_epoch = 0

        alpha = 1.0
        beta = 0.01
        # Linearly increase theta from 0 to 10.0 over the first half of training
        max_theta = 1
        warmup_epochs = 0
        if epoch < warmup_epochs:
            theta = max_theta * (epoch / warmup_epochs)
        else:
            theta = max_theta

        for i in range(0, latent_data.size(0), batch_size):
            idx = perm[i:i+batch_size]
            batch = latent_data[idx]
            x_attr = metadata_data[idx]
            optimizer.zero_grad()
            recon, mu, logvar = vae(batch)
            loss, (recon_loss, kl, attr_loss) = vae_loss(recon, batch, mu, logvar, x_attr, vae, alpha, beta, theta)
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

    loss_lists = [total_loss_history, recon_loss_history, kl_loss_history, attr_loss_history]
    labels = ['Total Loss', 'Recon Loss', 'KL Loss', 'Attr Loss']

    return vae, loss_lists, labels