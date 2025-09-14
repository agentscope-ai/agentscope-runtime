# -*- coding: utf-8 -*-
from fastapi import FastAPI


def build_app() -> FastAPI:
    return FastAPI(title="Example FastAPI App")


