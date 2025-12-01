"""as-runtime sandbox command - Sandbox management commands."""

import click
import sys
import subprocess

from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
    echo_warning,
)


@click.group()
def sandbox():
    """
    Sandbox management commands.

    This consolidates existing sandbox commands under a unified CLI.

    Available commands:
    \b
    - mcp: Start MCP server for sandbox
    - server: Start sandbox manager server
    - build: Build sandbox environments
    """
    pass


@sandbox.command()
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def mcp(args):
    """
    Start MCP server for sandbox (delegates to runtime-sandbox-mcp).

    Examples:
    \b
    $ as-runtime sandbox mcp
    $ as-runtime sandbox mcp --help
    """
    try:
        # Delegate to existing command
        cmd = ["runtime-sandbox-mcp"] + list(args)
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except FileNotFoundError:
        echo_error("runtime-sandbox-mcp command not found")
        echo_info("Make sure agentscope-runtime is properly installed")
        sys.exit(1)
    except Exception as e:
        echo_error(f"Failed to run MCP server: {e}")
        sys.exit(1)


@sandbox.command()
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def server(args):
    """
    Start sandbox manager server (delegates to runtime-sandbox-server).

    Examples:
    \b
    $ as-runtime sandbox server
    $ as-runtime sandbox server --help
    """
    try:
        # Delegate to existing command
        cmd = ["runtime-sandbox-server"] + list(args)
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except FileNotFoundError:
        echo_error("runtime-sandbox-server command not found")
        echo_info("Make sure agentscope-runtime is properly installed")
        sys.exit(1)
    except Exception as e:
        echo_error(f"Failed to run sandbox server: {e}")
        sys.exit(1)


@sandbox.command()
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def build(args):
    """
    Build sandbox environments (delegates to runtime-sandbox-builder).

    Examples:
    \b
    $ as-runtime sandbox build
    $ as-runtime sandbox build --help
    """
    try:
        # Delegate to existing command
        cmd = ["runtime-sandbox-builder"] + list(args)
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except FileNotFoundError:
        echo_error("runtime-sandbox-builder command not found")
        echo_info("Make sure agentscope-runtime is properly installed")
        sys.exit(1)
    except Exception as e:
        echo_error(f"Failed to run sandbox builder: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sandbox()