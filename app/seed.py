"""One-time seed of a default doctor account on first run."""

from __future__ import annotations

import logging

from flask import current_app

from .extensions import db
from .models import User

log = logging.getLogger(__name__)


def seed_default_doctor() -> None:
    username = current_app.config["BOOTSTRAP_DOCTOR_USERNAME"]
    if User.query.filter_by(username=username).first():
        return
    doctor = User(
        username=username,
        role="doctor",
        email=current_app.config["BOOTSTRAP_DOCTOR_EMAIL"],
        area=current_app.config.get("BOOTSTRAP_DOCTOR_AREA", "India"),
    )
    doctor.set_password(current_app.config["BOOTSTRAP_DOCTOR_PASSWORD"])
    db.session.add(doctor)
    db.session.commit()
    log.info(f"Seeded default doctor '{username}' (change the password in production!)")
    seed_doctors()


def seed_doctors() -> None:
    from .models import Doctor

    sample_doctors = [
        # Maharashtra
        {"name": "Dr. Amit Verma", "specialty": "Cardiologist", "area": "Mumbai", "lat": 19.0760, "lng": 72.8777, "phone": "+91 98765 43210", "email": "amit.verma@cardio.in"},
        {"name": "Dr. Priya Deshmukh", "specialty": "Cardiovascular Surgeon", "area": "Mumbai", "lat": 19.0825, "lng": 72.8900, "phone": "+91 98765 43211", "email": "priya.d@cardio.in"},
        {"name": "Dr. Neha Patil", "specialty": "Interventional Cardiologist", "area": "Pune", "lat": 18.5204, "lng": 73.8567, "phone": "+91 98765 43212", "email": "neha.patil@cardio.in"},
        {"name": "Dr. Vikram Singh", "specialty": "Cardiac Surgeon", "area": "Nagpur", "lat": 21.1458, "lng": 79.0882, "phone": "+91 98765 43213", "email": "vikram.singh@cardio.in"},

        # Gujarat (including Surat)
        {"name": "Dr. Meera Shah", "specialty": "Cardiologist", "area": "Surat", "lat": 21.1702, "lng": 72.8311, "phone": "+91 98765 43214", "email": "meera.shah@suratcardio.in"},
        {"name": "Dr. Rajiv Mehta", "specialty": "Interventional Cardiologist", "area": "Surat", "lat": 21.1900, "lng": 72.8200, "phone": "+91 98765 43215", "email": "rajiv.mehta@suratcardio.in"},
        {"name": "Dr. Anjali Desai", "specialty": "Pediatric Cardiologist", "area": "Ahmedabad", "lat": 23.0225, "lng": 72.5714, "phone": "+91 98765 43216", "email": "anjali.desai@ahmedabadcardio.in"},
        {"name": "Dr. Kunal Joshi", "specialty": "Electrophysiologist", "area": "Vadodara", "lat": 22.3072, "lng": 73.1812, "phone": "+91 98765 43217", "email": "kunal.joshi@vcardio.in"},

        # Karnataka
        {"name": "Dr. Rajesh Rao", "specialty": "Cardiologist", "area": "Bangalore", "lat": 12.9716, "lng": 77.5946, "phone": "+91 87654 32109", "email": "rajesh.rao@heart.in"},
        {"name": "Dr. Sandeep Kumar", "specialty": "Electrophysiologist", "area": "Bangalore", "lat": 12.9850, "lng": 77.6050, "phone": "+91 87654 32108", "email": "sandeep.k@heart.in"},
        {"name": "Dr. Lakshmi Narayan", "specialty": "Cardiologist", "area": "Mysore", "lat": 12.2958, "lng": 76.6394, "phone": "+91 87654 32118", "email": "lakshmi.n@heart.in"},

        # Delhi/NCR
        {"name": "Dr. Sunita Sharma", "specialty": "Interventional Cardiologist", "area": "Delhi", "lat": 28.6139, "lng": 77.2090, "phone": "+91 76543 21098", "email": "sunita.sharma@delhiheart.in"},
        {"name": "Dr. Arjun Kapoor", "specialty": "Cardiologist", "area": "Gurgaon", "lat": 28.4595, "lng": 77.0266, "phone": "+91 76543 21099", "email": "arjun.kapur@delhiheart.in"},
        {"name": "Dr. Priya Malhotra", "specialty": "Cardiac Surgeon", "area": "Noida", "lat": 28.5355, "lng": 77.3910, "phone": "+91 76543 21100", "email": "priya.malhotra@delhiheart.in"},

        # Tamil Nadu
        {"name": "Dr. Kavita Reddy", "specialty": "Interventional Cardiologist", "area": "Chennai", "lat": 13.0827, "lng": 80.2707, "phone": "+91 98765 43219", "email": "kavita.reddy@chennaiheart.in"},
        {"name": "Dr. Suresh Babu", "specialty": "Pediatric Cardiologist", "area": "Coimbatore", "lat": 11.0168, "lng": 76.9558, "phone": "+91 98765 43220", "email": "suresh.babu@coimbatoreheart.in"},

        # West Bengal
        {"name": "Dr. Suman Banerjee", "specialty": "Cardiologist", "area": "Kolkata", "lat": 22.5726, "lng": 88.3639, "phone": "+91 98765 43221", "email": "suman.banerjee@kolkatacardio.in"},
        {"name": "Dr. Debashree Roy", "specialty": "Cardiologist", "area": "Siliguri", "lat": 26.7271, "lng": 88.3953, "phone": "+91 98765 43222", "email": "debashree.roy@kolkatacardio.in"},

        # United States
        {"name": "Dr. Sarah Jenkins", "specialty": "Cardiologist", "area": "New York", "lat": 40.7128, "lng": -74.0060, "phone": "+1 212-555-0199", "email": "s.jenkins@nycardio.com"},
        {"name": "Dr. Robert Carter", "specialty": "Cardiology Specialist", "area": "Chicago", "lat": 41.8781, "lng": -87.6298, "phone": "+1 312-555-0144", "email": "r.carter@chicagocardio.net"},
        {"name": "Dr. Michael Chen", "specialty": "Interventional Cardiologist", "area": "Los Angeles", "lat": 34.0522, "lng": -118.2437, "phone": "+1 213-555-0199", "email": "m.chen@lacardio.com"},
        {"name": "Dr. Lisa Rodriguez", "specialty": "Pediatric Cardiologist", "area": "Houston", "lat": 29.7604, "lng": -95.3698, "phone": "+1 713-555-0199", "email": "l.rodriguez@txheart.com"}
    ]

    added_count = 0
    for d_data in sample_doctors:
        # Check if doctor with same name already exists to avoid duplicates
        existing_doctor = Doctor.query.filter_by(name=d_data["name"]).first()
        if not existing_doctor:
            d = Doctor(**d_data)
            db.session.add(d)
            added_count += 1
        else:
            # Optional: update existing doctor's info if needed
            pass

    if added_count > 0:
        db.session.commit()
        log.info(f"Seeded {added_count} new doctors for mapping feature.")
    else:
        log.info("All sample doctors already exist in database.")

