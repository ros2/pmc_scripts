from dataclasses import dataclass


@dataclass
class PackagingJob:
    job_name: str
    label: str


@dataclass
class RosDistroInfo:
    name: str
    packaging_jobs: list[PackagingJob]


JOB_LINUX = PackagingJob("ci_packaging_linux", "Linux")
JOB_LINUX_AARCH64 = PackagingJob("ci_packaging_linux-aarch64", "Linux-aarch64")
JOB_LINUX_RHEL = PackagingJob("ci_packaging_linux-rhel", "Linux-rhel")
JOB_WINDOWS = PackagingJob("ci_packaging_windows", "Windows")

ALL_PACKAGING_JOBS = [
    JOB_LINUX,
    JOB_LINUX_AARCH64,
    JOB_LINUX_RHEL,
    JOB_WINDOWS,
]

NO_WINDOWS_PACKAGING_JOBS = [
    JOB_LINUX,
    JOB_LINUX_AARCH64,
    JOB_LINUX_RHEL,
]

DISTRO_INFO_MAP: dict[str, RosDistroInfo] = {
    "rolling": RosDistroInfo(name="rolling", packaging_jobs=ALL_PACKAGING_JOBS),
    "lyrical": RosDistroInfo(name="lyrical", packaging_jobs=ALL_PACKAGING_JOBS),
    "kilted": RosDistroInfo(name="kilted", packaging_jobs=NO_WINDOWS_PACKAGING_JOBS),
    "jazzy": RosDistroInfo(name="jazzy", packaging_jobs=NO_WINDOWS_PACKAGING_JOBS),
    "humble": RosDistroInfo(name="humble", packaging_jobs=NO_WINDOWS_PACKAGING_JOBS),
}


def get_distro_info(distro_name: str) -> RosDistroInfo:
    """Get RosDistroInfo for a given ROS distribution."""
    distro_lower = distro_name.lower()
    return DISTRO_INFO_MAP.get(
        distro_lower,
        RosDistroInfo(name=distro_lower, packaging_jobs=ALL_PACKAGING_JOBS)
    )
