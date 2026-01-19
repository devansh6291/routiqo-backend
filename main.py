from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import math
import random
from typing import List, Optional

# --- CONFIG ---
# PASTE YOUR NEON URL HERE (Make sure it starts with postgresql://)
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- SETUP ---
app = FastAPI(title="Routiqo Enterprise API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# --- MODELS ---
class LoginRequest(BaseModel):
    username: str
    password: str

class OrderCreate(BaseModel):
    customer: str
    address: str
    lat: float
    lng: float
    priority: int
    time_window: str

# --- API ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "online", "system": "Routiqo Enterprise"}

@app.post("/api/login")
def login(creds: LoginRequest):
    with SessionLocal() as db:
        user = db.execute(text(f"SELECT * FROM users WHERE username='{creds.username}' AND password='{creds.password}'")).fetchone()
        if user: 
            return {
                "token": "admin-jwt-token",
                "user": {"name": "Code Blooded", "role": "Fleet Manager"}
            }
        raise HTTPException(401, "Invalid Credentials")

@app.get("/api/dashboard/stats")
def get_stats():
    """Returns real-time metrics for the top cards"""
    with SessionLocal() as db:
        total_orders = db.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        active_vehicles = db.execute(text("SELECT COUNT(*) FROM vehicles WHERE status='Available'")).scalar()
        pending_orders = db.execute(text("SELECT COUNT(*) FROM orders WHERE status='Pending'")).scalar()
        
        # Simulated Efficiency Calculation
        efficiency = random.randint(88, 96)
        
        return {
            "on_time_rate": f"{efficiency}%",
            "avg_time": "32 min",
            "parking_saved": "145 min",
            "total_stops": total_orders,
            "active_vehicles": active_vehicles,
            "pending_orders": pending_orders
        }

@app.get("/api/fleet")
def get_fleet():
    """Returns combined Vehicle + Driver data"""
    with SessionLocal() as db:
        query = text("""
            SELECT v.id, v.name as vehicle_name, v.type, v.fuel_level, v.status, 
                   d.name as driver_name, d.rating 
            FROM vehicles v 
            LEFT JOIN drivers d ON v.driver_id = d.id
        """)
        fleet = [dict(row._mapping) for row in db.execute(query)]
        return fleet

@app.get("/api/orders")
def get_orders():
    with SessionLocal() as db:
        orders = db.execute(text("SELECT * FROM orders ORDER BY priority DESC, id DESC"))
        return [dict(row._mapping) for row in orders]

@app.post("/api/orders")
def create_order(o: OrderCreate):
    with SessionLocal() as db:
        query = text("""
            INSERT INTO orders (customer, address, lat, lng, priority, time_window, status) 
            VALUES (:cust, :addr, :lat, :lng, :prio, :window, 'Pending')
        """)
        db.execute(query, {
            "cust": o.customer, "addr": o.address, "lat": o.lat, "lng": o.lng, 
            "prio": o.priority, "window": o.time_window
        })
        db.commit()
    return {"message": "Order Created"}

@app.get("/api/optimize")
def run_optimization(strategy: str = "balanced", vehicles: int = 3):
    """
    The Core Engine: 
    1. Fetches Orders & Parking Zones.
    2. Simulates Route Assignment based on Vehicle Count.
    3. Calculates Risk Scores.
    """
    with SessionLocal() as db:
        orders = [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders WHERE status='Pending'"))]
        zones = [dict(row._mapping) for row in db.execute(text("SELECT * FROM parking_zones"))]
        
        if not orders:
            return {"routes": []}

        # --- SIMULATED ROUTING ALGORITHM ---
        routes = []
        colors = ['#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
        
        # Split orders among vehicles (Simple Round Robin for Demo)
        chunks = [[] for _ in range(vehicles)]
        for i, order in enumerate(orders):
            chunks[i % vehicles].append(order)
            
        for i in range(vehicles):
            vehicle_stops = chunks[i]
            if not vehicle_stops: continue
            
            processed_stops = []
            total_time = 0
            savings = 0
            
            for stop in vehicle_stops:
                # Find best parking
                best_zone = None
                min_dist = 999
                
                for z in zones:
                    d = math.sqrt((stop['lat'] - z['lat'])**2 + (stop['lng'] - z['lng'])**2)
                    if d < min_dist:
                        min_dist = d
                        best_zone = z
                
                # Risk Logic
                risk = "Safe"
                if best_zone and best_zone['score'] < 40:
                    risk = "High Risk"
                
                # Time Simulation
                travel_time = random.randint(10, 25)
                parking_time_saved = random.randint(5, 15) if risk == "Safe" else 0
                
                total_time += travel_time
                savings += parking_time_saved
                
                processed_stops.append({
                    "id": stop['id'],
                    "customer": stop['customer'],
                    "address": stop['address'],
                    "lat": stop['lat'],
                    "lng": stop['lng'],
                    "risk": risk,
                    "parking_zone": best_zone['name'] if best_zone else "Street Parking",
                    "arrival_time": f"{9 + i}:{random.randint(10, 59)}",
                    "status": "Scheduled"
                })
            
            routes.append({
                "vehicle_id": f"Vehicle-{i+1}",
                "driver": f"Driver {i+1}",
                "color": colors[i % len(colors)],
                "total_time": total_time,
                "parking_savings": savings,
                "stops": processed_stops
            })
            
        return {"routes": routes}