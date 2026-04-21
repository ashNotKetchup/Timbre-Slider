import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from itertools import product
from scipy.interpolate import interp1d
from tqdm import tqdm

def resample_array(array, target_len, kind='cubic', smooth=False):
    """Interpolate array to target_len. Avoids ringing artifacts from FFT resampling."""
    if array.shape[0] == target_len:
        return array
    if array.shape[0] == 1:
        return np.repeat(array, target_len, axis=0)
    
    # Fallback to linear if not enough points for cubic
    if array.shape[0] < 4 and kind == 'cubic':
        kind = 'linear'
        
    x = np.linspace(0, 1, array.shape[0])
    x_new = np.linspace(0, 1, target_len)
    f = interp1d(x, array, axis=0, kind=kind)
    resampled = f(x_new)
    
    if smooth and kind == 'cubic':
        from scipy.ndimage import gaussian_filter1d
        # Apply a mild low-pass filter to remove jaggedness/zipper noise
        resampled = gaussian_filter1d(resampled, sigma=2.0, axis=0)
        
    return resampled

def prepare_data(sound_data, metadata_keys=None, resolution_multiplier=4):
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
            enc_len = sound['encoding'].shape[-1] * resolution_multiplier

            # Resample latent encoding to new length and append
            latent_enc = resample_array(sound['encoding'].squeeze(0).T, enc_len)
            latent_encodings.append(latent_enc)
            for key in metadata_keys:
                # Get feature value (could be scalar or array)
                val = sound['features_recon'][key]
                # If val is an array of shape (1, T), squeeze it so time is axis=0
                if isinstance(val, (np.ndarray, torch.Tensor)):
                    val = np.asarray(val)
                    if val.ndim == 2 and val.shape[0] == 1:
                        val = val.squeeze(0)
                        
                # If scalar, make it a constant vector; if array, resample to enc_len
                if np.isscalar(val) or (isinstance(val, np.ndarray) and val.ndim == 0):
                    vec = np.full((enc_len,), float(val))
                else:
                    vec = resample_array(val, enc_len)

                # Ensure vec is (enc_len, 1) for reliable stacking
                if vec.ndim == 1:
                    vec = vec[:, None]
                features.append(vec)
            
            # Stack features into shape (enc_len, num_features)
            features_stacked = np.concatenate(features, axis=-1)
            metadata_vectors.append(features_stacked)

        # metadata_vectors: list of arrays, each (num_features, enc_len)
        # latent_encodings: list of arrays, each (time, dim)
        # metadata_keys: list of feature names in order

        print(f'[data] {len(latent_encodings)} encodings, shape {latent_encodings[0].shape}')
        
        # Build clip_ids array to track which frame belongs to which clip
        clip_ids = []
        for clip_idx, encoding in enumerate(latent_encodings):
            clip_ids.extend([clip_idx] * encoding.shape[0])
        clip_ids = np.array(clip_ids, dtype=np.int32)
        
        latent_data = np.concatenate(latent_encodings, axis=0)  # shape: (total_time, dim)
        
        # Standardise the latent dataset to mean 0, std 1
        latent_mean = np.mean(latent_data, axis=0, keepdims=True)
        latent_std = np.std(latent_data, axis=0, keepdims=True) + 1e-8
        latent_data = (latent_data - latent_mean) / latent_std
        latent_data = torch.tensor(latent_data, dtype=torch.float32)

        # Standardise metadata elements to mean 0, std 1
        metadata_concat = np.concatenate(metadata_vectors, axis=0)
        meta_mean = np.mean(metadata_concat, axis=0, keepdims=True)
        meta_std = np.std(metadata_concat, axis=0, keepdims=True) + 1e-8
        for i in range(len(metadata_vectors)):
            metadata_vectors[i] = (metadata_vectors[i] - meta_mean) / meta_std

        input_dim = latent_data.shape[1]
        latent_dim = len(metadata_keys) + 4  # Number of metadata features + extra dimensions for unstructured variance

        return latent_data, metadata_vectors, metadata_keys, input_dim, latent_dim, clip_ids

class VAE(nn.Module):
        
    def __init__(self, input_dim, latent_dim):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.LayerNorm(128),
            nn.SiLU(),
            nn.Linear(128, 64),
            nn.LayerNorm(64),
            nn.SiLU(),
        )
        self.fc_mu = nn.Linear(64, latent_dim)
        self.fc_logvar = nn.Linear(64, latent_dim)
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.LayerNorm(64),
            nn.SiLU(),
            nn.Linear(64, 128),
            nn.LayerNorm(128),
            nn.SiLU(),
            nn.Linear(128, input_dim)
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
    
    def encode_mu(self, x):
            """
            Returns the mean vector mu given input x. used for inference and control, where we want a deterministic encoding without sampling noise.
            """
            mu, logvar = self.encode(x)
            return mu

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        recon = self.decode(z)
        return recon, mu, logvar

def attribute_distance_loss_dimwise_vectorised(mu, x_attr, delta=1.0, eps=1e-8):
    """
    Vectorised dimension-wise attribute regularisation. Based on Pati and Lerch

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

def vae_loss(recon_x, x, mu, logvar, x_attr, vae, alpha=10.0, beta=0.1, theta=100): #alpha=1.0, beta=0.1, theta=10.0
    z = vae.reparameterize(mu, logvar)
    loss_fn = nn.MSELoss(reduction='mean')
    recon_loss = loss_fn(recon_x, x)
    # Scale KL down because MSE is using mean now (mean over batch and features)
    kl = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
    attr_loss = attribute_distance_loss_dimwise_vectorised(mu, x_attr, delta=1.0)
    loss = alpha*recon_loss + beta*kl + theta*attr_loss
    return loss, (recon_loss, kl, attr_loss)

def train_vae(vae, latent_data, metadata_vectors, num_epochs=1000, batch_size=256, learning_rate=1e-2, plot_loss=False, alpha_max=10.0, beta_max=0.1, theta_max=10.0):
    optimizer = optim.Adam(vae.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
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

    if plot_loss:
        import matplotlib.pyplot as plt
        plt.ion()  # Turn on interactive mode
        fig, ax = plt.subplots(figsize=(8, 5))
        
    for epoch in tqdm(range(epochs), desc="Training VAE", unit="epoch", ncols=80):
        perm = torch.randperm(latent_data.size(0))
        total_loss = 0
        recon_epoch = 0
        kl_epoch = 0
        attr_epoch = 0


        #no warmup
        alpha = alpha_max
        # beta = beta_max
        # theta = theta_max

        # # With Warmups:
        # alpha_wait = epochs // 10  # Wait 10% of training before starting to apply reconstruction loss
        # alpha_warmup = epochs // 4
        # if epoch < alpha_wait:
        #     alpha = 0.0
        # elif epoch < alpha_warmup:
        #     alpha = alpha_max * (epoch / max(1, alpha_warmup))
        # else:
        #     alpha = alpha_max

        
        # KL annealing 
        kl_warmup_epochs = epochs // 3
        if epoch < kl_warmup_epochs:
            beta = beta_max * (epoch / max(1, kl_warmup_epochs))
        else:
            beta = beta_max

        # Attribute loss
        attr_warmup_epochs = epochs // 4  # Wait 25% of training before starting to apply attribute loss, then ramp up to full over next 25%
        if epoch < attr_warmup_epochs:
            theta = 0.0
        else:
            theta = theta_max * min(1.0, (epoch - attr_warmup_epochs) / max(1, epochs // 6))



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
            
        scheduler.step()
        total_loss_history.append(total_loss)
        recon_loss_history.append(recon_epoch)
        kl_loss_history.append(kl_epoch)
        attr_loss_history.append(attr_epoch)

        if plot_loss and (epoch % 5 == 0 or epoch == epochs - 1):
            ax.clear()
            ax.set_title(f"VAE Training Loss - Epoch {epoch}, alpha={alpha:.2f}, beta={beta:.2f}, theta={theta:.2f}")
            ax.plot(total_loss_history, label='Total Loss', color='black', linewidth=2)
            ax.plot(recon_loss_history, label='Recon Loss', color='blue', alpha=0.7)
            ax.plot(kl_loss_history, label='KL Loss', color='red', alpha=0.7)
            ax.plot(attr_loss_history, label='Attr Loss', color='green', alpha=0.7)
            ax.set_yscale('log')
            ax.set_xlabel('Epoch')
            ax.set_ylabel('Loss (Log Scale)')
            ax.legend(loc='upper right')
            plt.draw()
            plt.pause(0.001)

    if plot_loss:
        plt.ioff()
        # Optional: let the user see the final plot before it gets destroyed, or just keep it closed:
        plt.show() 

    loss_lists = [total_loss_history, recon_loss_history, kl_loss_history, attr_loss_history]
    labels = ['Total Loss', 'Recon Loss', 'KL Loss', 'Attr Loss']

    return vae, loss_lists, labels