import numpy as np
import warnings
import scipy.signal as signal
from scipy.interpolate import PchipInterpolator

class GlobalScaler:
    """
    Scale arrays based on a stored min/max to ±output_range.

    fit() stores one min/max over the whole array (every channel shares it). set_range() stores one
    per channel instead, e.g. the range each control dim covers over the training folder, so every
    slider spans the values the data actually has.
    """
    def __init__(self):
        self.global_min = None
        self.global_max = None

    def fit(self, array: np.ndarray):
        """Store min and max from array for future scaling."""
        self.global_min = np.min(array)
        self.global_max = np.max(array)
        if self.global_min == self.global_max:
            self.global_max += 1e-8  # avoid divide-by-zero
        return self

    def set_range(self, low, high):
        """Store a min/max per channel; arrays are (batch, channels, length)."""
        low = np.asarray(low, dtype=np.float32).reshape(1, -1, 1)
        high = np.asarray(high, dtype=np.float32).reshape(1, -1, 1)
        self.global_min = low
        self.global_max = np.maximum(high, low + 1e-8)  # avoid divide-by-zero
        return self

    def scale(self, array: np.ndarray, output_range: float = 1.0) -> np.ndarray:
        """
        Scale array based on stored min/max to a range of ±output_range 
        eg: a output_range=2 means range expands ±200% of original range.
        """
        if self.global_min is None or self.global_max is None:
            warnings.warn("Scaler not fitted yet; returning input unchanged", UserWarning)
            return array
        mid = (self.global_max + self.global_min) / 2
        spread = (self.global_max - self.global_min) / 2
        scaled = (array - mid) / spread  # normalize to [-1,1]
        return scaled * output_range

    def descale(self, scaled_array: np.ndarray, output_range: float = 1.0) -> np.ndarray:
        """Reverse the scaling to recover the original values."""
        if self.global_min is None or self.global_max is None:
            warnings.warn("Scaler not fitted yet; returning input unchanged", UserWarning)
            return scaled_array  
        mid = (self.global_max + self.global_min) / 2
        spread = (self.global_max - self.global_min) / 2
        array = scaled_array / output_range
        array = array * spread + mid
        return array
    
    def info(self) -> str:
        """Return a string with current min/max info."""
        return f"GlobalScaler(min={self.global_min}, max={self.global_max})"




class TimeCompressor:
    """
    Temporally compress and uncompress sequences based on comparison to a stored low-res sequence
    """

    ## Pseudo-code:
    # store init_hi_res: np.ndarray
    # store init_lo_res: np.ndarray = downsample(init_hi_res, factor)

    # get new_lo_res: np.ndarray from some input
    # calculate change_lo_res = compare(new_lo_res, init_lo_res) difference or scale
    # upsample change_lo_res to change_hi_res = upsample(change_lo_res, factor)
    # new_hi_res = init_lo_res + change_hi_res


    def __init__(self):
        self.init_hi_res = None
        self.init_lo_res = None
        self.factor = 10  # downsampling/upsampling factor
        self.factor_used = 1  # factor applied to the current clip (1 when it is too short to decimate)
        

    def set_factor(self, factor: int):
        """Set the downsampling/upsampling factor."""
        self.factor = factor 

    # def fit(self, array: np.ndarray):
    #     """Store init array for future upsampling."""
    #     self.init_hi_res = array
    #     # print("Fitting TimeCompressor with array shape:", array.shape)
    #     self.init_lo_res = signal.decimate(array, self.factor, axis=2)
    #     return self
    
    # scipy.signal.decimate's default IIR filter is applied with filtfilt, which needs more than
    # 3 * (order + 1) = 27 samples along the time axis.
    MIN_DECIMATE_LENGTH = 28
    # Short clips are decimated less, so they still have at least this many points to edit.
    MIN_POINTS = 12

    def down_scale(self, array: np.ndarray) -> np.ndarray:
        self.init_hi_res = array
        print("Fitting TimeCompressor with array shape:", array.shape)
        n = array.shape[2]
        factor = min(self.factor, max(1, n // self.MIN_POINTS))
        if factor > 1 and n >= self.MIN_DECIMATE_LENGTH:
            self.factor_used = factor
            self.init_lo_res = signal.decimate(array, factor, axis=2)
        else:
            # Too short to decimate (under ~1.3 s with Stable Audio): keep every frame
            self.factor_used = 1
            self.init_lo_res = np.array(array, copy=True)
        print("Downscaled shape:", self.init_lo_res.shape)
        return self.init_lo_res

    def up_scale(self, new_lo_res: np.ndarray) -> np.ndarray:
        """
        Scale array based on stored min/max to a range of ±output_range 
        eg: a output_range=2 means range expands ±200% of original range.
        """

        # compare
        diff_lo_res = new_lo_res - self.init_lo_res # or could be ratio?
        # upsample
        diff_hi_res = self._upsample(diff_lo_res, self.init_hi_res.shape[2])
        # add
        new_hi_res = self.init_hi_res + diff_hi_res
        return new_hi_res

    def _upsample(self, lo_res: np.ndarray, n_hi: int) -> np.ndarray:
        """Interpolate a low-res sequence (batch, channels, n_lo) back to n_hi frames.

        decimate keeps every factor-th frame, so low-res point i sits at frame i * factor. Shape-
        preserving cubic (PCHIP) interpolation joins the points without overshoot, and the last
        value is held to the end of the clip. (FFT resampling, used before, treated the sequence
        as periodic: drawn edits rang on both sides and wrapped round to the clip's ends.)
        """
        n_lo = lo_res.shape[2]
        if n_lo == n_hi:
            return lo_res
        if n_lo == 1:
            return np.repeat(lo_res, n_hi, axis=2)
        x_lo = np.arange(n_lo) * self.factor_used
        x_hi = np.clip(np.arange(n_hi), 0, x_lo[-1])
        return PchipInterpolator(x_lo, lo_res, axis=2)(x_hi).astype(lo_res.dtype, copy=False)

    
    # def info(self) -> str:
    #     """Return a string with current min/max info."""
    #     return f"GlobalScaler(min={self.global_min}, max={self.global_max})"
