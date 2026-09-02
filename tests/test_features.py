import io
import json
from unittest.mock import patch
from app.models import Doctor, PdfReport

def test_about_us_page(client):
    rv = client.get("/about")
    assert rv.status_code == 200
    assert b"About" in rv.data

def test_doctors_map_page(doctor_client):
    rv = doctor_client.get("/map")
    assert rv.status_code == 200
    assert b"Cardiologist Directory" in rv.data

def test_doctors_api(doctor_client, app):
    with app.app_context():
        # Make sure at least one doctor is in the DB
        if not Doctor.query.filter_by(name="Dr. Amit Verma").first():
            d = Doctor(name="Dr. Amit Verma", specialty="Cardiologist", area="Mumbai", lat=19.076, lng=72.877)
            from app.extensions import db
            db.session.add(d)
            db.session.commit()

    rv = doctor_client.get("/api/doctors?area=Mumbai")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "doctors" in data
    assert len(data["doctors"]) >= 1
    assert data["doctors"][0]["name"] == "Dr. Amit Verma"

@patch('app.blueprints.chatbot.routes.OpenAI')
def test_chatbot_api(mock_openai_class, doctor_client, app, monkeypatch):
    # Mock OpenAI API response
    mock_client = mock_openai_class.return_value
    mock_client.chat.completions.create.return_value = type('obj', (object,), {
        'choices': [
            type('choice', (object,), {
                'message': type('msg', (object,), {
                    'content': 'Hello, I am a mocked AI assistant.'
                })
            })
        ]
    })

    # The chat route prefers RAG (Gemini) when GOOGLE_API_KEY is set. To
    # exercise the OpenAI fallback path we explicitly force
    # ``is_configured()`` to return False for the duration of this test.
    # This way the mock is actually used regardless of the host env.
    monkeypatch.setattr(
        "app.blueprints.chatbot.routes._rag_ready", lambda: False
    )

    # Set mock configuration so LLM_API_KEY passes check
    with app.app_context():
        app.config['LLM_API_KEY'] = 'test-key'

    rv = doctor_client.post("/chat", json={"message": "Hello"})
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["reply"] == "Hello, I am a mocked AI assistant."

def test_upload_report_page(doctor_client):
    rv = doctor_client.get("/upload-report")
    assert rv.status_code == 200
    assert b"Upload Medical Report" in rv.data

def test_upload_report_pdf(doctor_client, app):
    # We will upload a dummy text PDF. For the test, we mock pdfplumber text extraction.
    pdf_content = b"%PDF-1.4 dummy pdf"
    
    parsed_mock = (
        "Name: Aarav Sharma\n"
        "Address: Mumbai, IN\n"
        "Age: 45\n"
        "Sex: Male\n"
        "RestingBP: 125\n"
        "Cholesterol: 210\n"
        "FastingBS: 0\n"
        "MaxHR: 165\n"
        "Oldpeak: 1.0\n"
        "ChestPainType: ATA\n"
        "RestingECG: Normal\n"
        "ExerciseAngina: N\n"
        "ST_Slope: Up\n"
    )

    with patch('pdfplumber.open') as mock_open:
        # Mock pdfplumber structure: open() context manager returns an object containing pages
        mock_page = type('page', (object,), {'extract_text': lambda: parsed_mock})
        mock_pdf = type('pdf', (object,), {'pages': [mock_page]})
        mock_open.return_value.__enter__.return_value = mock_pdf

        data = {
            'report_file': (io.BytesIO(pdf_content), 'report.pdf')
        }
        rv = doctor_client.post("/upload-report", data=data, content_type='multipart/form-data')
        
        # Should redirect to report detail view
        assert rv.status_code == 302
        assert "/report/" in rv.headers["Location"]

def test_delete_patient(doctor_client, app):
    # Patient views were removed (see app/blueprints/patients/routes.py —
    # the blueprint is now a catch-all 404). The endpoint this test
    # targets no longer exists, so the route returns 405 (METHOD NOT
    # ALLOWED) on POST instead of the expected 302 redirect. Skipping
    # until the patient CRUD views are reinstated or this test is
    # repurposed against a different delete surface.
    import pytest
    pytest.skip("patient delete endpoint removed with the patient views")

def test_delete_user_admin(client, app):
    with app.app_context():
        from app.models import User
        from app.extensions import db
        # Ensure admin user
        admin = User.query.filter_by(role="admin").first()
        if not admin:
            admin = User(username="admin_user", role="admin", email="admin@test.com")
            admin.set_password("adminpass")
            db.session.add(admin)

        target = User(username="user_to_delete", role="patient", email="delete@test.com")
        target.set_password("pass123")
        db.session.add(target)
        db.session.commit()
        target_id = target.id
        admin_username = admin.username

    # Login as admin
    client.post("/auth/login", data={"username": "admin_user", "password": "adminpass"})
    rv = client.post(f"/admin/users/{target_id}/delete")
    assert rv.status_code == 302

    with app.app_context():
        from app.models import User
        from app.extensions import db
        assert db.session.get(User, target_id) is None
