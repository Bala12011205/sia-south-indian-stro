from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from geopy.geocoders import Nominatim
import swisseph as swe
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder

app = FastAPI(title="South India Astrology API")

class BirthDetails(BaseModel):
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    birthplace: str

NAKSHATRAS =["Ashwini", "Bharani", "Krittika", "Rohini",
              "Mrigashira", "Ardra", "Punarvasu", "Pushya",
              "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
              "Hasta", "Chitra", "Swati", "Vishakha",
              "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
              "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
              "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
@app.get("/")
def read_root():
    return {"message": "Welcome to the South Indian Astrology API! Go to /docs to test it."}

@app.get("/search-city")
def search_city(query: str):
    """Search for any city, town, or village to get its exact latitude and longitude."""
    geolocator = Nominatim(user_agent="south_indian_astro_app")
    # Fetch up to 5 matching locations
    locations = geolocator.geocode(query, exactly_one=False, limit=5)
    
    if not locations:
        return {"status": "not_found", "message": f"Could not find any location matching '{query}'."}
    
    results = [
        {
            "display_name": loc.address,
            "latitude": loc.latitude,
            "longitude": loc.longitude
        } 
        for loc in locations
    ]
    
    return {"status": "success", "results": results}


@app.post("/calculate-chart")

def calculate_astro_chart(data: BirthDetails):
    try:
        geolocator = Nominatim(user_agent="south_indian_astro_app")
        location = geolocator.geocode(data.birthplace)

        if not location:
            raise HTTPException(status_code=404, detail="Birthplace not found")

        lat, lon = location.latitude, location.longitude

        tf = TimezoneFinder()
        tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
        local_tz = pytz.timezone(tz_str)

        local_dt = local_tz.localize(datetime(data.year,
                                             data.month,
                                             data.day,
                                             data.hour,
                                             data.minute))
        utc_dt = local_dt.astimezone(pytz.utc)

        julian_day = swe.julday(utc_dt.year,
                                utc_dt.month,
                                utc_dt.day,
                                utc_dt.hour + utc_dt.minute /60.0)
        
        swe.set_sid_mode(swe.SIDM_LAHIRI)

        moon_pos, ret, _ = swe.calc_ut(julian_day, swe.MOON,swe.FLG_SIDEREAL)
        moon_longitude = moon_pos[0]

        nakshatra_span = 360.0 /27.0
        nakshatra_index = int(moon_longitude / nakshatra_span)
        nakshatra_name = NAKSHATRAS[nakshatra_index]

        remainder_degrees = moon_longitude % nakshatra_span
        pada = int(remainder_degrees/(nakshatra_span / 4.0)) +1

        return {
            'status' : 'Success',
            "Name":data.name,
            "Birthplace":data.birthplace,
            "Coordinates":{'latitude':lat, "longitude":lon},
            "Timezone":tz_str,
            "Birthtime":utc_dt.strftime('%Y-%m-%d %H:%M:%S uTC'),
            "Astro results":{
                "Moon Longitude":round(moon_longitude, 2),
                "Nakshatra":nakshatra_name,
                "Pada":pada
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
