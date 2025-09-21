# -*- coding: utf-8 -*-
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    system_prompt: Optional[str] = ""
    user_prompt: Optional[str] = ""
    model_config = ConfigDict(extra="allow")
