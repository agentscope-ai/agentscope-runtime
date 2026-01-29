# -*- coding: utf-8 -*-
import platform
import subprocess
import logging


class HostPrerequisiteError(Exception):
    """Exception raised when host prerequisites
    for MobileSandbox are not met."""


logger = logging.getLogger(__name__)


def check_mobile_sandbox_host_readiness() -> None:
    """
    Performs a check of the host environment to ensure it has the necessary
    modules (like binder_linux) to run the MobileSandbox.
    """
    logger.info(
        "Performing host environment check for MobileSandbox readiness...",
    )

    architecture = platform.machine().lower()
    if architecture in ("aarch64", "arm64"):
        logger.warning(
            "\n======================== WARNING ========================\n"
            "ARM64/aarch64 architecture detected (e.g., Apple M-series).\n"
            "Running this mobile sandbox on a non-x86_64 host may lead \n"
            " to unexpected compatibility or performance issues.\n"
            "=========================================================",
        )

    os_type = platform.system()
    if os_type == "Linux":
        try:
            result = subprocess.run(
                ["lsmod"],
                capture_output=True,
                text=True,
                check=True,
            )
            loaded_modules = result.stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            loaded_modules = ""
            logger.warning(
                "Could not execute 'lsmod' to verify kernel modules.",
            )

        if "binder_linux" not in loaded_modules:
            error_message = (
                "\n========== HOST PREREQUISITE FAILED ==========\n"
                "MobileSandbox requires specific kernel modules"
                " that appear to be missing or not loaded.\n\n"
                "To fix this, please run the following commands"
                " on your Linux host:\n\n"
                "## Install required kernel modules\n"
                "sudo apt update"
                " && sudo apt install -y linux-modules-extra-`uname -r`\n"
                "sudo modprobe binder_linux"
                ' devices="binder,hwbinder,vndbinder"\n'
                "## (Optional) Load the ashmem driver for older kernels\n"
                "sudo modprobe ashmem_linux\n"
                "=================================================="
            )
            raise HostPrerequisiteError(error_message)

    if os_type == "Windows":
        try:
            result = subprocess.run(
                ["wsl", "lsmod"],
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )
            loaded_modules = result.stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            loaded_modules = ""
            logger.warning(
                "Could not execute 'wsl lsmod' to verify kernel modules.",
            )

        if "binder_linux" not in loaded_modules:
            error_message = (
                "\n========== HOST PREREQUISITE FAILED ==========\n"
                "MobileSandbox on Windows requires Docker Desktop "
                "with the WSL 2 backend.\n"
                "The required kernel modules seem to be missing "
                "in your WSL 2 environment.\n\n"
                "To fix this, please follow these steps:\n\n"
                "1. **Ensure Docker Desktop is using WSL 2**:\n"
                "   - Open Docker Desktop -> Settings -> General.\n"
                "   - Make sure 'Use the WSL 2 based engine' "
                "is checked.\n\n"
                "2. **Ensure WSL is installed and updated**:\n"
                "   - Open PowerShell or Command Prompt "
                "as Administrator.\n"
                "   - Run: wsl --install\n"
                "   - Run: wsl --update\n"
                "   (An update usually installs a recent Linux kernel "
                "with the required modules.)\n\n"
                "3. **Verify manually (Optional)**:\n"
                "   - After updating, run 'wsl lsmod | findstr binder' "
                "in your terminal.\n"
                "   - If it shows 'binder_linux', "
                "the issue should be resolved.\n"
                "=================================================="
            )
            raise HostPrerequisiteError(error_message)

    logger.info("Host environment check passed.")
