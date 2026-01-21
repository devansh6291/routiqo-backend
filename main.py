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
DATABASE_URL = "postgresql://neondb_owner:AbCd1234@ep-cool-frog.us-east-2.aws.neon.tech/neondb?sslmode=require"
TOMTOM_API_KEY = "UKIRAhTNNab6LHAIWC4lXmGR2S3J8beV"

app = FastAPI(title="Routiqo Ultimate")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

@app.get("/")
def health_check(): return {"status": "active", "message": "Routiqo Backend Online"}

def get_coords_from_address(address):
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json"
        headers = {'User-Agent': 'RoutiqoApp/1.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200 and len(resp.json()) > 0:
            data = resp.json()[0]
            return float(data['lat']), float(data['lon'])
    except Exception as e: print(f"Geocoding Error: {e}")
    return 22.7196, 75.8577 

def get_osrm_geometry(start_lat, start_lng, end_lat, end_lng):
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}?overview=full&geometries=geojson"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            coords = data['routes'][0]['geometry']['coordinates']
            path = [[p[1], p[0]] for p in coords]
            return path, data['routes'][0]['distance']/1000, data['routes'][0]['duration']/60
    except: pass
    return [[start_lat, start_lng], [end_lat, end_lng]], 5.0, 15.0

class LoginRequest(BaseModel): username: str; password: str
class OrderCreate(BaseModel): customer: str; address: str; lat: float = 0.0; lng: float = 0.0; priority: int; time_window: str
class VehicleCreate(BaseModel): name: str; type: str; capacity: int

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
            "on_time_rate": "98.2%", "hub_efficiency": "94%", "active_vehicles": active, "pending_orders": pending, "co2_saved": "156 kg", 
            "alerts": ["Heavy traffic near Rajwada", "Beta-Bike maintenance due"],
            "hub_load": [{"name": "Central Depot", "percent": 65}, {"name": "North Warehouse", "percent": 30}],
            "graph_data": [10, 25, 18, 30, 28, 35, 40], "recent_logs": ["Order #201 Delivered", "Alpha-Van started route", "Hub synchronization complete"]
        }

@app.get("/api/profile")
def get_profile():
    with SessionLocal() as db:
        prof = db.execute(text("SELECT * FROM user_profile LIMIT 1")).fetchone()
        return dict(prof._mapping) if prof else {"name": "Admin", "role": "Manager"}

@app.get("/api/hubs")
def get_hubs():
    with SessionLocal() as db: return [dict(row._mapping) for row in db.execute(text("SELECT * FROM hubs"))]

@app.get("/api/optimize")
def run_optimization(strategy: str = "balanced", vehicles: int = 3):
    with SessionLocal() as db:
        orders = [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders WHERE status='Pending'"))]
        hubs = [dict(row._mapping) for row in db.execute(text("SELECT * FROM hubs"))]
        if not orders or not hubs: return {"routes": []}
        if strategy == "speed": orders.sort(key=lambda x: x['lat']) 
        elif strategy == "parking": orders.sort(key=lambda x: x['priority'], reverse=True)
        
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
            stops = [{"lat": current_lat, "lng": current_lng, "type": "HUB", "name": main_hub['name']}]
            for order in chunk:
                path, dist, dur = get_osrm_geometry(current_lat, current_lng, order['lat'], order['lng'])
                geometry.extend(path)
                stops.append({"lat": order['lat'], "lng": order['lng'], "type": "STOP", "name": order['customer'], "window": order['time_window']})
                current_lat, current_lng = order['lat'], order['lng']
            path_back, d, t = get_osrm_geometry(current_lat, current_lng, main_hub['lat'], main_hub['lng'])
            geometry.extend(path_back)
            routes.append({"vehicle_id": f"V-{i+1}", "color": palette[i % len(palette)], "geometry": geometry, "stops": stops})
        return {"routes": routes}

@app.get("/api/fleet")
def get_fleet():
    with SessionLocal() as db: return [dict(row._mapping) for row in db.execute(text("SELECT * FROM vehicles ORDER BY id"))]

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
            results.append({"id": v.id, "name": v.name, "lat": v.lat + random.uniform(-0.0005, 0.0005), "lng": v.lng + random.uniform(-0.0005, 0.0005), "status": v.status})
        return results

@app.get("/api/orders")
def get_orders():
    with SessionLocal() as db: return [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders ORDER BY id DESC"))]

@app.post("/api/orders")
def add_order(o: OrderCreate):
    with SessionLocal() as db:
        if o.lat == 0.0 or o.lng == 0.0: lat, lng = get_coords_from_address(o.address)
        else: lat, lng = o.lat, o.lng
        db.execute(text(f"INSERT INTO orders (customer, address, lat, lng, priority, time_window, status) VALUES ('{o.customer}', '{o.address}', {lat}, {lng}, {o.priority}, '{o.time_window}', 'Pending')"))
        db.commit()
    return {"msg": "ok"}