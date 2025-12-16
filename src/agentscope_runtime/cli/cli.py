# -*- coding: utf-8 -*-
"""AgentScope Runtime CLI - Main entry point."""
# pylint: disable=no-value-for-parameter

import os

import click

# Import command groups (to be registered below)
from agentscope_runtime.cli.commands import (
    chat,
    run,
    web,
    deploy,
    list_cmd,
    status,
    stop,
    invoke,
    sandbox,
)
from agentscope_runtime.version import __version__

# Set default environment variable for trace console output
# This must be set BEFORE importing any runtime modules
# Individual commands can override this for verbose mode
if "TRACE_ENABLE_LOG" not in os.environ:
    os.environ.setdefault("TRACE_ENABLE_LOG", "false")


@click.group()
@click.version_option(version=__version__, prog_name="agentscope")
@click.pass_context
def cli(ctx):
    """
    AgentScope Runtime - Unified CLI for agent lifecycle management.

    Manage your agent development, deployment, and runtime operations
    from a single command.

    """
    # Ensure context object exists
    ctx.ensure_object(dict)


# Register commands
cli.add_command(chat.chat)
cli.add_command(run.run)
cli.add_command(web.web)
cli.add_command(deploy.deploy)
cli.add_command(list_cmd.list_deployments)
cli.add_command(status.status)
cli.add_command(stop.stop)
cli.add_command(invoke.invoke)
cli.add_command(sandbox.sandbox)


def main():
    """Entry point for console script."""
    cli(obj={})


if __name__ == "__main__":
    main()
