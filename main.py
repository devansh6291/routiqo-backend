from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
import math
from datetime import datetime

# --- CONFIGURATION ---
# PASTE YOUR NEON DATABASE URL HERE
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- APP SETUP ---
app = FastAPI(title="Routiqo Pro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE SETUP ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- DATA MODELS (Pydantic) ---
class LoginRequest(BaseModel):
    username: str
    password: str

class OrderCreate(BaseModel):
    customer_name: str
    address: str
    latitude: float
    longitude: float
    priority_score: int
    time_window_start: str
    time_window_end: str

class DriverCreate(BaseModel):
    name: str
    phone: str

# --- AUTH ROUTES ---
@app.post("/login")
def login(creds: LoginRequest):
    with SessionLocal() as db:
        # Simple hackathon auth
        user = db.execute(text(f"SELECT * FROM users WHERE username='{creds.username}' AND password_hash='{creds.password}'")).fetchone()
        if user:
            return {"token": "fake-jwt-token-123", "message": "Login Successful"}
        raise HTTPException(status_code=401, detail="Invalid Credentials")

# --- MANAGEMENT ROUTES ---
@app.post("/orders")
def create_order(order: OrderCreate):
    with SessionLocal() as db:
        query = text("""
            INSERT INTO orders (customer_name, address, latitude, longitude, priority_score, time_window_start, time_window_end, status)
            VALUES (:name, :addr, :lat, :lon, :prio, :start, :end, 'pending')
        """)
        db.execute(query, {
            "name": order.customer_name, "addr": order.address, "lat": order.latitude, "lon": order.longitude,
            "prio": order.priority_score, "start": order.time_window_start, "end": order.time_window_end
        })
        db.commit()
    return {"message": "Order Added"}

@app.post("/drivers")
def create_driver(driver: DriverCreate):
    with SessionLocal() as db:
        db.execute(text("INSERT INTO drivers (name, phone) VALUES (:name, :phone)"), 
                   {"name": driver.name, "phone": driver.phone})
        db.commit()
    return {"message": "Driver Added"}

@app.get("/drivers")
def get_drivers():
    with SessionLocal() as db:
        result = db.execute(text("SELECT * FROM drivers"))
        return [dict(row._mapping) for row in result]

@app.get("/vehicles")
def get_vehicles():
    with SessionLocal() as db:
        result = db.execute(text("SELECT * FROM vehicles"))
        return [dict(row._mapping) for row in result]

@app.get("/dashboard-stats")
def get_stats():
    with SessionLocal() as db:
        stops = db.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        active_drivers = db.execute(text("SELECT COUNT(*) FROM drivers WHERE status='On Route'")).scalar()
        return {
            "on_time_rate": "94%", 
            "parking_saved": "56 min", 
            "total_stops": stops,
            "active_drivers": active_drivers
        }

# --- THE SUPER OPTIMIZER ---
@app.get("/optimize-routes")
def run_optimization():
    """
    Features:
    1. Parking-First [cite: 51]
    2. Time Window Check 
    3. Priority Sorting 
    """
    with SessionLocal() as db:
        # Fetch Data
        orders = [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders WHERE status != 'delivered'"))]
        zones = [dict(row._mapping) for row in db.execute(text("SELECT * FROM parking_zones"))]
        
        # Sort by Priority (High to Low) 
        orders.sort(key=lambda x: x['priority_score'], reverse=True)
        
        routes = []
        current_time_sim = "10:00" # Simulating 10 AM

        for order in orders:
            # 1. Check Time Window 
            status_note = "On Time"
            if order['time_window_start'] > current_time_sim:
                status_note = "Early Arrival (Wait)"
            
            # 2. Find Parking (Parking-First Logic)
            best_zone = None
            min_dist = 999999
            for zone in zones:
                dist = math.sqrt((order['latitude'] - zone['latitude'])**2 + (order['longitude'] - zone['longitude'])**2)
                if dist < min_dist:
                    min_dist = dist
                    best_zone = zone
            
            # 3. Calculate Risk
            risk = "SAFE"
            if best_zone and best_zone['availability_score'] < 30:
                risk = "HIGH_RISK"
            if not best_zone:
                risk = "CRITICAL (No Parking)"

            routes.append({
                "customer": order['customer_name'],
                "priority": order['priority_score'],
                "location": {"lat": order['latitude'], "lng": order['longitude']},
                "parking": best_zone['name'] if best_zone else "None",
                "risk": risk,
                "time_window": f"{order['time_window_start']} - {order['time_window_end']}",
                "status_note": status_note
            })
            
        return {"routes": routes}