from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import swisseph as swe
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder
import json
import os

app = FastAPI(title="South Indian Astrology API (JSON-Backed)")

class BirthDetails(BaseModel):
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    birth_place: str 

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

# Load cities from external cities.json file
CITIES_FILE = "cities.json"
if os.path.exists(CITIES_FILE):
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        SOUTH_INDIAN_LOCATIONS = json.load(f)
else:
    SOUTH_INDIAN_LOCATIONS = {}

@app.get("/", response_class=HTMLResponse)
def home_page():
    """Serves a clean UI with a searchable dropdown for birth locations."""
    options_html = "".join([f'<option value="{city.title()}">' for city in SOUTH_INDIAN_LOCATIONS.keys()])
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>South Indian Astrology Calculator</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f6f9; padding: 40px; }}
            .container {{ max-width: 500px; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }}
            h2 {{ color: #333; margin-top: 0; }}
            label {{ font-weight: bold; display: block; margin-top: 15px; color: #555; }}
            input, button {{ width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
            button {{ background: #007bff; color: white; border: none; font-size: 16px; margin-top: 20px; cursor: pointer; }}
            button:hover {{ background: #0056b3; }}
            pre {{ background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>South Indian Horoscope Chart</h2>
            <form id="astroForm">
                <label>Name:</label>
                <input type="text" id="name" required value="Bala">

                <label>Birth Date:</label>
                <div style="display: flex; gap: 10px;">
                    <input type="number" id="year" placeholder="Year (e.g. 1998)" required value="1998">
                    <input type="number" id="month" placeholder="Month (1-12)" required value="5">
                    <input type="number" id="day" placeholder="Day (1-31)" required value="12">
                </div>

                <label>Birth Time (24-Hour Format):</label>
                <div style="display: flex; gap: 10px;">
                    <input type="number" id="hour" placeholder="Hour (0-23)" required value="14">
                    <input type="number" id="minute" placeholder="Minute (0-59)" required value="30">
                </div>

                <label>Birth Place (Search or Select Town):</label>
                <input list="cities-list" id="birth_place" placeholder="Type or select town (e.g., Thirukoilur)" required value="Thirukoilur">
                <datalist id="cities-list">
                    {options_html}
                </datalist>

                <button type="submit">Calculate Janma Nakshatra</button>
            </form>

            <h3>Result:</h3>
            <pre id="result">Awaiting input...</pre>
        </div>

        <script>
            document.getElementById("astroForm").addEventListener("submit", async function(e) {{
                e.preventDefault();
                const payload = {{
                    name: document.getElementById("name").value,
                    year: parseInt(document.getElementById("year").value),
                    month: parseInt(document.getElementById("month").value),
                    day: parseInt(document.getElementById("day").value),
                    hour: parseInt(document.getElementById("hour").value),
                    minute: parseInt(document.getElementById("minute").value),
                    birth_place: document.getElementById("birth_place").value
                }};

                const res = await fetch("/calculate-chart", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                document.getElementById("result").innerText = JSON.stringify(data, null, 2);
            }});
        </script>
    </body>
    </html>
    """

@app.post("/calculate-chart")
def calculate_astro_chart(data: BirthDetails):
    try:
        clean_place = data.birth_place.strip().lower()
        if clean_place not in SOUTH_INDIAN_LOCATIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Location '{data.birth_place}' not found in cities.json database."
            )
        
        lat = SOUTH_INDIAN_LOCATIONS[clean_place]["latitude"]
        lon = SOUTH_INDIAN_LOCATIONS[clean_place]["longitude"]

        # Find Timezone automatically using coordinates
        tf = TimezoneFinder()
        tz_str = tf.timezone_at(lng=lon, lat=lat) or "Asia/Kolkata"
        local_tz = pytz.timezone(tz_str)

        # Convert local birth time to UTC
        local_dt = local_tz.localize(datetime(data.year, data.month, data.day, data.hour, data.minute))
        utc_dt = local_dt.astimezone(pytz.utc)

        # Calculate Julian Day in Universal Time (UT)
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute / 60.0)

        # Set Ayanamsha to Lahiri (Standard for South Indian Astrology)
        swe.set_sid_mode(swe.SIDM_LAHIRI)

        # Calculate Moon's position (Sidereal / Nirayana)
        moon_pos, ret, err = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)
        moon_longitude = moon_pos[0] 

        # Determine Nakshatra & Pada
        nakshatra_span = 360.0 / 27.0
        nakshatra_index = int(moon_longitude / nakshatra_span)
        nakshatra_name = NAKSHATRAS[nakshatra_index]

        remainder_degrees = moon_longitude % nakshatra_span
        pada = int(remainder_degrees / (nakshatra_span / 4.0)) + 1

        return {
            "status": "success",
            "name": data.name,
            "birth_place": data.birth_place,
            "coordinates": {"latitude": lat, "longitude": lon},
            "timezone": tz_str,
            "astrological_results": {
                "moon_sidereal_longitude": round(moon_longitude, 2),
                "janma_nakshatra": nakshatra_name,
                "nakshatra_pada": pada
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
