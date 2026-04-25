"""Local runtime shims for the RVC CPU training workspace."""

from __future__ import annotations

import sys
import types


class _NoopSummaryWriter:
    def __init__(self, *args, **kwargs):
        pass

    def add_scalar(self, *args, **kwargs):
        pass

    def add_histogram(self, *args, **kwargs):
        pass

    def add_image(self, *args, **kwargs):
        pass

    def add_audio(self, *args, **kwargs):
        pass

    def flush(self):
        pass

    def close(self):
        pass


tensorboard_module = types.ModuleType("torch.utils.tensorboard")
tensorboard_module.SummaryWriter = _NoopSummaryWriter
sys.modules.setdefault("torch.utils.tensorboard", tensorboard_module)
