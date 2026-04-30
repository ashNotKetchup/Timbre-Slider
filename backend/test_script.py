import torch
from .timbre_VAE.vae_train import attribute_distance_loss_dimwise_vectorised

def main():
    """Entry point for the test_script."""
    mu = torch.randn(256, 4)
    x_attr = torch.randn(256, 4)

    attribute_distance_loss_dimwise_vectorised(mu, x_attr)
    print("Worked for 2D")

if __name__ == "__main__":
    main()
