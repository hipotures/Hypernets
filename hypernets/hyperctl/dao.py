import os

from hypernets.hyperctl.batch import ShellJob


def change_job_status(job: ShellJob, next_status):
    current_status = job.status
    target_status_file = job.status_file_path(next_status)
    if next_status == job.STATUS_INIT:
        raise ValueError(f"can not change to {next_status} ")

    elif next_status == job.STATUS_RUNNING:
        if current_status != job.STATUS_INIT:
            raise ValueError(f"only job in {job.STATUS_INIT} can change to {next_status}")

    elif next_status in job.FINAL_STATUS:
        if current_status != job.STATUS_RUNNING:
            raise ValueError(f"only job in {job.STATUS_RUNNING} can change to "
                             f"{next_status} but now is {current_status}")
        # delete running status file
        running_status_file = job.status_file_path(job.STATUS_RUNNING)
        os.remove(running_status_file)
    else:
        raise ValueError(f"unknown status {next_status}")

    with open(target_status_file, 'w') as f:
        pass
