"""MET-13 (#879): as-is karakterisering van de vormingsroute per bron.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

Legt het huidige gedrag vast dat docs/change-contracts/met-13-r46-route-binding-design.md
als gat tegen PROTOCOL §5.4 N1–N3 beschrijft: een nieuwe poging op dezelfde bron
neemt de actuele omgevingsmodus over in plaats van een eenmalig gebonden route.
Wijzig deze test alleen samen met de implementatie van de routebinding.
"""
from src.operations_console_v1 import ConsoleError
from tests.test_resv1_reservation_configuration import _attempts, _reextract_ready


def test_new_attempt_takes_current_environment_mode_not_the_first_route(tmp_path, *, production_console):
    console, sid, actor = _reextract_ready(tmp_path, production_console=production_console)
    [first] = _attempts(console, sid, 'ingest')
    real = console._processing_configuration_reader
    console._processing_configuration_reader = lambda: {**real(), 'mode': 'switched-environment-mode'}
    try:
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    except ConsoleError:
        pass  # uitkomst irrelevant: de reservering is duurzaam
    [attempt] = _attempts(console, sid, 'reextract')
    assert first['processing_configuration']['mode'] != 'switched-environment-mode'
    assert attempt['processing_configuration']['mode'] == 'switched-environment-mode'
    assert 'formation_route' not in console._envelope(sid)
