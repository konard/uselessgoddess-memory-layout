import numpy as np


class SimpleKalmanFilter:
  def __init__(self, R=1, Q=1, A=1, B=0, C=1):
    self.R = R  # Mesaure Noise
    self.Q = Q  # Process Noise
    self.A = A  # State transition
    self.B = B  # Control matrix
    self.C = C  # Measurement matrix

    self.cov = np.nan
    self.x = np.nan

  def update(self, measurement):
    if np.isnan(self.x):
      self.x = measurement
      self.cov = 1.0
    else:
      pred_x = (self.A * self.x) + (self.B * 0)
      pred_cov = (self.A * self.cov * self.A) + self.Q

      K = pred_cov * self.C / ((self.C * pred_cov * self.C) + self.R)
      self.x = pred_x + K * (measurement - (self.C * pred_x))
      self.cov = pred_cov - (K * self.C * pred_cov)

    return self.x
