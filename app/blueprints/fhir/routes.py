"""FHIR R4 stub: POST /fhir/Patient.

This is intentionally minimal — a full R4 mapping (Condition, Observation,
Encounter, etc.) is Phase 2. The endpoint exists so an external EHR can
push a Patient resource and we can acknowledge.
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)
bp = Blueprint("fhir", __name__)


@bp.post("/Patient")
def receive_patient():
    if not request.is_json:
        return jsonify({"resourceType": "OperationOutcome", "issue": [
            {"severity": "error", "code": "required", "diagnostics": "Expected application/json"}
        ]}), 400
    bundle = request.get_json(silent=True) or {}
    # Best-effort: extract name and a few fields. Real mapping is Phase 2.
    name_field = bundle.get("name", [{}])
    family = ""
    given = ""
    if name_field and isinstance(name_field, list):
        first = name_field[0]
        family = first.get("family", "")
        given_list = first.get("given", [])
        given = " ".join(given_list) if isinstance(given_list, list) else ""
    full_name = f"{given} {family}".strip() or "Unknown"
    log.info(f"FHIR: received Patient resource for '{full_name}' (id={bundle.get('id')})")
    return jsonify({
        "resourceType": "Patient",
        "id": bundle.get("id"),
        "acknowledged": True,
        "name": full_name,
    }), 201
