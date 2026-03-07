from flask import Flask, render_template, request
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import re

app = Flask(__name__)

# -----------------------------------------------------------
# HOUSING AUTHORITY DATA (STATIC)
# -----------------------------------------------------------

HOUSING_AUTHORITIES = {
    "dha": {
        "name": "Defence Housing Authority (DHA)",
        "areas": "Karachi, Lahore, Islamabad, Multan, Bahawalpur",
        "population": "1+ million (approx)",
        "houses": "Hundreds of thousands",
        "established": "1953"
    },
    "bahria town": {
        "name": "Bahria Town",
        "areas": "Karachi, Lahore, Islamabad, Rawalpindi",
        "population": "500,000+",
        "houses": "Planned residential sectors",
        "established": "1996"
    },
    "cda": {
        "name": "Capital Development Authority (CDA)",
        "areas": "Islamabad",
        "population": "2+ million",
        "houses": "Sectors-based housing",
        "established": "1960"
    }
}

# -----------------------------------------------------------
# Check for multiple housing authorities
# -----------------------------------------------------------
def check_housing_authority(query):
    """
    Accepts query string like 'dha, bahria town'
    Returns list of matching housing authorities from dictionary
    """
    query_lower = query.lower()
    results = []

    # Split query by commas
    queries = [q.strip() for q in query_lower.split(',')]

    for q in queries:
        for key, data in HOUSING_AUTHORITIES.items():
            if key in q:
                results.append(data)

    return results if results else None

# -----------------------------------------------------------
# OLX SCRAPER (unchanged)
# -----------------------------------------------------------
def scrape_olx(query):
    url = f"https://www.olx.com.pk/items/q-{query.replace(' ', '-')}"
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=90000)
            page.wait_for_selector('div[data-aut-id="itemBox"]', timeout=30000)
            time.sleep(3)
            soup = BeautifulSoup(page.content(), 'html.parser')
            items = soup.select('div[data-aut-id="itemBox"]')
            for item in items:
                title_elem = item.select_one('[data-aut-id="itemTitle"]')
                price_elem = item.select_one('[data-aut-id="itemPrice"]')
                link_elem = item.find('a', href=True)
                if title_elem and link_elem:
                    results.append({
                        "title": title_elem.text.strip(),
                        "price": price_elem.text.strip() if price_elem else "Price not listed",
                        "link": "https://www.olx.com.pk" + link_elem['href']
                    })
        except Exception as e:
            print(f"❌ OLX scraping error: {e}")
        finally:
            browser.close()
    return results

# -----------------------------------------------------------
# FACEBOOK SCRAPER (unchanged)
# -----------------------------------------------------------
def scrape_facebook(query):
    url = f"https://www.facebook.com/marketplace/search/?query={query.replace(' ', '%20')}"
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=90000)
            page.wait_for_selector('div[role="article"]', timeout=60000)
            soup = BeautifulSoup(page.content(), 'html.parser')
            items = soup.select('div[role="article"]')
            for item in items:
                title_elem = item.find('span', string=True)
                price_elem = item.find('span', string=lambda text: 'Rs' in text or 'PKR' in text if text else False)
                link_elem = item.find('a', href=True)
                if title_elem and link_elem:
                    results.append({
                        "title": title_elem.text.strip(),
                        "price": price_elem.text.strip() if price_elem else "Price not listed",
                        "link": "https://www.facebook.com" + link_elem['href']
                    })
        except Exception as e:
            print(f"❌ Facebook scraping error: {e}")
        finally:
            browser.close()
    return results

# -----------------------------------------------------------
# GOOGLE REAL ESTATE SCRAPER (unchanged)
# -----------------------------------------------------------
def scrape_google_real_estate(query):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            search_url = f"https://www.zameen.com/residential/societies/?q={query.replace(' ', '+')}"
            page.goto(search_url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            soup = BeautifulSoup(page.content(), "html.parser")
            societies = soup.select("div.ef447dde")  # Zameen society card
            for s in societies[:10]:
                name_elem = s.select_one("h2")
                location_elem = s.select_one("p")
                desc_elem = s.select_one("p")

                name = name_elem.text.strip() if name_elem else query.upper()
                location = location_elem.text.strip() if location_elem else "Not found"
                desc = desc_elem.text.strip() if desc_elem else ""

                # Parse description for population, houses, phases
                population = "Not found"
                houses = "Not found"
                phases = "Not found"

                pop_match = re.search(r'([\d,]+)\s*(people|inhabitants)', desc, re.I)
                if pop_match:
                    population = pop_match.group(0)

                houses_match = re.search(r'([\d,]+)\s*(houses|plots|units)', desc, re.I)
                if houses_match:
                    houses = houses_match.group(0)

                phases_match = re.findall(r'Phase\s*\d+', desc, re.I)
                if phases_match:
                    phases = ", ".join(phases_match)

                results.append({
                    "name": name,
                    "location": location,
                    "population": population,
                    "houses": houses,
                    "phases": phases,
                    "comments": [desc] if desc else []
                })

        except Exception as e:
            print(f"❌ Zameen scraping error: {e}")
        finally:
            browser.close()
    return results

# -----------------------------------------------------------
# ROUTES
# -----------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query', '')

    # STEP 1: Check for multiple housing authorities
    housing_data_list = check_housing_authority(query)

    if housing_data_list:
        return render_template(
            'results.html',
            query=query,
            housing_data_list=housing_data_list,  # send list now
            olx_results=[],  # keep scrapers empty
            fb_results=[],
            google_data=[]
        )

    # ELSE → normal product/property search
    olx_results = scrape_olx(query)
    fb_results = scrape_facebook(query)
    google_data = scrape_google_real_estate(query)

    return render_template(
        'results.html',
        query=query,
        olx_results=olx_results,
        fb_results=fb_results,
        google_data=google_data,
        housing_data_list=None
    )


if __name__ == '__main__':
    app.run(debug=True)
