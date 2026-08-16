import io
import os
import re
import unicodedata

import pdfplumber
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ...extensions import db
from ...models import Patient, Prediction, PdfReport, User
from ...predict import HeartFeatures, Predictor
from ...services.pdf_report import build_patient_pdf

bp = Blueprint('report', __name__, template_folder='templates')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', {'pdf'})

def parse_report_text(text):
    data = {
        'name': 'Anonymous',
        'address': '',  # default to empty, will be filled from PDF or user context
        'age': 50.0,
        'sex': 'M',
        'restingbp': 120.0,
        'cholesterol': 200.0,
        'fastingbs': 0,
        'maxhr': 140.0,
        'oldpeak': 0.0,
        'cp': 'ASY',
        'restecg': 'Normal',
        'exang': 'N',
        'slope': 'Flat'
    }
    
    name_match = re.search(r'(?:Name|Patient Name):\s*([^\n\r]+)', text, re.IGNORECASE)
    if name_match:
        data['name'] = name_match.group(1).strip()
        
    addr_match = re.search(r'(?:Address|Location|Area|City|State):\s*([^\n\r]+)', text, re.IGNORECASE)
    if addr_match:
        data['address'] = addr_match.group(1).strip()
        
    age_match = re.search(r'(?:Age):\s*([0-9.]+)', text, re.IGNORECASE)
    if age_match:
        try:
            data['age'] = float(age_match.group(1).strip())
        except ValueError:
            pass
        
    sex_match = re.search(r'(?:Sex|Gender):\s*([^\n\r]+)', text, re.IGNORECASE)
    if sex_match:
        val = sex_match.group(1).strip().upper()
        if 'FEMALE' in val or val == 'F':
            data['sex'] = 'F'
        else:
            data['sex'] = 'M'
            
    bp_match = re.search(r'(?:RestingBP|Resting BP|BP|Blood Pressure):\s*([0-9.]+)', text, re.IGNORECASE)
    if bp_match:
        try:
            data['restingbp'] = float(bp_match.group(1).strip())
        except ValueError:
            pass
        
    chol_match = re.search(r'(?:Cholesterol|Chol):\s*([0-9.]+)', text, re.IGNORECASE)
    if chol_match:
        try:
            data['cholesterol'] = float(chol_match.group(1).strip())
        except ValueError:
            pass
        
    fbs_match = re.search(r'(?:FastingBS|Fasting Blood Sugar|FBS):\s*([0-9.]+)', text, re.IGNORECASE)
    if fbs_match:
        try:
            val = float(fbs_match.group(1).strip())
            data['fastingbs'] = 1 if val > 120 or val == 1 else 0
        except ValueError:
            pass
        
    maxhr_match = re.search(r'(?:MaxHR|Max Heart Rate|Max HR):\s*([0-9.]+)', text, re.IGNORECASE)
    if maxhr_match:
        try:
            data['maxhr'] = float(maxhr_match.group(1).strip())
        except ValueError:
            pass
        
    op_match = re.search(r'(?:Oldpeak|ST Depression):\s*([0-9.]+)', text, re.IGNORECASE)
    if op_match:
        try:
            data['oldpeak'] = float(op_match.group(1).strip())
        except ValueError:
            pass
        
    cp_match = re.search(r'(?:ChestPainType|Chest Pain Type|CP Type|CP):\s*([A-Za-z]+)', text, re.IGNORECASE)
    if cp_match:
        val = cp_match.group(1).strip().upper()
        if val in ['TA', 'ATA', 'NAP', 'ASY']:
            data['cp'] = val
            
    ecg_match = re.search(r'(?:RestingECG|Resting ECG|ECG):\s*([A-Za-z0-9]+)', text, re.IGNORECASE)
    if ecg_match:
        val = ecg_match.group(1).strip()
        if 'ST' in val.upper():
            data['restecg'] = 'ST'
        elif 'LVH' in val.upper():
            data['restecg'] = 'LVH'
        else:
            data['restecg'] = 'Normal'
            
    ex_match = re.search(r'(?:ExerciseAngina|Exercise Induced Angina|ExAng|Angina):\s*([A-Za-z]+)', text, re.IGNORECASE)
    if ex_match:
        val = ex_match.group(1).strip().upper()
        if 'Y' in val or 'YES' in val:
            data['exang'] = 'Y'
        else:
            data['exang'] = 'N'
            
    slope_match = re.search(r'(?:ST_Slope|Slope|ST Slope):\s*([A-Za-z]+)', text, re.IGNORECASE)
    if slope_match:
        val = slope_match.group(1).strip().title()
        if val in ['Up', 'Flat', 'Down']:
            data['slope'] = val
            
    return data

@bp.route('/upload-report', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'report_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['report_file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Save upload path in app instance folder
            upload_dir = os.path.join(current_app.instance_path, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            
            # Extract PDF text
            text = ""
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
            except Exception as e:
                flash(f"Failed to parse PDF: {str(e)}", 'danger')
                return redirect(request.url)
            
            # Parse features
            parsed_data = parse_report_text(text)
            
            # Run prediction
            try:
                features = HeartFeatures(
                    Age=parsed_data['age'],
                    RestingBP=parsed_data['restingbp'],
                    Cholesterol=parsed_data['cholesterol'],
                    FastingBS=parsed_data['fastingbs'],
                    MaxHR=parsed_data['maxhr'],
                    Oldpeak=parsed_data['oldpeak'],
                    Sex=parsed_data['sex'],
                    ChestPainType=parsed_data['cp'],
                    RestingECG=parsed_data['restecg'],
                    ExerciseAngina=parsed_data['exang'],
                    ST_Slope=parsed_data['slope']
                )
                predictor = Predictor.instance(current_app.config["MODEL_PATH"])
                result = predictor.predict(features)
                explanations = predictor.explain(features)
            except Exception as e:
                current_app.logger.exception("Prediction failed during PDF upload")
                flash(f"Prediction failed: {str(e)}", 'danger')
                return redirect(request.url)
            
            # Save Patient
            patient = Patient(
                name=parsed_data['name'],
                age=parsed_data['age'],
                restingbp=parsed_data['restingbp'],
                cholesterol=parsed_data['cholesterol'],
                fastingbs=parsed_data['fastingbs'],
                maxhr=parsed_data['maxhr'],
                oldpeak=parsed_data['oldpeak'],
                sex=parsed_data['sex'],
                cp=parsed_data['cp'],
                restecg=parsed_data['restecg'],
                exang=parsed_data['exang'],
                slope=parsed_data['slope'],
                risk=result.risk,
                probability=result.probability,
                owner_id=current_user.id
            )
            db.session.add(patient)
            db.session.flush()
            
            # Save Prediction
            pred_row = Prediction(
                patient_id=patient.id,
                user_id=current_user.id,
                probability=result.probability,
                risk=result.risk,
                model_version=result.model_version,
                input_features=features.to_dataframe_row()
            )
            db.session.add(pred_row)

            # Use user's area as fallback if no address found in PDF
            report_address = parsed_data['address']
            if not report_address and current_user.is_authenticated and hasattr(current_user, 'area') and current_user.area:
                report_address = current_user.area

            # Save PDF Report Metadata
            pdf_rep = PdfReport(
                filename=filename,
                patient_name=parsed_data['name'],
                address=report_address,
                parsed_data=parsed_data,
                patient_id=patient.id
            )
            db.session.add(pdf_rep)
            db.session.commit()
            
            # Redirect to the report dashboard page
            return redirect(url_for('report.view_report', report_id=pdf_rep.id))
            
    return render_template('report/upload.html')

@bp.route('/report/<int:report_id>')
@login_required
def view_report(report_id):
    pdf_rep = db.session.get(PdfReport, report_id)
    if not pdf_rep:
        flash('Report not found', 'danger')
        return redirect(url_for('main.dashboard'))

    # Read the prediction linked to patient
    patient = pdf_rep.patient
    pred = Prediction.query.filter_by(patient_id=patient.id).order_by(Prediction.created_at.desc()).first()

    # Calculate dataset statistics to show charts comparing this user to others
    # Read some stats or use average stats from training set
    # E.g., average cholesterol is 244, maxhr is 136, bp is 130
    return render_template('report/view_report.html', report=pdf_rep, patient=patient, prediction=pred)


def _slug(value: str) -> str:
    """Make a filename-safe slug from a patient name. Returns 'patient' if
    the input is empty or only non-alphanumeric characters."""
    if not value:
        return "patient"
    # Normalise unicode, then strip accents, then keep only a-z 0-9 and '-'.
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "patient"


@bp.route('/report/<int:report_id>/pdf')
@login_required
def download_pdf(report_id: int):
    """Generate and return a downloadable PDF analysis report for the given
    PdfReport row. Mirrors the predict blueprint's permission policy: admins
    see any report, regular users see only reports that own the underlying
    patient."""
    try:
        pdf_rep = db.session.get(PdfReport, report_id)
    except Exception as exc:
        # The local DB may be missing columns that the model declares (e.g.
        # an older pdf_reports table that lacks pdf_path). Fall through to 404
        # so we never 500 a user trying to download a legitimate report.
        current_app.logger.warning("PDF lookup failed for report %s: %s", report_id, exc)
        abort(404)
    if pdf_rep is None:
        abort(404)
    patient = pdf_rep.patient
    if patient is None:
        abort(404, description="Linked patient not found.")
    if not (current_user.is_admin or patient.owner_id == current_user.id):
        abort(403)

    pred = (
        Prediction.query
        .filter_by(patient_id=patient.id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    if pred is None:
        abort(404, description="No prediction available for this report.")

    # SHAP is not persisted on the Prediction row (see app/models.py), so we
    # recompute it here. The Predictor is a singleton and the model is
    # already loaded — extra cost is the SHAP call on a single row, which is
    # cheap. mirror the pattern used by app/blueprints/predict/routes.py:40.
    explanations: dict | None = None
    try:
        features = HeartFeatures(**pred.input_features)
        predictor = Predictor.instance(current_app.config["MODEL_PATH"])
        explanations = predictor.explain(features)
    except Exception:
        current_app.logger.warning("SHAP explain failed during PDF generation")

    try:
        pdf_bytes = build_patient_pdf(
            report=pdf_rep,
            patient=patient,
            prediction=pred,
            explanations=explanations,
            generated_by=current_user if current_user.is_authenticated else None,
        )
    except Exception:
        current_app.logger.exception("PDF build failed for report %s", report_id)
        abort(500, description="Failed to generate PDF.")

    filename = f"corai-report-{pdf_rep.id}-{_slug(pdf_rep.patient_name or 'patient')}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )
