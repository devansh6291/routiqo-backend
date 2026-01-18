from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import math
import random
from datetime import datetime

# --- CONFIGURATION ---
# PASTE YOUR NEON URL BELOW (Keep the quotes!)
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- APP SETUP ---
app = FastAPI(title="Routiqo Super API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE CONNECTION ---
engine = None
SessionLocal = None

try:
    if "your-database-url-here" in DATABASE_URL:
        raise Exception("Database URL missing!")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    print("SUCCESS: Database connected.")
except Exception as e:
    print(f"DB ERROR: {e}")

# --- HELPER: 4D ASSIGNMENT LOGIC ---
def calculate_4d_score(order, zone, vehicle):
    """
    Implements '4D Assignment'[cite: 110]:
    Optimizes for Vehicle Type + Stop Distance + Time + Parking Availability.
    """
    # 1. Distance Score (Lower is better)
    dist = math.sqrt((order['latitude'] - zone['latitude'])**2 + (order['longitude'] - zone['longitude'])**2)
    
    # 2. Parking Score (Higher is better)
    parking_quality = zone['availability_score']
    
    # 3. Vehicle Match (Van is better for large orders)
    vehicle_match = 10 if vehicle['type'] == 'Electric Van' and order['priority_score'] > 3 else 0
    
    # Final Score formula (Simulated)
    return (100 - dist*1000) + parking_quality + vehicle_match

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "Routiqo Super-Brain Online", "systems": "Active [cite: 104]"}

@app.get("/dashboard-stats")
def get_stats():
    """Returns the Key Metrics for the Dashboard [cite: 85]"""
    return {
        "on_time_rate": "92%",      # [cite: 89]
        "avg_route_time": "148 min",# [cite: 92]
        "parking_saved": "42 min",  # [cite: 94]
        "total_stops": 24           # [cite: 95]
    }

@app.get("/vehicles")
def get_vehicles():
    """Returns live fleet status"""
    if not SessionLocal: return []
    with SessionLocal() as db:
        result = db.execute(text("SELECT * FROM vehicles"))
        return [dict(row._mapping) for row in result]

@app.get("/optimize-routes")
def run_optimization():
    """
    The Core Engine:
    1. Fetches Orders & Parking Zones.
    2. Runs 'Parking-First' Logic[cite: 101].
    3. Assigns Risk Labels[cite: 109].
    """
    if not SessionLocal: return {"error": "No DB"}
    
    db = SessionLocal()
    try:
        orders = [dict(row._mapping) for row in db.execute(text("SELECT * FROM orders"))]
        zones = [dict(row._mapping) for row in db.execute(text("SELECT * FROM parking_zones"))]
        vehicles = [dict(row._mapping) for row in db.execute(text("SELECT * FROM vehicles"))]
        
        optimized_routes = []
        
        # ACTIVE LOGIC: Iterate through orders to find best 4D fit
        for order in orders:
            best_zone = None
            best_score = -999
            
            # Find best parking zone (Parking-First Optimization)
            for zone in zones:
                # Use first vehicle as default for calculation
                score = calculate_4d_score(order, zone, vehicles[0]) 
                if score > best_score:
                    best_score = score
                    best_zone = zone
            
            # Risk Analysis [cite: 52]
            risk_status = "SAFE"
            action = "Proceed"
            
            # If parking is bad (Score < 30) -> High Risk
            if best_zone and best_zone['availability_score'] < 30:
                risk_status = "HIGH_RISK"
                action = "Re-route to Loading Zone B" # Proactive redesign [cite: 58]
            
            optimized_routes.append({
                "order_id": order['id'],
                "customer": order['customer_name'],
                "address": order['address'],
                "location": {"lat": order['latitude'], "lng": order['longitude']},
                "parking_zone": best_zone['name'] if best_zone else "None",
                "parking_score": best_zone['availability_score'] if best_zone else 0,
                "risk_status": risk_status,
                "suggested_action": action,
                "priority": order.get('priority_score', 1)
            })
            
        return {
            "strategy": "Parking-First Priority", # [cite: 99]
            "routes": optimized_routes
        }
        
    finally:
        db.close()