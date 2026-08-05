# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-08-05

### Added

- Initial release of the Heart Disease Prediction System.
- Calibrated ensemble classifier (LR, RF, XGBoost, LightGBM) on UCI heart-disease
  dataset (918 rows).
- Flask web app with auth, dashboard, patient CRUD, prediction form,
  PDF reports, JSON API, admin tools, FHIR R4 stub.
- Per-prediction audit log (model version, user, input features).
- SHAP-based per-prediction explanations.
- Docker / docker-compose support.
- Pytest + ruff CI.