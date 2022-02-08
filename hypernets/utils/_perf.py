# -*- coding:utf-8 -*-
"""

"""
import time
from _datetime import datetime
from collections import OrderedDict

import pandas as pd
import psutil

try:
    import pynvml

except ImportError:
    pynvml = None
except:
    import traceback

    traceback.print_exc()
    pynvml = None

_gpu_devices = []


def _initialize_pynvml():
    if pynvml is not None and pynvml.nvmlLib is None:
        pynvml.nvmlInit()

        global _gpu_devices
        _gpu_devices = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(pynvml.nvmlDeviceGetCount())]


def get_perf(proc=None, recursive=True, metrics=None):
    """
    Get process performance metrics
    """
    _initialize_pynvml()

    if metrics is None:
        metrics = OrderedDict()

    metrics['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
    metrics['cpu_total'] = psutil.cpu_count()
    metrics['cpu_used'] = psutil.cpu_percent()
    if proc:
        if recursive:
            percents = []
            _recursive_proc(percents, proc, lambda p: p.cpu_percent())
            metrics['proc_count'] = len(percents)
            metrics['cpu_used_proc'] = sum(percents)
        else:
            metrics['cpu_used_proc'] = proc.cpu_percent()

    mem = psutil.virtual_memory()
    metrics['mem_total'] = mem.total
    metrics['mem_used'] = mem.used
    if proc:
        if recursive:
            rss = []
            _recursive_proc(rss, proc, lambda p: p.memory_info().rss)
            metrics['mem_used_proc'] = sum(rss)
        else:
            metrics['mem_used_proc'] = proc.memory_info().rss

    for i, h in enumerate(_gpu_devices):
        used = pynvml.nvmlDeviceGetUtilizationRates(h)
        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
        metrics[f'gpu_{i}_used'] = used.gpu
        metrics[f'gpu_{i}_mem_used'] = mem.used  # used.memory
        metrics[f'gpu_{i}_mem_total'] = mem.total
        metrics[f'gpu_{i}_power_used'] = pynvml.nvmlDeviceGetPowerUsage(h)
        metrics[f'gpu_{i}_power_total'] = pynvml.nvmlDeviceGetPowerManagementLimit(h)

    return metrics


def _recursive_proc(buf, proc_, fn):
    try:
        buf.append(fn(proc_))
        for c in proc_.children():
            _recursive_proc(buf, c, fn)
    except:
        pass


def dump_perf(file_path, pid=None, recursive=False, interval=1):
    """
    Dump process performance metrics data into a csv file
    """

    metrics = OrderedDict()
    proc = psutil.Process(pid) if pid else None
    header = True
    try:
        with open(file_path, 'w') as f:
            while True:
                get_perf(proc, recursive=recursive, metrics=metrics)
                if header:
                    header = False
                    f.write(','.join(metrics.keys()) + '\n')
                f.write(','.join(map(str, metrics.values())) + '\n')
                f.flush()
                time.sleep(interval)
    except:
        import traceback
        traceback.print_exc()
        pass


def load_perf(file_path, human_readable=True):
    df = pd.read_csv(file_path)
    columns = df.columns.to_list()
    assert 'timestamp' in columns

    df['timestamp'] = df['timestamp'].apply(lambda t: datetime.strptime(t, '%Y-%m-%d %H:%M:%S'))
    start_at = df['timestamp'].min()
    delta = pd.Timedelta(1, 'S')
    df.insert(1, 'elapsed', (df['timestamp'] - start_at) // delta)

    if human_readable:
        GB = 1024 ** 3
        if 'cpu_used_proc' in columns:
            df['cpu_used_proc'] = df['cpu_used_proc'] / df['cpu_total']
        for c in columns:
            if c.startswith('mem_'):
                df[c] = df[c] / GB
            if c.startswith('gpu_'):
                if c.find('_power_') > 0:
                    df[c] = df[c] / 1000
                elif c.find('_mem_') > 0:
                    df[c] = df[c] / GB

    return df
