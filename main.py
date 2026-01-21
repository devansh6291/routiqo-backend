from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import math
import random
import requests # <--- NEW IMPORT
from datetime import datetime

# --- CONFIG ---
# PASTE YOUR NEON URL HERE
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
TOMTOM_API_KEY = "UKIRAhTNNab6LHAIWC4lXmGR2S3J8beV" # <--- PASTE KEY HERE

app = FastAPI(title="Routiqo Ultimate")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# --- TOMTOM TRAFFIC HELPER ---
def get_real_traffic_data(start_lat, start_lng, end_lat, end_lng):
    """
    Queries TomTom Routing API to get real-time travel duration considering traffic.
    """
    # If no key provided, return simulation immediately to prevent crash
    if TOMTOM_API_KEY == "YOUR_TOMTOM_API_KEY": 
        return random.randint(15, 45), random.uniform(2, 10)

    base_url = "https://api.tomtom.com/routing/1/calculateRoute"
    locations = f"{start_lat},{start_lng}:{end_lat},{end_lng}"
    
    url = f"{base_url}/{locations}/json?traffic=true&key={TOMTOM_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # Extract real data
        summary = data['routes'][0]['summary']
        travel_time = summary['travelTimeInSeconds'] // 60 # Convert to minutes
        distance_km = round(summary['lengthInMeters'] / 1000, 1)
        
        return travel_time, distance_km
    except Exception as e:
        print(f"TomTom API Error: {e}")
        # Fallback to simulation if API fails/quota exceeded
        return random.randint(15, 45), random.uniform(2, 10)


# --- HEALTH CHECK (REQUIRED FOR RENDER) ---
@app.get("/")
def health_check():
    return {"status": "active", "message": "Routiqo Backend is Online"}

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
class VehicleCreate(BaseModel):
    name: str
    type: str
    capacity: int

# --- API ENDPOINTS ---

@app.post("/api/login")
def login(creds: LoginRequest):
    with SessionLocal() as db:
        user = db.execute(text(f"SELECT * FROM users WHERE username='{creds.username}' AND password='{creds.password}'")).fetchone()
        if user: return {"token": "valid"}
        raise HTTPException(401, "Invalid")

@app.get("/api/dashboard/stats")
def get_stats():
    with SessionLocal() as db:
        total = db.execute(text("SELECT COUNT(*) FROM orders")).scalar()
        active = db.execute(text("SELECT COUNT(*) FROM vehicles WHERE status='On Route'")).scalar()
        pending = db.execute(text("SELECT COUNT(*) FROM orders WHERE status='Pending'")).scalar()
        
        return {
            "on_time_rate": "97.5%",
            "hub_efficiency": "92%",
            "active_vehicles": active,
            "pending_orders": pending,
            "co2_saved": "142 kg", 
            "alerts": ["Heavy traffic in North Zone", "Alpha-Van Low Fuel"],
            "hub_load": [
                {"name": "Central Depot", "percent": 75},
                {"name": "North Warehouse", "percent": 40}
            ],
            "graph_data": [12, 19, 15, 25, 22, 30, 28], 
            "recent_logs": [
                "Order #104 delivered by Alpha-Van",
                "Beta-Bike reached South Hub",
                "New order received from Starbucks",
                "Shift started for Driver Raj"
            ]
        }

@app.get("/api/profile")
def get_profile():
    with SessionLocal() as db:
        prof = db.execute(text("SELECT * FROM user_profile LIMIT 1")).fetchone()
        if prof: return dict(prof._mapping)
        return {"name": "Admin", "role": "Manager"}

@app.get("/api/hubs")
def get_hubs():
    with SessionLocal() as db:
        return [dict(row._mapping) for row in db.execute(text("SELECT * FROM hubs"))]

@app.get("/api/optimize")
def run_optimization(strategy: str = "balanced", vehicles: int = 3):
    with SessionLocal() as db:
        orders = [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders WHERE status='Pending'"))]
        hubs = [dict(row._mapping) for row in db.execute(text("SELECT * FROM hubs"))]
        
        if not orders or not hubs: return {"routes": []}

        if strategy == "parking":
            palette = ['#10b981', '#059669', '#34d399', '#064e3b']
        elif strategy == "speed":
            palette = ['#3b82f6', '#2563eb', '#60a5fa', '#1e40af']
        else:
            palette = ['#f59e0b', '#8b5cf6', '#d97706', '#7c3aed']

        routes = []
        main_hub = hubs[0] 
        
        chunk_size = math.ceil(len(orders) / vehicles) if len(orders) > 0 else 1
        order_chunks = [orders[i:i + chunk_size] for i in range(0, len(orders), chunk_size)]

        for i in range(min(vehicles, len(order_chunks))):
            chunk = order_chunks[i]
            
            # 1. Start at HUB
            stops = [{"lat": main_hub['lat'], "lng": main_hub['lng'], "type": "HUB", "name": main_hub['name']}]
            
            current_lat = main_hub['lat']
            current_lng = main_hub['lng']
            total_time_min = 0

            # 2. Visit Spokes (WITH REAL TRAFFIC DATA)
            for order in chunk:
                # Calculate real traffic time from previous point to this order
                t_time, t_dist = get_real_traffic_data(current_lat, current_lng, order['lat'], order['lng'])
                
                stops.append({
                    "lat": order['lat'], 
                    "lng": order['lng'], 
                    "type": "STOP", 
                    "name": order['customer'], 
                    "window": order['time_window'],
                    "travel_time": f"{t_time} min" # Added this to show in frontend if needed
                })
                
                # Update current location for next leg
                current_lat = order['lat']
                current_lng = order['lng']
                total_time_min += t_time

            # 3. Return to HUB
            t_time_back, t_dist_back = get_real_traffic_data(current_lat, current_lng, main_hub['lat'], main_hub['lng'])
            stops.append({"lat": main_hub['lat'], "lng": main_hub['lng'], "type": "HUB", "name": "Return"})
            
            routes.append({
                "vehicle_id": f"V-{i+1}",
                "color": palette[i % len(palette)],
                "stops": stops,
                "est_duration": f"{total_time_min + t_time_back} min"
            })
            
        return {"routes": routes}

@app.get("/api/fleet")
def get_fleet():
    with SessionLocal() as db:
        return [dict(row._mapping) for row in db.execute(text("SELECT * FROM vehicles ORDER BY id"))]

@app.post("/api/vehicles")
def add_vehicle(v: VehicleCreate):
    with SessionLocal() as db:
        db.execute(text(f"INSERT INTO vehicles (name, type, capacity, fuel_level, status, lat, lng) VALUES ('{v.name}', '{v.type}', {v.capacity}, 100, 'Available', 22.7196, 75.8577)"))
        db.commit()
    return {"msg": "ok"}

@app.get("/api/tracking")
def get_tracking():
    with SessionLocal() as db:
        vehs = db.execute(text("SELECT * FROM vehicles WHERE status != 'Maintenance'"))
        results = []
        for v in vehs:
            new_lat = v.lat + random.uniform(-0.0005, 0.0005)
            new_lng = v.lng + random.uniform(-0.0005, 0.0005)
            results.append({"id": v.id, "name": v.name, "lat": new_lat, "lng": new_lng, "status": v.status})
        return results

@app.get("/api/orders")
def get_orders():
    with SessionLocal() as db:
        return [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders ORDER BY id DESC"))]

@app.post("/api/orders")
def add_order(o: OrderCreate):
    with SessionLocal() as db:
        db.execute(text(f"INSERT INTO orders (customer, address, lat, lng, priority, time_window, status) VALUES ('{o.customer}', '{o.address}', {o.lat}, {o.lng}, {o.priority}, '{o.time_window}', 'Pending')"))
        db.commit()
    return {"msg": "ok"}