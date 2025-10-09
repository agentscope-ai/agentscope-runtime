# -*- coding: utf-8 -*-
from typing import AsyncGenerator
from openai.types.chat import ChatCompletionChunk


class BaseLLM:
    base_url = None

    def __init__(self, model_name: str, **kwargs):
        self.client = None
        self.async_client = None
        self.model_name = model_name
        self.kwargs = kwargs

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate a response from the Qwen LLM model.

        Args:
            prompt (str): The prompt to generate a response for.
            **kwargs: Additional keyword arguments to pass to the model.

        Returns:
            str: The generated response.
        """
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            **kwargs,
        )
        return response.choices[0].message.content

    def chat(self, messages, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content

    async def chat_stream(
        self,
        messages,
        tools=None,
        **kwargs,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        # call model
        if self.async_client is not None:
            # Use async client for non-blocking streaming
            generator = await self.async_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                stream=True,
                **kwargs,
            )
            async for chunk in generator:
                yield chunk
        else:
            # Switch back to the sync method
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                stream=True,
                **kwargs,
            )
            for chunk in completion:
                yield chunk
