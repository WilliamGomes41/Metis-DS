"""Disposable, supervised urllib transport. No workflow or persistent authority.

The parent owns deadlines and reaps the worker; Linux kills it if the parent dies.
Only small transport observations use named files. Private requests/results use
anonymous descriptors, which the OS closes on process death. No provider cancellation is claimed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import http.client
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import HTTPHandler, HTTPSHandler, Request, build_opener

VERSION = 'bounded-model-call-v1'
MAX_RESPONSE_BYTES = 4_000_000
CLEANUP_SECONDS = 2.0


@dataclass(frozen=True)
class ModelCallLimits:
    connect: float = 10.0
    idle: float = 600.0
    total: float = 900.0
    attempt: float = 1800.0
    max_attempts: int = 4

    def record(self):
        return {'version': VERSION, **asdict(self), 'cleanup': CLEANUP_SECONDS, 'automatic_retries': 0}


def load_limits(environ: Mapping[str, str] | None = None) -> ModelCallLimits:
    env = os.environ if environ is None else environ
    names = {'connect':'METIS_LLM_CONNECT_TIMEOUT_SECONDS', 'idle':'METIS_LLM_IDLE_TIMEOUT_SECONDS',
             'total':'METIS_LLM_TOTAL_TIMEOUT_SECONDS', 'attempt':'METIS_PROCESSING_ATTEMPT_TIMEOUT_SECONDS',
             'max_attempts':'METIS_PROCESSING_MAX_ATTEMPTS'}
    defaults = ModelCallLimits()
    try:
        values = {key: float(env.get(name, getattr(defaults, key))) for key, name in names.items()}
        if not all(math.isfinite(n) and n > 0 for n in values.values()):
            raise ValueError()
        if not (values['connect'] <= values['idle'] <= values['total'] <= values['attempt'] - 60
                and values['attempt'] <= 3600 and values['max_attempts'].is_integer()
                and values['max_attempts'] <= 8):
            raise ValueError()
    except (ValueError, TypeError, OverflowError) as exc:
        from src.operations_console_v1 import ConsoleError
        raise ConsoleError('pre_review_llm_limits_invalid') from exc
    return ModelCallLimits(**{**values, 'max_attempts':int(values['max_attempts'])})


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


def _worker(directory: Path, parent_pid: int, request_fd: int, result_fd: int):
    # Arm before reading credentials/connecting; close the parent-death race.
    if sys.platform != 'linux':
        raise RuntimeError('bounded_model_transport_requires_linux')
    import ctypes
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL) != 0:
        raise OSError('parent_death_guard_failed')
    if os.getppid() != parent_pid:
        return
    with os.fdopen(request_fd, 'r', encoding='utf-8') as request_file:
        request = json.load(request_file)
    limits = ModelCallLimits(**request['limits'])
    status = {'phase':'connecting', 'last_activity':time.monotonic(), 'bytes_received':0}
    def observe(**values):
        status.update(values, last_activity=time.monotonic())
        _write(directory/'status.json', status)
    class Connection(http.client.HTTPConnection):
        def connect(self):
            super().connect()
            self.sock.settimeout(limits.idle)
            observe(phase='waiting_response')
    class SecureConnection(http.client.HTTPSConnection):
        def connect(self):
            super().connect()
            self.sock.settimeout(limits.idle)
            observe(phase='waiting_response')
    class Http(HTTPHandler):
        def http_open(self, req):
            return self.do_open(Connection, req)
    class Https(HTTPSHandler):
        def https_open(self, req):
            return self.do_open(SecureConnection, req, context=self._context)
    outcome = {}
    try:
        req = Request(request['url'], data=json.dumps(request['payload'], ensure_ascii=False).encode(),
                      headers=request['headers'], method='POST')
        # Redirects could replay private input/credentials to another authority.
        from urllib.request import HTTPRedirectHandler
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                raise HTTPError(req.full_url, 302, 'redirect_not_allowed', {}, None)
        with build_opener(Http(), Https(), NoRedirect()).open(req, timeout=limits.connect) as response:
            observe(phase='receiving', http_status=response.status)
            body = bytearray()
            while True:
                chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
                observe(bytes_received=len(body))
                if len(body) > MAX_RESPONSE_BYTES:
                    outcome = {'error':'pre_review_llm_output_limit_exceeded', 'category':'output_limit'}
                    break
            if not outcome:
                try:
                    value = json.loads(body.decode('utf-8'))
                    if not isinstance(value, dict):
                        raise ValueError()
                    outcome = {'response':value}
                except (ValueError, UnicodeError):
                    outcome = {'error':'pre_review_llm_response_invalid','category':'invalid_response'}
    except HTTPError as exc:
        outcome = {'error':'pre_review_llm_provider_unavailable','category':'provider_error','http_status':exc.code}
    except (URLError, OSError, TimeoutError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        connecting = status['phase'] == 'connecting'
        category = ('connection_timeout' if connecting else 'inactivity_timeout') if isinstance(reason, TimeoutError) else 'connection_failed' if connecting else 'provider_error'
        outcome = {'error':'pre_review_llm_'+category if category in {'connection_timeout','inactivity_timeout','connection_failed'} else 'pre_review_llm_provider_unavailable', 'category':category}
    except Exception:
        outcome = {'error':'pre_review_llm_provider_unavailable','category':'transport_worker_failed'}
    with os.fdopen(result_fd, 'w', encoding='utf-8') as result_file:
        json.dump(outcome, result_file, ensure_ascii=False)
    _write(directory/'result.json', {'ready':True})


def post_json(url: str, headers: dict, payload: dict, limits: ModelCallLimits, *, observation: dict | None = None):
    from src.operations_console_v1 import ConsoleError
    if sys.platform != 'linux':
        raise ConsoleError('pre_review_llm_transport_unsupported')
    started = time.monotonic()
    record = {'version':VERSION, 'call_id':(observation or {}).get('call_id') or uuid.uuid4().hex, 'limits':limits.record(), 'started_at':_utc(),
              'external_cancellation':'unknown', 'retry_not_before':None}
    status = {}
    error = None
    process = None
    with (tempfile.TemporaryDirectory(prefix='metis-model-') as folder,
          tempfile.TemporaryFile(mode='w+b') as request_file,
          tempfile.TemporaryFile(mode='w+b') as result_file):
        directory = Path(folder)
        # Anonymous descriptors disappear even on SIGKILL; private input/output
        # never remains in a named file, argv, status observations or logs.
        request_file.write(json.dumps({'url':url,'headers':headers,'payload':payload,'limits':asdict(limits)}, ensure_ascii=False).encode())
        request_file.seek(0)
        try:
            process = subprocess.Popen([sys.executable, '-m', 'src.bounded_model_call_v1', str(directory), str(os.getpid()), str(request_file.fileno()), str(result_file.fileno())],
                                       pass_fds=(request_file.fileno(), result_file.fileno()), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            record['transport_pid'] = process.pid
            while True:
                elapsed = time.monotonic() - started
                status = _read(directory/'status.json')
                phase = status.get('phase', 'connecting')
                if elapsed >= limits.total:
                    raise ConsoleError('pre_review_llm_processing_timeout')
                if phase == 'connecting' and elapsed >= limits.connect:
                    raise ConsoleError('pre_review_llm_connection_timeout')
                if phase != 'connecting' and time.monotonic() - status['last_activity'] >= limits.idle:
                    raise ConsoleError('pre_review_llm_inactivity_timeout')
                ready = _read(directory/'result.json')
                if ready:
                    result_file.seek(0)
                    result = json.load(result_file)
                    # Reading/decoding the complete result is within the budget too.
                    if time.monotonic() - started >= limits.total:
                        raise ConsoleError('pre_review_llm_processing_timeout')
                    if result.get('error'):
                        record['category'] = result['category']
                        record['http_status'] = result.get('http_status')
                        raise ConsoleError(result['error'])
                    record.update(category='success', external_cancellation='not_requested', http_status=status.get('http_status'))
                    return result['response']
                if process.poll() is not None:
                    raise ConsoleError('pre_review_llm_provider_unavailable')
                time.sleep(min(.02, max(.001, limits.total - elapsed)))
        except Exception as exc:
            error = exc
            code = getattr(exc, 'code', 'pre_review_llm_provider_unavailable')
            record.setdefault('category', {'pre_review_llm_processing_timeout':'total_timeout',
                 'pre_review_llm_connection_timeout':'connection_timeout',
                 'pre_review_llm_inactivity_timeout':'inactivity_timeout'}.get(code, 'provider_error'))
            record['error_code'] = code
            if record['category'] in {'connection_timeout','inactivity_timeout','total_timeout','provider_error'}:
                from datetime import timedelta
                record['retry_not_before'] = (datetime.fromisoformat(record['started_at']) + timedelta(seconds=limits.total+CLEANUP_SECONDS)).isoformat()
            raise
        finally:
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=CLEANUP_SECONDS / 2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=CLEANUP_SECONDS / 2)
                else:
                    process.wait()
                record['local_worker_reaped'] = True
            record.update(finished_at=_utc(), elapsed_seconds=time.monotonic()-started,
                          bytes_received=status.get('bytes_received',0), phase=status.get('phase','connecting'))
            if observation is not None:
                observation.update(record)
            if error is not None:
                error.model_call_observation = record


if __name__ == '__main__':
    _worker(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
