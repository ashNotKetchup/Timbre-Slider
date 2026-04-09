import torch
from timbre_VAE.vae_train import attribute_distance_loss_dimwise_vectorised

mu = torch.randn(256, 4)
x_attr = torch.randn(256, 4)

attribute_distance_loss_dimwise_vectorised(mu, x_attr)
print("Worked for 2D")
