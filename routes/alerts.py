from fastapi import FastAPI, WebSocket, Query
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import math

app = FastAPI()

# Database setup
DATABASE_URL = "sqlite:///./traffic.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Accident model
class Accident(Base):
    __tablename__ = "accidents"
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    description = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

# Store active WebSocket connections
active_connections = []

# Function to calculate distance between two points (Haversine Formula)
def is_nearby(lat1, lon1, lat2, lon2, max_distance=2.0):
    R = 6371  # Radius of Earth in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2) ** 2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * (math.sin(dlon/2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = R * c  # Distance in km
    return distance <= max_distance

# 1️⃣ Report an Accident (POST)
@app.post("/report-accident")
def report_accident(latitude: float, longitude: float, description: str):
    db = SessionLocal()
    new_accident = Accident(latitude=latitude, longitude=longitude, description=description)
    db.add(new_accident)
    db.commit()
    db.refresh(new_accident)

    # Notify nearby vehicles
    for connection in active_connections:
        if is_nearby(latitude, longitude, connection["lat"], connection["lon"]):
            connection["ws"].send_json({
                "alert": f"🚨 {description} near your location!",
                "latitude": latitude,
                "longitude": longitude
            })
    
    return {"message": "Accident reported successfully", "id": new_accident.id}

# 2️⃣ Get Nearby Alerts (GET)
@app.get("/get-alerts")
def get_alerts(lat: float, lon: float, max_distance: float = 2.0):
    db = SessionLocal()
    all_accidents = db.query(Accident).all()
    nearby_accidents = [
        {
            "id": acc.id,
            "latitude": acc.latitude,
            "longitude": acc.longitude,
            "description": acc.description
        }
        for acc in all_accidents if is_nearby(lat, lon, acc.latitude, acc.longitude, max_distance)
    ]
    return {"alerts": nearby_accidents}

# 3️⃣ WebSocket for Real-Time Alerts
@app.websocket("/ws/alerts")
async def alert_websocket(websocket: WebSocket, lat: float = Query(...), lon: float = Query(...)):
    await websocket.accept()
    connection = {"ws": websocket, "lat": lat, "lon": lon}
    active_connections.append(connection)

    try:
        while True:
            await websocket.receive_text()  # Keep connection open
    except:
        active_connections.remove(connection)
