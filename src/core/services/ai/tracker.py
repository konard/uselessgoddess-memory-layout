import numpy as np
import scipy.linalg as linalg
from scipy.optimize import linear_sum_assignment
from dataclasses import dataclass
from typing import List

from core.services.ai.infer import Target


@dataclass
class STrack:
  tlwh: np.ndarray
  score: float
  label: str
  track_id: int = 0
  state: int = 1  # 1=New/Tracked, 2=Lost, 3=Removed
  is_activated: bool = False
  frame_id: int = 0
  start_frame: int = 0

  mean: np.ndarray = None
  covariance: np.ndarray = None

  @property
  def tlbr(self):
    """Top-Left-Bottom-Right"""
    ret = self.tlwh.copy()
    ret[2:] += ret[:2]
    return ret


class KalmanFilter:
  def __init__(self):
    ndim, dt = 4, 1.0

    # Matricies
    self._motion_mat = np.eye(2 * ndim, 2 * ndim)
    for i in range(ndim):
      self._motion_mat[i, ndim + i] = dt

    self._update_mat = np.eye(ndim, 2 * ndim)

    # Weights
    self._std_weight_position = 1.0 / 20
    self._std_weight_velocity = 1.0 / 160

  def initiate(self, measurement):
    mean_pos = measurement
    mean_vel = np.zeros_like(mean_pos)
    mean = np.r_[mean_pos, mean_vel]

    std = [
      2 * self._std_weight_position * measurement[3],
      2 * self._std_weight_position * measurement[3],
      1e-2,
      2 * self._std_weight_position * measurement[3],
      10 * self._std_weight_velocity * measurement[3],
      10 * self._std_weight_velocity * measurement[3],
      1e-5,
      10 * self._std_weight_velocity * measurement[3],
    ]
    covariance = np.diag(np.square(std))
    return mean, covariance

  def predict(self, mean, covariance):
    std_pos = [
      self._std_weight_position * mean[3],
      self._std_weight_position * mean[3],
      1e-2,
      self._std_weight_position * mean[3],
    ]
    std_vel = [
      self._std_weight_velocity * mean[3],
      self._std_weight_velocity * mean[3],
      1e-5,
      self._std_weight_velocity * mean[3],
    ]
    motion_cov = np.diag(np.square(np.r_[std_pos, std_vel]))

    # x' = Fx
    mean = np.dot(self._motion_mat, mean)
    # P' = FPF^T + Q
    covariance = (
      np.linalg.multi_dot((self._motion_mat, covariance, self._motion_mat.T))
      + motion_cov
    )

    return mean, covariance

  def project(self, mean, covariance):
    std = [
      self._std_weight_position * mean[3],
      self._std_weight_position * mean[3],
      1e-1,
      self._std_weight_position * mean[3],
    ]
    innovation_cov = np.diag(np.square(std))

    # Hx
    mean = np.dot(self._update_mat, mean)
    # HPH^T + R
    covariance = (
      np.linalg.multi_dot((self._update_mat, covariance, self._update_mat.T))
      + innovation_cov
    )

    return mean, covariance

  def update(self, mean, covariance, measurement):
    projected_mean, projected_cov = self.project(mean, covariance)

    # K = PH^T * S^-1
    # ИСПРАВЛЕНО: используем scipy.linalg вместо np.linalg
    chol_factor, lower = linalg.cho_factor(
      projected_cov, lower=True, check_finite=False
    )
    kalman_gain = linalg.cho_solve(
      (chol_factor, lower),
      np.dot(covariance, self._update_mat.T).T,
      check_finite=False,
    ).T

    innovation = measurement - projected_mean

    # x = x + Ky
    new_mean = mean + np.dot(innovation, kalman_gain.T)

    # P = (I - KH)P
    new_covariance = covariance - np.linalg.multi_dot(
      (kalman_gain, projected_cov, kalman_gain.T)
    )

    return new_mean, new_covariance


def iou_batch(bboxes1, bboxes2):
  bboxes2 = np.expand_dims(bboxes2, 0)
  bboxes1 = np.expand_dims(bboxes1, 1)

  xx1 = np.maximum(bboxes1[..., 0], bboxes2[..., 0])
  yy1 = np.maximum(bboxes1[..., 1], bboxes2[..., 1])
  xx2 = np.minimum(bboxes1[..., 2], bboxes2[..., 2])
  yy2 = np.minimum(bboxes1[..., 3], bboxes2[..., 3])

  w = np.maximum(0.0, xx2 - xx1)
  h = np.maximum(0.0, yy2 - yy1)
  wh = w * h

  o = wh / (
    (bboxes1[..., 2] - bboxes1[..., 0]) * (bboxes1[..., 3] - bboxes1[..., 1])
    + (bboxes2[..., 2] - bboxes2[..., 0]) * (bboxes2[..., 3] - bboxes2[..., 1])
    - wh
  )
  return o


class ByteTracker:
  def __init__(self, track_thresh=0.5, track_buffer=30, match_thresh=0.8):
    self.track_thresh = track_thresh
    self.track_buffer = track_buffer
    self.match_thresh = match_thresh

    self.tracked_stracks: List[STrack] = []
    self.lost_stracks: List[STrack] = []
    self.removed_stracks: List[STrack] = []

    self.frame_id = 0
    self.kalman = KalmanFilter()

  def update(self, targets: List[Target]) -> List[Target]:
    self.frame_id += 1

    activated_starcks = []
    refind_stracks = []
    lost_stracks = []
    _removed_stracks = []

    scores = np.array([t.confidence for t in targets])
    bboxes = np.array(
      [
        [t.mid_x - t.width / 2, t.mid_y - t.height / 2, t.width, t.height]
        for t in targets
      ]
    )

    remain_inds = scores > self.track_thresh
    inds_low = scores > 0.1
    inds_high = scores < self.track_thresh
    inds_second = np.logical_and(inds_low, inds_high)

    detections = [
      STrack(bboxes[i], scores[i], targets[i].label)
      for i in range(len(targets))
      if remain_inds[i]
    ]
    detections_second = [
      STrack(bboxes[i], scores[i], targets[i].label)
      for i in range(len(targets))
      if inds_second[i]
    ]

    unconfirmed = []
    tracked_stracks = []
    for track in self.tracked_stracks:
      if not track.is_activated:
        unconfirmed.append(track)
      else:
        tracked_stracks.append(track)

    strack_pool = join_stracks(tracked_stracks, self.lost_stracks)

    for strack in strack_pool:
      strack.mean, strack.covariance = self.kalman.predict(
        strack.mean, strack.covariance
      )

    dists = self._get_dists(strack_pool, detections)
    matches, u_track, u_detection = self._linear_assignment(
      dists, thresh=self.match_thresh
    )

    for itracked, idet in matches:
      track = strack_pool[itracked]
      det = detections[idet]
      if track.state == 1:
        self._update_track(track, det)
        activated_starcks.append(track)
      else:
        self._update_track(track, det)
        track.state = 1
        refind_stracks.append(track)

    r_tracked_stracks = [
      strack_pool[i] for i in u_track if strack_pool[i].state == 1
    ]
    dists = self._get_dists(r_tracked_stracks, detections_second)
    matches, u_track, u_detection_second = self._linear_assignment(
      dists, thresh=0.5
    )

    for itracked, idet in matches:
      track = r_tracked_stracks[itracked]
      det = detections_second[idet]
      if track.state == 1:
        self._update_track(track, det)
        activated_starcks.append(track)
      else:
        self._update_track(track, det)
        track.state = 1
        refind_stracks.append(track)

    for it in u_track:
      track = r_tracked_stracks[it]
      if not track.state == 2:
        track.state = 2
        lost_stracks.append(track)

    for inew in u_detection:
      track = detections[inew]
      if track.score < self.track_thresh:
        continue
      self._init_track(track)
      activated_starcks.append(track)

    self.tracked_stracks = [t for t in self.tracked_stracks if t.state == 1]
    self.tracked_stracks = join_stracks(self.tracked_stracks, activated_starcks)
    self.tracked_stracks = join_stracks(self.tracked_stracks, refind_stracks)
    self.lost_stracks = sub_stracks(self.lost_stracks, self.tracked_stracks)
    self.lost_stracks.extend(lost_stracks)
    self.lost_stracks = sub_stracks(self.lost_stracks, self.removed_stracks)

    self.lost_stracks = [
      t
      for t in self.lost_stracks
      if self.frame_id - t.frame_id < self.track_buffer
    ]

    final_targets = []
    output_stracks = [t for t in self.tracked_stracks if t.is_activated]

    for track in output_stracks:
      _x, _y, _a, _h = track.mean[:4]
      t_w = _h * _a
      t_h = _h
      mid_x = _x
      mid_y = _y

      new_target = Target(
        input_x=0,
        input_y=0,
        mid_x=mid_x,
        mid_y=mid_y,
        width=t_w,
        height=t_h,
        confidence=track.score,
        label=track.label,
        laidx=0,
      )
      new_target.track_id = track.track_id
      final_targets.append(new_target)

    return final_targets

  def _init_track(self, track):
    bbox = track.tlwh
    xyah = np.r_[
      bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2, bbox[2] / bbox[3], bbox[3]
    ]
    track.mean, track.covariance = self.kalman.initiate(xyah)
    track.is_activated = True
    track.track_id = self._next_id()
    track.start_frame = self.frame_id
    track.frame_id = self.frame_id

  def _update_track(self, track, new_track):
    bbox = new_track.tlwh
    xyah = np.r_[
      bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2, bbox[2] / bbox[3], bbox[3]
    ]
    track.mean, track.covariance = self.kalman.update(
      track.mean, track.covariance, xyah
    )
    track.tlwh = new_track.tlwh
    track.score = new_track.score
    track.frame_id = self.frame_id

  def _get_dists(self, tracks, detections):
    if len(tracks) == 0 or len(detections) == 0:
      return np.zeros((len(tracks), len(detections)))

    t_boxes = np.array([t.tlbr for t in tracks])
    d_boxes = np.array([d.tlbr for d in detections])

    ious = iou_batch(t_boxes, d_boxes)
    dists = 1 - ious
    return dists

  def _linear_assignment(self, cost_matrix, thresh):
    if cost_matrix.size == 0:
      return (
        np.empty((0, 2), dtype=int),
        tuple(range(cost_matrix.shape[0])),
        tuple(range(cost_matrix.shape[1])),
      )

    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    matches, unmatched_a, unmatched_b = [], [], []

    for i in range(len(row_ind)):
      if cost_matrix[row_ind[i], col_ind[i]] > thresh:
        unmatched_a.append(row_ind[i])
        unmatched_b.append(col_ind[i])
      else:
        matches.append((row_ind[i], col_ind[i]))

    for i in range(cost_matrix.shape[0]):
      if i not in row_ind:
        unmatched_a.append(i)
    for i in range(cost_matrix.shape[1]):
      if i not in col_ind:
        unmatched_b.append(i)

    return matches, unmatched_a, unmatched_b

  _count = 0

  def _next_id(self):
    self._count += 1
    return self._count


def join_stracks(tlista, tlistb):
  exists = {}
  res = []
  for t in tlista:
    exists[t.track_id] = 1
    res.append(t)
  for t in tlistb:
    tid = t.track_id
    if not exists.get(tid, 0):
      exists[tid] = 1
      res.append(t)
  return res


def sub_stracks(tlista, tlistb):
  stracks = {}
  for t in tlista:
    stracks[t.track_id] = t
  for t in tlistb:
    tid = t.track_id
    if stracks.get(tid, 0):
      del stracks[tid]
  return list(stracks.values())
