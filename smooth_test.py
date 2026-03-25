import torch
import numpy as np
from scipy.ndimage import gaussian_filter1d

# Suppose control model decode output is 
out = torch.randn(100, 64)

# Smooth over time (axis=0)
out_np = out.numpy()
smoothed = gaussian_filter1d(out_np, sigma=2.0, axis=0)
print(smoothed.shape)
