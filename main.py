from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import math
import random
from datetime import datetime

# --- CONFIG ---
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- SETUP ---
app = FastAPI(title="Routiqo Enterprise")
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
        vehicles = db.execute(text("SELECT COUNT(*) FROM vehicles WHERE status='On Route'")).scalar()
        pending = db.execute(text("SELECT COUNT(*) FROM orders WHERE status='Pending'")).scalar()
        return {
            "on_time_rate": "97.5%",
            "hub_efficiency": "92%",
            "active_vehicles": vehicles,
            "pending_orders": pending,
            "alerts": ["Heavy traffic in North Zone", "Van-04 requires maintenance"]
        }

@app.get("/api/profile")
def get_profile():
    with SessionLocal() as db:
        prof = db.execute(text("SELECT * FROM user_profile LIMIT 1")).fetchone()
        if prof: return dict(prof._mapping)
        return {}

# --- HUB & SPOKE ENDPOINTS ---
@app.get("/api/hubs")
def get_hubs():
    with SessionLocal() as db:
        hubs = db.execute(text("SELECT * FROM hubs"))
        return [dict(row._mapping) for row in hubs]

@app.get("/api/optimize")
def run_hub_spoke_optimization(strategy: str = "balanced", vehicles: int = 3):
    with SessionLocal() as db:
        orders = [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders WHERE status='Pending'"))]
        hubs = [dict(row._mapping) for row in db.execute(text("SELECT * FROM hubs"))]
        
        if not orders or not hubs: return {"routes": []}

        # HUB & SPOKE LOGIC:
        # 1. Identify Primary Hub (Central Depot)
        main_hub = hubs[0] 
        
        routes = []
        colors = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6'] # Green, Blue, Orange, Purple
        
        # 2. Cluster Orders (Simple Simulation: Divide list by vehicle count)
        chunk_size = math.ceil(len(orders) / vehicles)
        order_chunks = [orders[i:i + chunk_size] for i in range(0, len(orders), chunk_size)]

        for i, chunk in enumerate(order_chunks):
            if i >= vehicles: break
            
            # Route starts at HUB
            stops = [{"lat": main_hub['lat'], "lng": main_hub['lng'], "type": "HUB", "name": main_hub['name']}]
            
            # Visit Orders (Spokes)
            for order in chunk:
                stops.append({
                    "lat": order['lat'], "lng": order['lng'], 
                    "type": "STOP", "name": order['customer'],
                    "window": order['time_window']
                })
            
            # Return to HUB
            stops.append({"lat": main_hub['lat'], "lng": main_hub['lng'], "type": "HUB", "name": "Return to Depot"})

            routes.append({
                "vehicle_id": f"V-{i+1}",
                "color": colors[i % len(colors)],
                "stops": stops,
                "total_dist": f"{random.randint(12, 30)} km"
            })
            
        return {"routes": routes}

# --- STANDARD ENDPOINTS (Fleet, Orders, Live Tracking) ---
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
        return [{"id": v.id, "name": v.name, "lat": v.lat + random.uniform(-0.001,0.001), "lng": v.lng + random.uniform(-0.001,0.001), "status": v.status} for v in vehs]

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