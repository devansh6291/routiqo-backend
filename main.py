from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import math

# --- CONFIGURATION ---
# PASTE YOUR NEON/RENDER CONNECTION STRING INSIDE THE QUOTES BELOW
DATABASE_URL = "postgresql://neondb_owner:npg_PCxSgWy6kM7E@ep-dark-waterfall-ah56w45z-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

if "your-database-url-here" in DATABASE_URL:
    print("ERROR: You forgot to paste your database URL in main.py line 11!")

# --- APP SETUP ---
app = FastAPI(title="Routiqo API")

# Allow the frontend to talk to this backend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all for hackathon simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DATABASE SETUP ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MOCK ALGORITHMS (Simplified for Hackathon) ---

def calculate_risk(parking_score):
    """
    Implements 'Zero-Crisis Delivery'[cite: 107].
    If parking is hard (low score), risk is HIGH.
    """
    if parking_score < 30:
        return "HIGH_RISK"
    return "SAFE"

# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return {"message": "Routiqo Backend is Online [cite: 104]"}

@app.get("/vehicles")
def get_vehicles():
    """Fetch all vehicles [cite: 81]"""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM vehicles"))
        return [dict(row._mapping) for row in result]

@app.get("/optimize-routes")
def optimize_routes():
    """
    The core logic: 'Parking-First Route Optimization'[cite: 51].
    We fetch orders and check nearby parking zones.
    """
    db = SessionLocal()
    try:
        # 1. Get pending orders
        orders_query = db.execute(text("SELECT * FROM orders WHERE status='pending'"))
        orders = [dict(row._mapping) for row in orders_query]
        
        # 2. Get parking zones
        parking_query = db.execute(text("SELECT * FROM parking_zones"))
        zones = [dict(row._mapping) for row in parking_query]
        
        optimized_routes = []
        
        for order in orders:
            # Simple logic: Find nearest parking zone
            best_zone = None
            min_dist = 999999
            
            for zone in zones:
                # Euclidean distance (rough approx for hackathon)
                dist = math.sqrt((order['latitude'] - zone['latitude'])**2 + (order['longitude'] - zone['longitude'])**2)
                if dist < min_dist:
                    min_dist = dist
                    best_zone = zone
            
            # Apply Risk Analysis [cite: 52]
            risk = "UNKNOWN"
            if best_zone:
                risk = calculate_risk(best_zone['availability_score'])
            
            optimized_routes.append({
                "order_id": order['id'],
                "customer": order['customer_name'],
                "location": {"lat": order['latitude'], "lng": order['longitude']},
                "nearest_parking": best_zone['name'] if best_zone else "None",
                "risk_status": risk,
                "action": "Avoid" if risk == "HIGH_RISK" else "Proceed" # [cite: 101]
            })
            
        return {"strategy": "Balanced", "routes": optimized_routes} # [cite: 86]
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

# --- RUN INSTRUCTIONS ---
# To run this locally: uvicorn main:app --reload