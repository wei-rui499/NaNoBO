#!/usr/bin/env python

# ======================================================================

from olympus.campaigns.observations import Observations
from olympus.campaigns.param_space import ParameterSpace

# NaNoBO fix: importing ParameterSpace for Dataset must not eagerly import Campaign and re-enter Dataset.
__all__ = ["Campaign", "Observations", "ParameterSpace"]


def __getattr__(name):
    if name == "Campaign":
        from olympus.campaigns.campaign import Campaign
        globals()[name] = Campaign
        return Campaign
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
