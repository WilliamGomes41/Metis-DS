"""Real annotation/build routes; hold only worker scheduling to observe running state."""
from threading import Event

from src.vorming import human_annotation_build_v1 as builds
from tests.browser_annotation_suggestions_fixture import app


release_build = Event()
execute = builds.execute


def held_execute(*args, **kwargs):
    if not release_build.wait(30):
        raise RuntimeError('synthetic_build_gate_timeout')
    return execute(*args, **kwargs)


builds.execute = held_execute


@app.post('/browser-release-build')
def release():
    release_build.set()
    return {'released': True}
