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
# PASTE YOUR TOMTOM KEY HERE
TOMTOM_API_KEY = "UKIRAhTNNab6LHAIWC4lXmGR2S3J8beV"

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

# --- HEALTH CHECK ---
@app.get("/")
def health_check():
    return {"status": "active", "message": "Routiqo Backend Online"}

# --- ROUTING ENGINE (FIXED GEOMETRY) ---
def get_road_geometry(start_lat, start_lng, end_lat, end_lng):
    """
    Fetches exact road geometry. 
    CRITICAL FIX: Ensures coordinates are returned as [Lat, Lng] for Leaflet.
    """
    # 1. Try TomTom First (Most Accurate)
    if TOMTOM_API_KEY != "YOUR_TOMTOM_API_KEY":
        try:
            base_url = "https://api.tomtom.com/routing/1/calculateRoute"
            locations = f"{start_lat},{start_lng}:{end_lat},{end_lng}"
            url = f"{base_url}/{locations}/json?traffic=true&routeRepresentation=polyline&key={TOMTOM_API_KEY}"
            
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                pts = resp.json()['routes'][0]['legs'][0]['points']
                # TomTom returns {latitude, longitude}, we convert to [Lat, Lng]
                return [[p['latitude'], p['longitude']] for p in pts]
        except:
            pass # Fallback to OSRM

    # 2. Try OSRM (Backup - Free)
    try:
        # OSRM expects {Lng},{Lat}
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}?overview=full&geometries=geojson"
        resp = requests.get(url, timeout=2)
        if resp.status_code == 200:
            coords = resp.json()['routes'][0]['geometry']['coordinates']
            # OSRM returns [Lng, Lat]. We SWAP to [Lat, Lng]
            return [[p[1], p[0]] for p in coords]
    except:
        pass

    # 3. Fallback (Straight Line)
    return [[start_lat, start_lng], [end_lat, end_lng]]

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
        active = db.execute(text("SELECT COUNT(*) FROM vehicles WHERE status='On Route'")).scalar()
        pending = db.execute(text("SELECT COUNT(*) FROM orders WHERE status='Pending'")).scalar()
        return {
            "on_time_rate": "98.2%",
            "hub_efficiency": "94%",
            "active_vehicles": active,
            "pending_orders": pending,
            "co2_saved": "156 kg", 
            "alerts": ["Heavy traffic near Rajwada", "Beta-Bike maintenance due"],
            "hub_load": [{"name": "Central Depot", "percent": 65}, {"name": "North Warehouse", "percent": 30}],
            "graph_data": [10, 25, 18, 30, 28, 35, 40], 
            "recent_logs": ["Order #201 Delivered", "Alpha-Van started route", "Hub synchronization complete"]
        }

@app.get("/api/profile")
def get_profile():
    with SessionLocal() as db:
        prof = db.execute(text("SELECT * FROM user_profile LIMIT 1")).fetchone()
        return dict(prof._mapping) if prof else {"name": "Admin", "role": "Manager"}

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

        if strategy == "parking": palette = ['#10b981', '#059669'] 
        elif strategy == "speed": palette = ['#3b82f6', '#2563eb']
        else: palette = ['#f59e0b', '#8b5cf6']

        routes = []
        main_hub = hubs[0] 
        chunk_size = math.ceil(len(orders) / vehicles) if len(orders) > 0 else 1
        order_chunks = [orders[i:i + chunk_size] for i in range(0, len(orders), chunk_size)]

        for i in range(min(vehicles, len(order_chunks))):
            chunk = order_chunks[i]
            geometry = []
            current_lat, current_lng = main_hub['lat'], main_hub['lng']
            
            # Start at Hub
            stops = [{"lat": current_lat, "lng": current_lng, "type": "HUB", "name": main_hub['name']}]

            for order in chunk:
                # Get Geometry
                path = get_road_geometry(current_lat, current_lng, order['lat'], order['lng'])
                geometry.extend(path)
                
                stops.append({"lat": order['lat'], "lng": order['lng'], "type": "STOP", "name": order['customer'], "window": order['time_window']})
                current_lat, current_lng = order['lat'], order['lng']

            # Return to Hub
            path_back = get_road_geometry(current_lat, current_lng, main_hub['lat'], main_hub['lng'])
            geometry.extend(path_back)

            routes.append({
                "vehicle_id": f"V-{i+1}",
                "color": palette[i % len(palette)],
                "geometry": geometry,
                "stops": stops
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
            # Jitter
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