# -*- coding: utf-8 -*-
"""FastAPI templates management and rendering."""

import os
from typing import Dict, Any
from jinja2 import Template, Environment, FileSystemLoader
from ..deployment_modes import DeploymentMode


class FastAPITemplateManager:
    """Manager for FastAPI deployment templates."""

    def __init__(self):
        """Initialize template manager."""
        self.template_dir = os.path.join(
            os.path.dirname(__file__),
        )
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_standalone_template(
        self,
        agent_name: str,
        endpoint_path: str = "/process",
        deployment_mode: str = DeploymentMode.STANDALONE,
        **kwargs,
    ) -> str:
        """Render the standalone deployment template.

        Args:
            agent_name: Name of the agent variable
            endpoint_path: API endpoint path
            deployment_mode: Deployment mode (standalone or detached_process)
            **kwargs: Additional template variables

        Returns:
            Rendered template content
        """
        template = self.env.get_template("standalone_main.py.j2")
        return template.render(
            agent_name=agent_name,
            endpoint_path=endpoint_path,
            deployment_mode=deployment_mode,
            **kwargs,
        )

    def render_detached_script_template(
        self,
        endpoint_path: str = "/process",
        host: str = "127.0.0.1",
        port: int = 8000,
        stream_enabled: bool = True,
        response_type: str = "sse",
        runner_code: str = "",
        func_code: str = "",
        services_config: str = "",
        **kwargs,
    ) -> str:
        """Render the detached process script template.

        Args:
            endpoint_path: API endpoint path
            host: Host to bind to
            port: Port to bind to
            stream_enabled: Enable streaming responses
            response_type: Response type
            runner_code: Code to setup runner
            func_code: Code to setup custom function
            services_config: Services configuration code
            **kwargs: Additional template variables

        Returns:
            Rendered template content
        """
        template = self.env.get_template("detached_script.py.j2")
        return template.render(
            endpoint_path=endpoint_path,
            host=host,
            port=port,
            stream_enabled=str(stream_enabled).lower(),
            response_type=response_type,
            runner_code=runner_code,
            func_code=func_code,
            services_config=services_config,
            **kwargs,
        )

    def render_template_from_string(
        self,
        template_string: str,
        **variables,
    ) -> str:
        """Render a template from string.

        Args:
            template_string: Template content as string
            **variables: Template variables

        Returns:
            Rendered template content
        """
        template = Template(template_string)
        return template.render(**variables)

    def create_services_config_code(
        self,
        services_config: Dict[str, Any],
    ) -> str:
        """Create Python code for services configuration.

        Args:
            services_config: Services configuration dictionary

        Returns:
            Python code as string
        """
        lines = []

        if "memory" in services_config:
            memory_config = services_config["memory"]
            lines.append(f"memory=ServiceConfig(")
            lines.append(
                f"    provider='{memory_config.get('provider', 'in_memory')}',",
            )
            if memory_config.get("config"):
                lines.append(f"    config={memory_config['config']}")
            lines.append(f"),")

        if "session_history" in services_config:
            session_config = services_config["session_history"]
            lines.append(f"session_history=ServiceConfig(")
            lines.append(
                f"    provider='{session_config.get('provider', 'in_memory')}',",
            )
            if session_config.get("config"):
                lines.append(f"    config={session_config['config']}")
            lines.append(f"),")

        return "\n".join(lines)

    def get_template_list(self) -> list:
        """Get list of available templates.

        Returns:
            List of template filenames
        """
        if not os.path.exists(self.template_dir):
            return []

        templates = []
        for filename in os.listdir(self.template_dir):
            if filename.endswith(".j2"):
                templates.append(filename)

        return templates

    def validate_template_variables(
        self,
        template_name: str,
        variables: Dict[str, Any],
    ) -> Dict[str, list]:
        """Validate template variables.

        Args:
            template_name: Name of the template
            variables: Variables to validate

        Returns:
            Dictionary with 'missing' and 'extra' keys containing lists
        """
        # This is a basic implementation
        # In practice, you might want to parse the template to find required variables
        required_vars = {
            "standalone_main.py.j2": ["agent_name", "endpoint_path"],
        }

        required = required_vars.get(template_name, [])
        provided = list(variables.keys())

        missing = [var for var in required if var not in provided]
        extra = [var for var in provided if var not in required]

        return {"missing": missing, "extra": extra}
