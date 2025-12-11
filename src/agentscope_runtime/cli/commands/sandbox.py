# -*- coding: utf-8 -*-
"""agentscope sandbox command - Sandbox management commands."""

import sys

import click

from agentscope_runtime.cli.utils.console import (
    echo_error,
    echo_info,
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


@sandbox.command()
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def mcp(args):
    """
    Start MCP server for sandbox (delegates to runtime-sandbox-mcp).

    Examples:
    \b
    $ agentscope sandbox mcp
    $ agentscope sandbox mcp --help
    """
    try:
        from agentscope_runtime.sandbox.mcp_server import main as mcp_main

        # Set sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ["runtime-sandbox-mcp"] + list(args)

        try:
            mcp_main()
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    except ImportError as e:
        echo_error(f"Failed to import MCP server module: {e}")
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
    $ agentscope sandbox server
    $ agentscope sandbox server --help
    """
    try:
        from agentscope_runtime.sandbox.manager.server.app import (
            main as server_main,
        )

        # Set sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ["runtime-sandbox-server"] + list(args)

        try:
            server_main()
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    except ImportError as e:
        echo_error(f"Failed to import sandbox server module: {e}")
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
    $ agentscope sandbox build
    $ agentscope sandbox build --help
    """
    try:
        from agentscope_runtime.sandbox.build import main as builder_main

        # Set sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ["runtime-sandbox-builder"] + list(args)

        try:
            builder_main()
        finally:
            # Restore original sys.argv
            sys.argv = original_argv
    except ImportError as e:
        echo_error(f"Failed to import sandbox builder module: {e}")
        echo_info("Make sure agentscope-runtime is properly installed")
        sys.exit(1)
    except Exception as e:
        echo_error(f"Failed to run sandbox builder: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sandbox()
