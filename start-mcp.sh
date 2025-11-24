#!/bin/bash
cd /home/noname/code/FIWARE-MCP-Server
/home/noname/.local/bin/uv run --with "requests>=2.31.0" --with "fastmcp>=0.3.0" --with "pysmartdatamodels" server.py
