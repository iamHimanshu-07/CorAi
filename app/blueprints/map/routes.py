from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from ...models import Doctor

bp = Blueprint('map', __name__, template_folder='templates')

@bp.route('/map')
@login_required
def view_map():
    # Retrieve query param 'area', fallback to user's area if configured
    area = request.args.get('area', '').strip()
    if not area and current_user.is_authenticated and hasattr(current_user, 'area'):
        area = current_user.area or ''
    # If no area specified, leave empty for user to specify

    return render_template('map/map.html', area=area, map_tile_url=current_app.config.get('MAP_TILE_URL'))

@bp.route('/api/doctors')
@login_required
def get_doctors_api():
    area = request.args.get('area', '').strip()
    
    if area:
        # Check if we can find doctors matching area
        doctors_query = Doctor.query.filter(Doctor.area.ilike(f"%{area}%")).all()
        if not doctors_query:
            # Fallback to fuzzy match or first word
            first_word = area.split(',')[0].strip()
            doctors_query = Doctor.query.filter(Doctor.area.ilike(f"%{first_word}%")).all()
    else:
        doctors_query = []
        
    # If no doctors found for the area, return all doctors as fallback
    if not doctors_query:
        doctors_query = Doctor.query.all()

    doctors_list = [{
        'id': d.id,
        'name': d.name,
        'specialty': d.specialty,
        'area': d.area,
        'lat': d.lat,
        'lng': d.lng,
        'phone': d.phone,
        'email': d.email
    } for d in doctors_query]
    
    return jsonify({
        'area': area,
        'doctors': doctors_list
    })
