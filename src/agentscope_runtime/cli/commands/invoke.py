# -*- coding: utf-8 -*-
"""agentscope invoke command - Invoke a deployed agent."""
# pylint: disable=no-value-for-parameter

import click

from agentscope_runtime.cli.commands.chat import chat
from agentscope_runtime.cli.utils.console import echo_info


@click.command()
@click.argument("deploy_id", required=True)
@click.option(
    "--query",
    "-q",
    help="Single query to execute (non-interactive mode)",
    default=None,
)
@click.option(
    "--session-id",
    help="Session ID for conversation continuity",
    default=None,
)
@click.option(
    "--user-id",
    help="User ID for the session",
    default="default_user",
)
def invoke(deploy_id: str, query: str, session_id: str, user_id: str):
    """
    Invoke a deployed agent (alias for 'run' with deployment ID).

    This is a convenience command that is equivalent to:
    $ agentscope chat <deploy_id> [options]

    Examples:
    \b
    # Interactive mode
    $ agentscope invoke local_20250101_120000_abc123

    # Single query
    $ agentscope invoke local_20250101_120000_abc123 --query "Hello"
    """
    echo_info(f"Invoking deployment: {deploy_id}")

    # Delegate to run command
    ctx = click.get_current_context()
    ctx.invoke(
        chat,
        source=deploy_id,
        query=query,
        session_id=session_id,
        user_id=user_id,
    )


if __name__ == "__main__":
    invoke()
