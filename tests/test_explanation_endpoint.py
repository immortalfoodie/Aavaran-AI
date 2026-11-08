import pytest
from fastapi.testclient import TestClient
from api.main import app
from engine.store import global_result_store

def test_explanation_background_and_polling():
    client = TestClient(app)
    
    # 1. Submit kisan recommendation
    payload = {
        "mode": "kisan",
        "input": {
            "commodity_id": "veg.potato.solanum_tuberosum",
            "state": {"whole": True},
        },
        "locale": "en-IN",
    }
    res = client.post("/api/v1/recommend", json=payload)
    assert res.status_code == 200
    data = res.json()
    result_id = data["result_id"]
    
    # In Kisan mode, the initial recommendation has kisan_instruction set to None
    if data.get("recommendation"):
        assert data["recommendation"]["kisan_instruction"] is None
        
    # 2. Poll explanation endpoint
    poll_res = client.get(f"/api/v1/recommend/{result_id}/explanation")
    assert poll_res.status_code == 200
    poll_data = poll_res.json()
    
    # In TestClient, BackgroundTasks execute synchronously after response
    assert poll_data["status"] == "ready"
    assert "kisan_instruction" in poll_data["explanation"]
    assert len(poll_data["explanation"]["kisan_instruction"]) > 0

def test_explanation_polling_pending_or_missing():
    client = TestClient(app)
    poll_res = client.get("/api/v1/recommend/res_non_existent/explanation")
    assert poll_res.status_code == 200
    assert poll_res.json()["status"] == "pending"


def test_kisan_instruction_potato_common_and_marathi_translation():
    client = TestClient(app)
    payload = {
        "mode": "kisan",
        "input": {
            "commodity_id": "veg.potato.solanum_tuberosum",
            "state": {"whole": True},
        },
        "locale": "en-IN",
    }
    res = client.post("/api/v1/recommend", json=payload)
    assert res.status_code == 200
    result_id = res.json()["result_id"]

    # 1. English explanation must have "potato" and NEVER "solanum tuberosum"
    en_res = client.get(f"/api/v1/recommend/{result_id}/explanation?locale=en-IN")
    assert en_res.status_code == 200
    en_data = en_res.json()
    assert en_data["status"] == "ready"
    en_instr = en_data["explanation"]["kisan_instruction"]
    assert "potato" in en_instr.lower()
    assert "solanum tuberosum" not in en_instr.lower()

    # 2. Dynamic Marathi locale request must produce Marathi text with "बटाटा"
    mr_res = client.get(f"/api/v1/recommend/{result_id}/explanation?locale=mr-IN")
    assert mr_res.status_code == 200
    mr_data = mr_res.json()
    assert mr_data["status"] == "ready"
    mr_instr = mr_data["explanation"]["kisan_instruction"]
    assert "बटाटा" in mr_instr
    assert "दिवस" in mr_instr
    assert "solanum tuberosum" not in mr_instr.lower()

    # 3. Dynamic Hindi locale request must produce Hindi text with "आलू"
    hi_res = client.get(f"/api/v1/recommend/{result_id}/explanation?locale=hi-IN")
    assert hi_res.status_code == 200
    hi_data = hi_res.json()
    assert hi_data["status"] == "ready"
    hi_instr = hi_data["explanation"]["kisan_instruction"]
    assert "आलू" in hi_instr
    assert "दिन" in hi_instr
    assert "solanum tuberosum" not in hi_instr.lower()

