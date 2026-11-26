"""Authenticated control API for the existing source-processing owner."""
import asyncio
import json

from fastapi import Request
from fastapi.responses import JSONResponse
from src.operations_console_v1 import ConsoleError
from src.vorming import prose_transition_v1 as domain


def install(app, console, require):
    @app.get('/source-selection/transition')
    async def read(request: Request, document: str):
        actor = require(request)
        result = await asyncio.to_thread(domain.inventory, console,
            actor_id=actor['account_id'], snapshot_id=document)
        return JSONResponse(result, headers={'Cache-Control': 'no-store'})

    @app.post('/source-selection/transition')
    async def stop(request: Request):
        actor = require(request)
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse({'error': 'prose_transition_command_invalid'}, status_code=422)
        if not isinstance(payload, dict) or set(payload) != {
                'snapshot_id', 'attempt_id', 'command_id', 'expected_revision', 'reason'}:
            return JSONResponse({'error': 'prose_transition_command_invalid'}, status_code=422)
        try:
            result = await asyncio.to_thread(domain.stop, console, actor_id=actor['account_id'], **payload)
        except ConsoleError as error:
            if error.code in {'not_authenticated', 'researcher_role_required', 'reviewer_not_named_on_snapshot'}:
                raise
            return JSONResponse({'error': error.code}, status_code=409, headers={'Cache-Control': 'no-store'})
        return JSONResponse(result, headers={'Cache-Control': 'no-store'})
