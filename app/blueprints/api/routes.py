"""Public JSON API: POST /v1/predict."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, request
from pydantic import BaseModel, Field, ValidationError

from ...extensions import db
from ...models import Patient, Prediction
from ...predict import HeartFeatures, Predictor

bp = Blueprint("api", __name__)


class PredictRequest(BaseModel):
    name: str | None = None
    patient_id: int | None = None
    Age: float = Field(..., ge=0, le=120)
    RestingBP: float = Field(..., ge=0, le=300)
    Cholesterol: float = Field(..., ge=0, le=1000)
    FastingBS: int = Field(..., ge=0, le=1)
    MaxHR: float = Field(..., ge=0, le=300)
    Oldpeak: float = Field(..., ge=-5, le=10)
    Sex: str = Field(..., pattern="^[MF]$")
    ChestPainType: str = Field(..., pattern="^(ATA|NAP|ASY|TA)$")
    RestingECG: str = Field(..., pattern="^(Normal|ST|LVH)$")
    ExerciseAngina: str = Field(..., pattern="^[NY]$")
    ST_Slope: str = Field(..., pattern="^(Up|Flat|Down)$")


def _validation_error_response(err: ValidationError):
    return jsonify({"error": "validation_error", "details": err.errors()}), 400


@bp.post("/predict")
def predict():
    if not request.is_json:
        return jsonify({"error": "bad_request", "message": "Expected application/json"}), 400

    try:
        payload = PredictRequest.model_validate(request.get_json())
    except ValidationError as err:
        return _validation_error_response(err)

    features = HeartFeatures(
        Age=payload.Age,
        RestingBP=payload.RestingBP,
        Cholesterol=payload.Cholesterol,
        FastingBS=payload.FastingBS,
        MaxHR=payload.MaxHR,
        Oldpeak=payload.Oldpeak,
        Sex=payload.Sex,
        ChestPainType=payload.ChestPainType,
        RestingECG=payload.RestingECG,
        ExerciseAngina=payload.ExerciseAngina,
        ST_Slope=payload.ST_Slope,
    )

    try:
        predictor = Predictor.instance(current_app.config["MODEL_PATH"])
        result = predictor.predict(features)
    except FileNotFoundError as exc:
        return jsonify({"error": "model_not_ready", "message": str(exc)}), 503

    # Resolve or create a patient row.
    patient = None
    if payload.patient_id is not None:
        patient = db.session.get(Patient, payload.patient_id)
    if patient is None:
        patient = Patient(
            name=payload.name or "Anonymous",
            age=features.Age,
            restingbp=features.RestingBP,
            cholesterol=features.Cholesterol,
            fastingbs=features.FastingBS,
            maxhr=features.MaxHR,
            oldpeak=features.Oldpeak,
            sex=features.Sex,
            cp=features.ChestPainType,
            restecg=features.RestingECG,
            exang=features.ExerciseAngina,
            slope=features.ST_Slope,
            risk=result.risk,
            probability=result.probability,
        )
        db.session.add(patient)
        db.session.flush()

    user_id = None
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            user_id = current_user.id
    except Exception:  # noqa: BLE001
        pass

    pred_row = Prediction(
        patient_id=patient.id,
        user_id=user_id,
        probability=result.probability,
        risk=result.risk,
        model_version=result.model_version,
        input_features=features.to_dataframe_row(),
    )
    db.session.add(pred_row)
    db.session.commit()

    return jsonify(
        {
            "prediction_id": pred_row.id,
            "patient_id": patient.id,
            "probability": result.probability,
            "risk": result.risk,
            "model_version": result.model_version,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    ), 200
