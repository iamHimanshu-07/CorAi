import requests
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, current_app

bp = Blueprint('about', __name__, template_folder='templates')

cached_about_data = None

def scrape_about_info():
    global cached_about_data
    if cached_about_data:
        return cached_about_data
        
    url = current_app.config.get('ABOUT_US_SOURCE_URL', 'https://www.who.int/about')
    fallback_data = {
        'title': 'About WHO & Cardiovascular Health',
        'content': [
            'Cardiovascular diseases (CVDs) are the leading cause of death globally, taking an estimated 17.9 million lives each year.',
            'The World Health Organization (WHO) is the United Nations specialized agency for health, founded in 1948 and headquartered in Geneva, Switzerland.',
            'WHO works worldwide to promote health, keep the world safe, and serve the vulnerable. Our goal is to ensure that a billion more people have universal health coverage, to protect a billion more people from health emergencies, and provide a billion more people with better health and well-being.',
            'Through advocacy, research, and guidelines, WHO supports countries in implementing cost-effective interventions to prevent and control heart disease, such as reducing tobacco use, promoting healthy diets, and improving access to essential medicines.'
        ],
        'sourced_from': 'Default Knowledgebase (Offline Fallback)'
    }
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            paragraphs = []
            
            # Look for content in standard article/content divs
            main_content = soup.find('article') or soup.find(class_='sf-detail-body-wrapper') or soup.find(id='main-content') or soup.find(class_='content')
            if main_content:
                for p in main_content.find_all('p'):
                    text = p.get_text().strip()
                    if text and len(text) > 30:
                        paragraphs.append(text)
            
            if not paragraphs:
                for p in soup.find_all('p'):
                    text = p.get_text().strip()
                    if text and len(text) > 40:
                        paragraphs.append(text)
            
            if paragraphs:
                title = soup.title.string.strip() if soup.title else 'About World Health Organization'
                # Clean title if it contains suffixes
                if ' | ' in title:
                    title = title.split(' | ')[0]
                
                cached_about_data = {
                    'title': title,
                    'content': paragraphs[:6],
                    'sourced_from': url
                }
                return cached_about_data
    except Exception as e:
        current_app.logger.warning(f"Failed to scrape about page: {e}")
        
    return fallback_data

@bp.route('/about')
def view_about():
    data = scrape_about_info()
    return render_template('about/about.html', data=data)
