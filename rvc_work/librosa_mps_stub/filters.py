from __future__ import annotations

import numpy as np


def _hz_to_mel(frequencies):
    scalar = np.isscalar(frequencies)
    frequencies = np.atleast_1d(np.asanyarray(frequencies, dtype=np.float64))
    f_min = 0.0
    f_sp = 200.0 / 3
    mels = (frequencies - f_min) / f_sp
    min_log_hz = 1000.0
    min_log_mel = (min_log_hz - f_min) / f_sp
    logstep = np.log(6.4) / 27.0
    log_t = frequencies >= min_log_hz
    mels[log_t] = min_log_mel + np.log(frequencies[log_t] / min_log_hz) / logstep
    return mels.item() if scalar else mels


def _mel_to_hz(mels):
    scalar = np.isscalar(mels)
    mels = np.atleast_1d(np.asanyarray(mels, dtype=np.float64))
    f_min = 0.0
    f_sp = 200.0 / 3
    freqs = f_min + f_sp * mels
    min_log_hz = 1000.0
    min_log_mel = (min_log_hz - f_min) / f_sp
    logstep = np.log(6.4) / 27.0
    log_t = mels >= min_log_mel
    freqs[log_t] = min_log_hz * np.exp(logstep * (mels[log_t] - min_log_mel))
    return freqs.item() if scalar else freqs


def mel(sr, n_fft, n_mels=128, fmin=0.0, fmax=None, htk=False, norm="slaney", dtype=np.float32):
    if fmax is None:
        fmax = float(sr) / 2
    fftfreqs = np.linspace(0, float(sr) / 2, int(1 + n_fft // 2), dtype=np.float64)
    mel_f = _mel_to_hz(
        np.linspace(_hz_to_mel(float(fmin)), _hz_to_mel(float(fmax)), n_mels + 2)
    )
    fdiff = np.diff(mel_f)
    ramps = np.subtract.outer(mel_f, fftfreqs)
    weights = np.zeros((n_mels, len(fftfreqs)), dtype=np.float64)
    for i in range(n_mels):
        lower = -ramps[i] / fdiff[i]
        upper = ramps[i + 2] / fdiff[i + 1]
        weights[i] = np.maximum(0, np.minimum(lower, upper))
    if norm == "slaney":
        enorm = 2.0 / (mel_f[2 : n_mels + 2] - mel_f[:n_mels])
        weights *= enorm[:, np.newaxis]
    return weights.astype(dtype, copy=False)
