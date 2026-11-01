#!/usr/bin/env python

# NaNoBO modification: resource is Unix-only; memory reporting is optional.
try:
    import resource
except ImportError:
    resource = None
import sys


def parse_time(start, end):
    elapsed = end - start  # elapsed time in seconds
    if elapsed <= 1.0:
        ms = elapsed * 1000.
        time_string = f"{ms:.1f} ms"
    elif 1.0 < elapsed < 60.0:
        time_string = f"{elapsed:.1f} s"
    else:
        m, s = divmod(elapsed, 60)
        time_string = f"{m:.0f} min {s:.0f} s"
    return time_string


def memory_usage():
    if resource is None:
        return None, None, None
    if sys.platform == 'darwin':  # MacOS --> memory in bytes
        kB = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1000.
    else:  # Linux --> memory in kilobytes
        kB = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    GB = kB // 1000000.
    MB = kB // 1000.
    kB = kB % 1000.
    return GB, MB, kB


def print_memory_usage():
    GB, MB, kB = memory_usage()
    if GB is None:
        print('==> MEMORY USAGE: unavailable on this platform')
        return
    print(f'==> MEMORY USAGE: {GB:.0f} GB, {MB:.0f} MB, {kB:.0f} kB')
