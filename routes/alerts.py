from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
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

# 1️⃣ WebSocket for Reporting & Receiving Accidents
@app.websocket("/ws/alerts")
async def accident_websocket(websocket: WebSocket, lat: float = Query(...), lon: float = Query(...)):
    await websocket.accept()
    connection = {"ws": websocket, "lat": lat, "lon": lon}
    active_connections.append(connection)

    try:
        while True:
            data = await websocket.receive_json()  # Receive JSON data from client
            if "report_accident" in data:
                accident_data = data["report_accident"]
                latitude = accident_data["latitude"]
                longitude = accident_data["longitude"]
                description = accident_data["description"]

                # Save accident to database
                db = SessionLocal()
                new_accident = Accident(latitude=latitude, longitude=longitude, description=description)
                db.add(new_accident)
                db.commit()
                db.refresh(new_accident)

                # Notify nearby vehicles
                for conn in active_connections:
                    if is_nearby(latitude, longitude, conn["lat"], conn["lon"]):
                        await conn["ws"].send_json({
                            "alert": f"🚨 {description} near your location!",
                            "latitude": latitude,
                            "longitude": longitude
                        })

                # Acknowledge accident report
                await websocket.send_json({"message": "Accident reported successfully", "id": new_accident.id})

    except WebSocketDisconnect:
        active_connections.remove(connection)
