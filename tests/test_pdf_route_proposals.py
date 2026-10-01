"""Real PDF geometry yields proposals, never automatic publication proof.

# release-control-evidence: kwaliteit
# release-control-evidence: beschikbaarheid
"""
import fitz
import pytest

from tests.test_decision_graph_chain import _console, _accounts, _ingest_boom, policy


def route_pdf(*, arrow=True, reverse=False, label="", disconnected=False):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((70, 80), "Bespreek de situatie.")
        page.insert_text((70, 220), "Maak een afspraak.")
        if label:
            page.insert_text((116, 140), label)
        shape = page.new_shape()
        shape.draw_line((110, 90), (110, 195 if not disconnected else 115))
        if arrow:
            y = 90 if reverse else 195
            dy = 8 if reverse else -8
            shape.draw_line((104, y + dy), (110, y))
            shape.draw_line((116, y + dy), (110, y))
        shape.finish(closePath=False)
        shape.commit()
        return doc.tobytes()


def proposal(console, accounts, **kwargs):
    sid = _ingest_boom(console, accounts, data=route_pdf(**kwargs), filename="routes.pdf",
        content_type="application/pdf", named_reviewers=[], review_policy=policy(accounts))["snapshot_id"]
    return sid, console._envelope(sid)


@pytest.mark.parametrize("reverse", [False, True])
def test_real_arrow_direction_and_literal_non_boolean_label(tmp_path, reverse):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid, env = proposal(console, accounts, reverse=reverse, label="Verbeterd")
    assert len(env["decision_graph_proposals"]) == 1
    route = env["decision_graph_proposals"][0]
    objects = {o["object_id"]: o for o in console.snapshot_objects(sid)}
    assert objects[route["from"]]["content"]["clean_text"] == ("Maak een afspraak." if reverse else "Bespreek de situatie.")
    assert route["label"] == "Verbeterd"
    assert route["kind"] == "answer"
    assert "direction_unverified" not in route["uncertainties"]
    assert "human_route_confirmation_required" in route["uncertainties"]
    assert env["decision_graph"]["unresolved"]
    assert not console.consider_publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)["publish_allowed"]


def test_no_arrow_stays_uncertain_and_disconnected_line_cannot_invent_route(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    _, env = proposal(console, accounts, arrow=False)
    assert "direction_unverified" in env["decision_graph_proposals"][0]["uncertainties"]
    _, disconnected = proposal(console, accounts, arrow=False, disconnected=True)
    assert disconnected["decision_graph_proposals"] == []


def test_curved_vector_keeps_original_control_points_and_uncertainty(tmp_path):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((70, 80), "Eerste stap.")
        page.insert_text((70, 220), "Volgende stap.")
        shape = page.new_shape()
        shape.draw_bezier((100, 90), (160, 110), (160, 170), (100, 200))
        shape.finish(closePath=False)
        shape.commit()
        data = doc.tobytes()
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = _ingest_boom(console, accounts, data=data, filename="curve.pdf", content_type="application/pdf",
        named_reviewers=[], review_policy=policy(accounts))["snapshot_id"]
    env = console._envelope(sid)
    graphic = next(v for v in env["decision_graph_evidence"]["items"].values() if v["kind"] == "graphic")
    assert graphic["curves"][0] == [[100, 90], [160, 110], [160, 170], [100, 200]]
    assert "curved_path_approximation" in env["decision_graph_proposals"][0]["uncertainties"]
