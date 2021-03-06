# -*- coding: utf-8 -*-

import datetime
import gevent
import psutil
import logging

from gevent import monkey

from psutil import (
    AccessDenied,
    NoSuchProcess,
)

from koenig import koenig_thrift
from koenig.models import RuntimeProfile

from koenig.utils import (
    profile_,
    serialize,
    datetime2utc,
)

from koenig.exc import (
    raise_user_exc,
    raise_system_exc,
    KoenigErrorCode,
)


monkey.patch_all()
logger = logging.getLogger(__name__)


def __extend_process(process):

    attrs = process.as_dict(attrs=[
        'pid', 'ppid', 'name', 'username', 'create_time',
        'cpu_percent', 'memory_percent', 'cwd', 'status',
    ])

    # hack trick to call cpu_percent with interval 0.1
    gevent.sleep(0.1)

    attrs.update(process.as_dict(attrs=['cpu_percent']))

    process.__dict__.clear()
    process.__dict__.update(attrs)

    return process


@profile_
def query_cpu_times():
    cpu_times = psutil.cpu_times()
    return serialize(cpu_times, koenig_thrift.TCPUTimes)


@profile_
def query_cpu_times_percpu():
    cpu_times_percpu = psutil.cpu_times(percpu=True)
    return serialize(cpu_times_percpu, koenig_thrift.TCPUTimes, _list=True)


@profile_
def query_cpu_percent(interval):
    cpu_percent = psutil.cpu_percent(interval)
    return cpu_percent


@profile_
def query_cpu_percent_percpu(interval):
    cpu_percent_percpu = psutil.cpu_percent(interval, percpu=True)
    return cpu_percent_percpu


@profile_
def query_cpu_times_percent(interval):
    cpu_times_percent = psutil.cpu_times_percent(interval)
    return serialize(
        cpu_times_percent,
        koenig_thrift.TCPUTimesPercent)


@profile_
def query_cpu_times_percent_percpu(interval):
    cpu_times_percent_percpu = psutil.cpu_times_percent(interval, percpu=True)
    return serialize(
        cpu_times_percent_percpu,
        koenig_thrift.TCPUTimesPercent,
        _list=True)


@profile_
def query_virtual_memory():
    virtual_memory = psutil.virtual_memory()
    return serialize(virtual_memory, koenig_thrift.TVirtualMemory)


@profile_
def query_swap_memory():
    swap_memory = psutil.swap_memory()
    return serialize(swap_memory, koenig_thrift.TSwapMemory)


@profile_
def query_disk_partitions():
    disk_partitions = psutil.disk_partitions()
    return serialize(
        disk_partitions,
        koenig_thrift.TDiskPartition,
        _list=True)


@profile_
def query_disk_io_counters():
    disk_io_counters = psutil.disk_io_counters()
    return serialize(disk_io_counters, koenig_thrift.TDiskIOCounters)


@profile_
def query_disk_io_counters_perdisk():
    disk_io_counters_perdisk = psutil.disk_io_counters(perdisk=True)
    return serialize(
        disk_io_counters_perdisk,
        koenig_thrift.TDiskIOCounters,
        _map=True)


@profile_
def query_disk_usage(path):
    try:
        disk_usage = psutil.disk_usage(path)
    except OSError:
        raise_user_exc(KoenigErrorCode.DISK_PATH_NOT_FOUND)

    return serialize(disk_usage, koenig_thrift.TDiskUsage)


@profile_
def query_net_io_counters():
    net_io_counters = psutil.net_io_counters()
    return serialize(
        net_io_counters,
        koenig_thrift.TNetworkIOCounters)


@profile_
def query_net_io_counters_pernic():
    net_io_counters_pernic = psutil.net_io_counters(pernic=True)
    return serialize(
        net_io_counters_pernic,
        koenig_thrift.TNetworkIOCounters,
        _map=True)


@profile_
def query_net_connections():
    try:
        net_connections = psutil.net_connections()
    except AccessDenied:
        raise_user_exc(KoenigErrorCode.ACCESS_DENIED)

    return serialize(
        net_connections,
        koenig_thrift.TNetworkConnections,
        _list=True)


@profile_
def query_login_users():
    login_users = psutil.users()
    return serialize(login_users, koenig_thrift.TUser, _list=True)


@profile_
def query_boot_time():
    boot_time = psutil.boot_time()
    return datetime.datetime.fromtimestamp(boot_time).\
        strftime('%Y-%m-%d %H:%M:%S')


@profile_
def query_pids():
    return psutil.pids()


@profile_
def query_process_by_pid(pid):

    try:
        process = psutil.Process(pid)
    except AccessDenied:
        raise_user_exc(KoenigErrorCode.ACCESS_DENIED)
    except NoSuchProcess:
        raise_system_exc(KoenigErrorCode.PROCESS_NOT_FOUND)

    process = __extend_process(process)

    return serialize(process, koenig_thrift.TProcess)


@profile_
def query_processes_by_pids(pids):

    threads = []

    for pid in pids:
        try:
            process = psutil.Process(pid)
        except AccessDenied:
            raise_user_exc(KoenigErrorCode.ACCESS_DENIED)
        except NoSuchProcess:
            raise_system_exc(KoenigErrorCode.PROCESS_NOT_FOUND)

        threads.append(gevent.spawn(__extend_process, process))

    gevent.joinall(threads)
    result = {thread.value.__dict__['pid']: thread.value
              for thread in threads}

    return serialize(result, koenig_thrift.TProcess, _map=True)


@profile_
def query_runtime_statistic():
    start_ts = datetime.datetime.now().replace(second=0, microsecond=0)
    end_ts = start_ts - datetime.timedelta(minutes=5)

    profiles = RuntimeProfile.get_by_ts(start_ts, end_ts)
    for profile in profiles:
        if profile:
            profiles.profile_ts = datetime2utc(profile.profile_ts)
    profiles.sort(key=lambda p: p.profile_ts)

    return serialize(profiles, koenig_thrift.TRuntimeProfile, _list=True)
