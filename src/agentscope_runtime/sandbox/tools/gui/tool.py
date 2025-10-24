# -*- coding: utf-8 -*-
# flake8: noqa: E501
# pylint: disable=line-too-long
from typing import Dict

from ..sandbox_tool import SandboxTool


class ComputerUseTool(SandboxTool):
    """
    Use a mouse and keyboard to interact with a computer, and take screenshots.
    """

    _name: str = "computer"
    _sandbox_type: str = "gui"
    _tool_type: str = "computer_use"
    _schema: Dict = {
        "name": "computer",
        "description": (
            "Use a mouse and keyboard to interact with a computer, and take screenshots.\n"
            "* This is an interface to a desktop GUI. You do not have access to a terminal or applications menu. You must click on desktop icons to start applications.\n"
            "* Always prefer using keyboard shortcuts rather than clicking, where possible.\n"
            "* If you see boxes with two letters in them, typing these letters will click that element. Use this instead of other shortcuts or clicking, where possible.\n"
            "* Some applications may take time to start or process actions, so you may need to wait and take successive screenshots to see the results of your actions. E.g. if you click on Firefox and a window doesn't open, try taking another screenshot.\n"
            "* Whenever you intend to move the cursor to click on an element like an icon, you should consult a screenshot to determine the coordinates of the element before moving the cursor.\n"
            "* If you tried clicking on a program or link but it failed to load, even after waiting, try adjusting your cursor position so that the tip of the cursor visually falls on the element that you want to click.\n"
            "* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the element. Don't click boxes on their edges unless asked."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "key",
                        "type",
                        "mouse_move",
                        "left_click",
                        "left_click_drag",
                        "right_click",
                        "middle_click",
                        "double_click",
                        "get_screenshot",
                        "get_cursor_position",
                    ],
                    "description": (
                        "The action to perform. The available actions are:\n"
                        "* key: Press a key or key-combination on the keyboard.\n"
                        "* type: Type a string of text on the keyboard.\n"
                        "* get_cursor_position: Get the current (x, y) pixel coordinate of the cursor on the screen.\n"
                        "* mouse_move: Move the cursor to a specified (x, y) pixel coordinate on the screen.\n"
                        "* left_click: Click the left mouse button.\n"
                        "* left_click_drag: Click and drag the cursor to a specified (x, y) pixel coordinate on the screen.\n"
                        "* right_click: Click the right mouse button.\n"
                        "* middle_click: Click the middle mouse button.\n"
                        "* double_click: Double-click the left mouse button.\n"
                        "* get_screenshot: Take a screenshot of the screen."
                    ),
                },
                "coordinate": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type or key command to execute",
                },
            },
            "required": ["action"],
        },
    }


computer_use = ComputerUseTool()
