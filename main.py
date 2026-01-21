from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import math
import random
import requests
from datetime import datetime

# --- CONFIG ---
# PASTE YOUR NEON URL HERE
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
TOMTOM_API_KEY = "UKIRAhTNNab6LHAIWC4lXmGR2S3J8beV" # <--- PASTE YOUR TOMTOM KEY HERE

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

# --- HEALTH CHECK (REQUIRED FOR RENDER) ---
@app.get("/")
def health_check():
    return {"status": "active", "message": "Routiqo Backend is Online"}

# --- TOMTOM TRAFFIC HELPER (UPDATED FOR GEOMETRY) ---
def get_real_traffic_data(start_lat, start_lng, end_lat, end_lng):
    """
    Queries TomTom to get:
    1. Travel Time (min)
    2. Distance (km)
    3. Route Shape (List of [lat, lng] points for drawing)
    """
    if TOMTOM_API_KEY == "UKIRAhTNNab6LHAIWC4lXmGR2S3J8beV": 
        # Simulation Fallback if key is missing
        return 20, 5.5, [[start_lat, start_lng], [end_lat, end_lng]]

    # Ask for Polyline representation (The Shape)
    base_url = "https://api.tomtom.com/routing/1/calculateRoute"
    locations = f"{start_lat},{start_lng}:{end_lat},{end_lng}"
    
    url = f"{base_url}/{locations}/json?traffic=true&routeRepresentation=polyline&key={TOMTOM_API_KEY}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        route_data = data['routes'][0]
        summary = route_data['summary']
        
        # 1. Metrics
        travel_time = summary['travelTimeInSeconds'] // 60
        distance_km = round(summary['lengthInMeters'] / 1000, 1)
        
        # 2. Shape (The magic part)
        # TomTom returns: [{'latitude': 12.3, 'longitude': 45.6}, ...]
        # We need: [[12.3, 45.6], ...] for Leaflet
        points = route_data['legs'][0]['points']
        geometry = [[p['latitude'], p['longitude']] for p in points]
        
        return travel_time, distance_km, geometry
        
    except Exception as e:
        print(f"TomTom API Error: {e}")
        # Fallback: Straight line
        return 20, 5.0, [[start_lat, start_lng], [end_lat, end_lng]]


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

# --- UPDATED OPTIMIZATION ENDPOINT ---
@app.get("/api/optimize")
def run_optimization(strategy: str = "balanced", vehicles: int = 3):
    with SessionLocal() as db:
        orders = [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders WHERE status='Pending'"))]
        hubs = [dict(row._mapping) for row in db.execute(text("SELECT * FROM hubs"))]
        
        if not orders or not hubs: return {"routes": []}

        # Color Palette Logic
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
            
            # Route Data Containers
            route_geometry = [] # Holds ALL points for the vehicle's entire path
            stops_metadata = [] # Holds info about where we stop (markers)

            # 1. Start Leg: HUB -> First Order
            current_lat = main_hub['lat']
            current_lng = main_hub['lng']
            
            # Add Hub Marker info
            stops_metadata.append({"lat": current_lat, "lng": current_lng, "type": "HUB", "name": main_hub['name']})
            
            # 2. Visit Spokes
            for order in chunk:
                # Get road shape to next stop
                t_time, t_dist, shape = get_real_traffic_data(current_lat, current_lng, order['lat'], order['lng'])
                
                # Add shape to main route path
                route_geometry.extend(shape)
                
                # Add Stop Marker info
                stops_metadata.append({"lat": order['lat'], "lng": order['lng'], "type": "STOP", "name": order['customer'], "window": order['time_window']})
                
                # Update current location
                current_lat = order['lat']
                current_lng = order['lng']

            # 3. Return Leg: Last Order -> HUB
            t_time_back, t_dist_back, shape_back = get_real_traffic_data(current_lat, current_lng, main_hub['lat'], main_hub['lng'])
            route_geometry.extend(shape_back)

            routes.append({
                "vehicle_id": f"V-{i+1}",
                "color": palette[i % len(palette)],
                "geometry": route_geometry, # Sending the actual road shape!
                "stops": stops_metadata
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