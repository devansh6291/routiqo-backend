from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import math
import random
from datetime import datetime, timedelta

# --- CONFIG ---
# PASTE YOUR NEON URL HERE
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- SETUP ---
app = FastAPI(title="Routiqo Pro")

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

class SettingsUpdate(BaseModel):
    refresh_rate: str
    distance_unit: str

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
            "on_time_rate": "96%",
            "parking_saved": "182 min",
            "active_vehicles": vehicles,
            "pending_orders": pending
        }

# --- FLEET MANAGEMENT ---
@app.get("/api/fleet")
def get_fleet():
    with SessionLocal() as db:
        res = db.execute(text("SELECT * FROM vehicles ORDER BY id"))
        return [dict(row._mapping) for row in res]

@app.post("/api/vehicles")
def add_vehicle(v: VehicleCreate):
    with SessionLocal() as db:
        # Defaults: Fuel=100, Status=Available, Location=Indore Center
        query = text(f"""
            INSERT INTO vehicles (name, type, capacity, fuel_level, status, lat, lng)
            VALUES ('{v.name}', '{v.type}', {v.capacity}, 100, 'Available', 22.7196, 75.8577)
        """)
        db.execute(query)
        db.commit()
    return {"message": "Vehicle Added"}

# --- LIVE TRACKING ---
@app.get("/api/tracking")
def get_live_tracking():
    """Simulates drivers moving slightly for the live map"""
    with SessionLocal() as db:
        vehicles = [dict(row._mapping) for row in db.execute(text("SELECT * FROM vehicles WHERE status != 'Maintenance'"))]
        
        updated_vehicles = []
        for v in vehicles:
            # Jiggle the coordinates slightly to simulate movement
            new_lat = v['lat'] + random.uniform(-0.001, 0.001)
            new_lng = v['lng'] + random.uniform(-0.001, 0.001)
            
            # Update DB (optional, but good for persistence)
            # db.execute(text(f"UPDATE vehicles SET lat={new_lat}, lng={new_lng} WHERE id={v['id']}"))
            
            updated_vehicles.append({
                "id": v['id'], "name": v['name'], "type": v['type'],
                "lat": new_lat, "lng": new_lng, "status": v['status']
            })
            
        # db.commit()
        return updated_vehicles

# --- ORDERS ---
@app.get("/api/orders")
def get_orders():
    with SessionLocal() as db:
        res = db.execute(text("SELECT * FROM orders ORDER BY id DESC"))
        return [dict(row._mapping) for row in res]

@app.post("/api/orders")
def create_order(o: OrderCreate):
    with SessionLocal() as db:
        db.execute(text(f"""
            INSERT INTO orders (customer, address, lat, lng, priority, time_window, status) 
            VALUES ('{o.customer}', '{o.address}', {o.lat}, {o.lng}, {o.priority}, '{o.time_window}', 'Pending')
        """))
        db.commit()
    return {"message": "Order Created"}

# --- OPTIMIZATION ENGINE ---
@app.get("/api/optimize")
def run_optimization(strategy: str = "balanced", vehicles: int = 3):
    with SessionLocal() as db:
        orders = [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders WHERE status='Pending'"))]
        zones = [dict(row._mapping) for row in db.execute(text("SELECT * FROM parking_zones"))]
        
        if not orders: return {"routes": []}

        # COLOR LOGIC based on Strategy
        # Parking First = Green/Teal (Safe)
        # Time First = Blue/Indigo (Fast)
        # Balanced = Orange/Amber (Middle)
        
        base_color = "#3b82f6" # Default Blue
        if strategy == "parking":
            colors = ['#10b981', '#059669', '#34d399'] # Greens
        elif strategy == "speed":
            colors = ['#3b82f6', '#2563eb', '#60a5fa'] # Blues
        else:
            colors = ['#f59e0b', '#d97706', '#fbbf24'] # Oranges
            
        routes = []
        
        # Simple Logic: Assign orders to vehicles cyclically
        for i in range(vehicles):
            vehicle_stops = []
            assigned_orders = orders[i::vehicles] # Python slice magic
            
            total_time = 0
            savings = 0
            
            for order in assigned_orders:
                # Find Parking
                best_zone = None
                min_dist = 999
                for z in zones:
                    d = math.sqrt((order['lat'] - z['lat'])**2 + (order['lng'] - z['lng'])**2)
                    if d < min_dist:
                        min_dist = d
                        best_zone = z
                
                # Check Time Window Compliance (Simulation)
                is_on_time = True
                
                vehicle_stops.append({
                    "lat": order['lat'], "lng": order['lng'],
                    "customer": order['customer'],
                    "parking": best_zone['name'] if best_zone else "Street",
                    "time_window": order['time_window'],
                    "compliance": "On Time" if is_on_time else "Late"
                })
                
                savings += random.randint(5, 15)
                total_time += random.randint(15, 30)

            if vehicle_stops:
                routes.append({
                    "vehicle_id": f"V-{i+1}",
                    "color": colors[i % len(colors)],
                    "strategy_label": strategy.upper(),
                    "total_time": total_time,
                    "savings": savings,
                    "stops": vehicle_stops
                })
                
        return {"routes": routes}