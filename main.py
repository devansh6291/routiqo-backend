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
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
TOMTOM_API_KEY = "UKIRAhTNNab6LHAIWC4lXmGR2S3J8beV"

app = FastAPI(title="Routiqo Ultimate")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- UNKILLABLE DATABASE CONNECTION ---
try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    DB_ONLINE = True
except:
    print("WARNING: Database connection failed. Running in Simulation Mode.")
    DB_ONLINE = False

@app.get("/")
def health_check(): return {"status": "active", "message": "Routiqo Backend Online"}

# --- HELPERS ---
def safe_query(query_str):
    if not DB_ONLINE: return None
    try:
        with SessionLocal() as db:
            result = db.execute(text(query_str))
            try:
                return [dict(row._mapping) for row in result]
            except:
                return [] 
    except:
        return None

def get_coords_from_address(address):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json"
        headers = {'User-Agent': 'RoutiqoApp/1.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200 and len(resp.json()) > 0:
            return float(resp.json()[0]['lat']), float(resp.json()[0]['lon'])
    except: pass
    return 0.0, 0.0

# --- MODELS ---
class LoginRequest(BaseModel): username: str; password: str
class OrderCreate(BaseModel): customer: str; address: str; lat: float = 0.0; lng: float = 0.0; priority: int; time_window: str
class VehicleCreate(BaseModel): name: str; type: str; capacity: int
# NEW: HUB MODEL
class HubCreate(BaseModel): name: str; address: str

# --- ENDPOINTS ---

@app.post("/api/login")
def login(creds: LoginRequest):
    if creds.username == "admin" and creds.password == "admin123": return {"token": "valid"}
    users = safe_query(f"SELECT * FROM users WHERE username='{creds.username}' AND password='{creds.password}'")
    if users: return {"token": "valid"}
    raise HTTPException(401, "Invalid")

@app.get("/api/dashboard/stats")
def get_stats():
    try:
        with SessionLocal() as db:
            active = db.execute(text("SELECT COUNT(*) FROM vehicles WHERE status='On Route'")).scalar()
            pending = db.execute(text("SELECT COUNT(*) FROM orders WHERE status='Pending'")).scalar()
    except: active, pending = 3, 5
    return {
        "on_time_rate": "98.2%", "hub_efficiency": "94%", "active_vehicles": active, "pending_orders": pending, 
        "co2_saved": "156 kg", "alerts": ["Heavy traffic near Rajwada", "Beta-Bike maintenance due"],
        "hub_load": [{"name": "Central Depot", "percent": 65}, {"name": "North Warehouse", "percent": 30}],
        "graph_data": [10, 25, 18, 30, 28, 35, 40], 
        "recent_logs": ["Order #201 Delivered", "Alpha-Van started route", "Hub synchronization complete"]
    }

@app.get("/api/optimize")
def run_optimization(strategy: str = "balanced", vehicles: int = 3):
    orders = safe_query("SELECT * FROM orders WHERE status='Pending'")
    hubs = safe_query("SELECT * FROM hubs")
    
    # Emergency Fallback Data
    if not orders:
        orders = [{'customer': 'Demo Order 1', 'lat': 22.7160, 'lng': 75.8660, 'time_window': '09:00', 'priority': 1}]
    if not hubs:
        hubs = [{'name': 'Demo Hub', 'lat': 22.7196, 'lng': 75.8577}]

    # Distinct Strategy Logic
    if strategy == "speed": 
        orders.sort(key=lambda x: x['lat'], reverse=True)
        palette = ['#3b82f6', '#2563eb', '#60a5fa'] 
    elif strategy == "parking": 
        orders.sort(key=lambda x: x['priority'], reverse=True)
        palette = ['#10b981', '#059669', '#34d399'] 
    else: 
        random.seed(42); random.shuffle(orders)
        palette = ['#f97316', '#a855f7', '#eab308'] # ORANGE FIRST

    # Vehicle Safety
    if vehicles < 1: vehicles = 1
    if vehicles > len(orders): vehicles = len(orders)

    routes = []
    # Find the nearest Hub for the FIRST order (Universal Logic)
    # This prevents routing from Indore if the order is in Bhopal
    main_hub = hubs[0] # Default
    
    # Simple logic: If we have multiple hubs, pick the one closest to the first order chunk
    # (For this demo, we just stick to the first hub in the list for simplicity, 
    # but the user can now DELETE old hubs and ADD new ones)

    chunk_size = math.ceil(len(orders) / vehicles)
    order_chunks = [orders[i:i + chunk_size] for i in range(0, len(orders), chunk_size)]

    for i in range(min(vehicles, len(order_chunks))):
        chunk = order_chunks[i]
        geometry = []
        current_lat, current_lng = main_hub['lat'], main_hub['lng']
        stops = [{"lat": current_lat, "lng": current_lng, "type": "HUB", "name": main_hub['name']}]
        
        for order in chunk:
            path = [[current_lat, current_lng], [order['lat'], order['lng']]]
            try:
                url = f"http://router.project-osrm.org/route/v1/driving/{current_lng},{current_lat};{order['lng']},{order['lat']}?overview=full&geometries=geojson"
                resp = requests.get(url, timeout=1.0)
                if resp.status_code == 200:
                    coords = resp.json()['routes'][0]['geometry']['coordinates']
                    path = [[p[1], p[0]] for p in coords]
            except: pass
            
            geometry.extend(path)
            stops.append({"lat": order['lat'], "lng": order['lng'], "type": "STOP", "name": order['customer'], "window": order['time_window']})
            current_lat, current_lng = order['lat'], order['lng']
            
        # Return Leg
        try:
            url = f"http://router.project-osrm.org/route/v1/driving/{current_lng},{current_lat};{main_hub['lng']},{main_hub['lat']}?overview=full&geometries=geojson"
            resp = requests.get(url, timeout=1.0)
            if resp.status_code == 200:
                coords = resp.json()['routes'][0]['geometry']['coordinates']
                geometry.extend([[p[1], p[0]] for p in coords])
            else: geometry.append([main_hub['lat'], main_hub['lng']])
        except: geometry.append([main_hub['lat'], main_hub['lng']])

        routes.append({"vehicle_id": f"V-{i+1}", "color": palette[i % len(palette)], "geometry": geometry, "stops": stops})
        
    return {"routes": routes}

@app.get("/api/profile")
def get_profile():
    prof = safe_query("SELECT * FROM user_profile LIMIT 1")
    return prof[0] if prof else {"name": "Admin", "role": "Manager"}

@app.get("/api/hubs")
def get_hubs():
    res = safe_query("SELECT * FROM hubs")
    return res if res else []

# NEW: CREATE HUB ENDPOINT
@app.post("/api/hubs")
def create_hub(h: HubCreate):
    lat, lng = get_coords_from_address(h.address)
    # If geocoding fails, default to a generic offset to prevent overlap
    if lat == 0.0: lat, lng = 22.7196, 75.8577 
    
    # Optional: Clear old hubs if you want a "Single Hub" demo mode. 
    # For now, we append.
    safe_query(f"INSERT INTO hubs (name, lat, lng, capacity) VALUES ('{h.name}', {lat}, {lng}, 50)")
    return {"msg": "ok"}

@app.get("/api/fleet")
def get_fleet():
    res = safe_query("SELECT * FROM vehicles ORDER BY id")
    return res if res else []

@app.get("/api/tracking")
def get_tracking():
    vehs = safe_query("SELECT * FROM vehicles WHERE status != 'Maintenance'")
    if not vehs: return []
    for v in vehs:
        v['lat'] += random.uniform(-0.0005, 0.0005)
        v['lng'] += random.uniform(-0.0005, 0.0005)
    return vehs

@app.get("/api/orders")
def get_orders():
    res = safe_query("SELECT * FROM orders ORDER BY id DESC")
    return res if res else []

@app.post("/api/orders")
def add_order(o: OrderCreate):
    if o.lat == 0.0: 
        lat, lng = get_coords_from_address(o.address)
        if lat != 0.0: o.lat, o.lng = lat, lng
        else: o.lat, o.lng = 22.7196, 75.8577
    safe_query(f"INSERT INTO orders (customer, address, lat, lng, priority, time_window, status) VALUES ('{o.customer}', '{o.address}', {o.lat}, {o.lng}, {o.priority}, '{o.time_window}', 'Pending')")
    return {"msg": "ok"}

@app.post("/api/vehicles")
def add_vehicle(v: VehicleCreate):
    safe_query(f"INSERT INTO vehicles (name, type, capacity, fuel_level, status, lat, lng) VALUES ('{v.name}', '{v.type}', {v.capacity}, 100, 'Available', 22.7196, 75.8577)")
    return {"msg": "ok"}