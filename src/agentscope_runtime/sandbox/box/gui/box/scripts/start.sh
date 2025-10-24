#!/bin/bash

uvicorn app:app --app-dir=/agentscope_runtime --host=0.0.0.0 --port 8000 &
wait
