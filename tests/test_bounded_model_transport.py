"""Actual bounded socket waiting, process cleanup and safe evidence.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
import pytest
from src.bounded_model_call_v1 import ModelCallLimits, load_limits, post_json
from src.operations_console_v1 import ConsoleError
from tests.model_transport_support import peer


@pytest.mark.parametrize('case,code',[
 ('connect','pre_review_llm_connection_timeout'),('silent','pre_review_llm_inactivity_timeout'),
 ('drip','pre_review_llm_processing_timeout'),('late','pre_review_llm_processing_timeout')])
def test_real_transport_wait_is_bounded_even_with_trickle(case,code,monkeypatch):
    for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:
        monkeypatch.delenv(key,raising=False)
    limits=ModelCallLimits(connect=.7,idle=.2,total=.8)
    options={'connect':{'tls_stall':True},'silent':{'delay':3},
             'drip':{'drip':.06,'body':b'{"ok":"'+b'x'*100+b'"}'},'late':{'delay':1.2}}[case]
    if case=='connect':limits=ModelCallLimits(connect=.2,idle=.5,total=.8)
    # Drip proves the total deadline independently of runner scheduling jitter.
    # Silent proves the separate idle deadline; drip/late must not race that timer.
    if case in {'drip','late'}:limits=ModelCallLimits(connect=.5,idle=2,total=.8)
    observation={}
    with peer(**options) as (url,received):
        started=time.monotonic()
        with pytest.raises(ConsoleError) as error:
            post_json(url,{'Authorization':'private-credential'},{'input':'private-document'},limits,observation=observation)
        assert error.value.code==code
        assert time.monotonic()-started < limits.total+2.0+.3
        assert received.is_set()
        assert observation['local_worker_reaped']
        with pytest.raises(ProcessLookupError):os.kill(observation['transport_pid'],0)
        assert observation['external_cancellation']=='unknown'
        assert 'private-' not in str(observation)
        if case=='drip':assert observation['bytes_received']>2


def test_timely_success_has_complete_response_and_no_background_worker(monkeypatch):
    monkeypatch.setenv('NO_PROXY','127.0.0.1')
    with peer(body=b'{"ok":true,"numbers":[1,2,3]}') as (url,_):
        observation={}
        assert post_json(url,{}, {},ModelCallLimits(connect=1,idle=1,total=2),observation=observation)=={'ok':True,'numbers':[1,2,3]}
        assert observation['category']=='success'
        assert observation['bytes_received']==len(b'{"ok":true,"numbers":[1,2,3]}')
        assert observation['local_worker_reaped']


def test_parent_process_death_terminates_transport_worker(monkeypatch,tmp_path):
    env={**os.environ,'NO_PROXY':'127.0.0.1'}
    with peer(delay=5) as (url,received):
        code='from src.bounded_model_call_v1 import *;post_json('+repr(url)+',{}, {},ModelCallLimits(connect=2,idle=30,total=30))'
        process=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            assert received.wait(5)
            assert process.poll() is None, "transport parent exited before test kill"
            children=[]
            for stat in Path("/proc").glob("[0-9]*/stat"):
                try:
                    fields=stat.read_text().rsplit(") ",1)[1].split()
                    if int(fields[1])==process.pid:children.append(stat.parent.name)
                except (FileNotFoundError,ProcessLookupError):pass
            assert len(children)==1
            process.kill();process.wait(5)
            for _ in range(100):
                child=Path(f"/proc/{children[0]}/stat")
                try:
                    state=child.read_text().rsplit(") ",1)[1].split()[0]
                except (FileNotFoundError,ProcessLookupError):
                    # Exit can remove procfs metadata before or during read.
                    break
                if state=="Z":break
                time.sleep(.02)
            else:pytest.fail('orphan transport process remains alive')
        finally:
            if process.poll() is None:process.kill();process.wait(5)


@pytest.mark.parametrize('name,value', [('METIS_LLM_TOTAL_TIMEOUT_SECONDS','nan'),
 ('METIS_LLM_CONNECT_TIMEOUT_SECONDS','-1'),('METIS_LLM_IDLE_TIMEOUT_SECONDS','901'),
 ('METIS_PROCESSING_MAX_ATTEMPTS','1.5'),('METIS_PROCESSING_ATTEMPT_TIMEOUT_SECONDS','900')])
def test_invalid_bounds_fail_closed(name,value):
    with pytest.raises(ConsoleError,match='pre_review_llm_limits_invalid'):load_limits({name:value})


def test_defaults_allow_large_silent_generation_but_have_a_total_bound():
    assert load_limits({})==ModelCallLimits(connect=10,idle=600,total=900,attempt=1800,max_attempts=4)
