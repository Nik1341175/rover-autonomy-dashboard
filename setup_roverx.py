#!/usr/bin/env python3
"""
RoverX Autonomous Rover - Database Setup Script
Creates telemetry table with wildlife/Christmas object detection data
"""
 
import psycopg2
from psycopg2 import Error
from datetime import datetime, timedelta
import random
import json
 
# ============================================================================
# UPDATE THESE WITH YOUR PUKKI DATABASE CREDENTIALS
# ============================================================================
 
DB_HOST = "195.148.30.93"
DB_PORT = 5432
DB_NAME = "Project_dashboard"
DB_USER = "Nihar"
DB_PASSWORD = "Nihar@1341"  # CHANGE THIS!
 
# ============================================================================
# ROVERX OBJECT CLASSES (Your trained model)
# ============================================================================
DETECTED_OBJECTS = {
    0: "bear",
    1: "cyclist",
    2: "fox",
    3: "reindeer",
    4: "robot",
    5: "santa"
}
 
ROVER_MODES = ["Autonomous", "Manual Override", "Standby", "Error"]
DECISIONS = ["move_forward", "turn_left", "turn_right", "stop", "slow_down"]
 
# ============================================================================
 
def create_connection():
    """Create connection to Pukki database"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("✓ Connected to Pukki DBaaS")
        return conn
    except Error as e:
        print(f"✗ Connection failed: {e}")
        return None
 
def create_roverx_table(conn):
    """Create RoverX telemetry table with wildlife detection schema"""
    cursor = conn.cursor()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS roverx_telemetry (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Navigation & Position
        latitude FLOAT NOT NULL,
        longitude FLOAT NOT NULL,
        gps_speed FLOAT,
        
        -- Power & Health
        battery_voltage FLOAT,
        battery_current FLOAT,
        rover_mode VARCHAR(50),
        
        -- Perception & Autonomy
        detected_objects JSONB,
        lidar_distance FLOAT,
        decision_made VARCHAR(100),
        confidence_score FLOAT,
        
        -- Camera (optional)
        camera_frame_path VARCHAR(500)
    );
    """
    
    try:
        cursor.execute(create_table_sql)
        conn.commit()
        print("✓ RoverX telemetry table created")
        cursor.close()
        return True
    except Error as e:
        print(f"✗ Table creation failed: {e}")
        conn.rollback()
        return False
 
def generate_roverx_data(num_records=30):
    """Generate realistic simulated RoverX telemetry data with object detection"""
    data = []
    base_time = datetime.now() - timedelta(hours=2)
    
    # Simulate rover operating in Helsinki area
    start_lat = 60.1699
    start_lon = 24.9384
    
    # Simulate a mission scenario
    wildlife_encounters = {
        5: (60.1700, 24.9390),   # Santa at location 1
        0: (60.1705, 24.9400),   # Bear at location 2
        3: (60.1695, 24.9380),   # Reindeer at location 3
    }
    
    for i in range(num_records):
        timestamp = base_time + timedelta(minutes=i*4)
        
        # Simulate rover movement
        latitude = start_lat + random.uniform(-0.015, 0.015)
        longitude = start_lon + random.uniform(-0.015, 0.015)
        gps_speed = random.uniform(0.5, 3.5) if i % 3 != 0 else 0  # Occasional stops
        
        # Power readings
        battery_voltage = max(10.5, 12.0 - (i * 0.05) + random.uniform(-0.2, 0.2))
        battery_current = random.uniform(0.5, 3.5)
        
        # Rover mode (mostly autonomous during mission)
        rover_mode = random.choices(
            ROVER_MODES,
            weights=[70, 10, 15, 5]  # 70% Autonomous, 10% Manual, 15% Standby, 5% Error
        )[0]
        
        # Object detection simulation
        detected_objects = None
        decision = "move_forward"
        confidence = 0.0
        
        # Randomly detect objects (30% chance per reading)
        if random.random() < 0.3:
            detected_class = random.randint(0, 5)
            detected_object = DETECTED_OBJECTS[detected_class]
            confidence = random.uniform(0.75, 0.99)
            detected_objects = json.dumps({
                "class": detected_class,
                "object": detected_object,
                "confidence": round(confidence, 3),
                "detection_time": timestamp.isoformat()
            })
            
            # Make decisions based on detected object
            if detected_object in ["bear", "cyclist"]:
                decision = "stop"
            elif detected_object in ["reindeer", "santa"]:
                decision = "slow_down"
            else:
                decision = random.choice(["turn_left", "turn_right", "stop"])
        else:
            decision = "move_forward"
        
        # LiDAR distance (cm) - obstacle detection
        lidar_distance = random.uniform(30, 500) if rover_mode == "Autonomous" else None
        
        # Camera frame path (simulated)
        camera_frame = f"/data/frames/roverx_{i:04d}.jpg" if detected_objects else None
        
        data.append({
            'timestamp': timestamp,
            'latitude': round(latitude, 6),
            'longitude': round(longitude, 6),
            'gps_speed': round(gps_speed, 2),
            'battery_voltage': round(battery_voltage, 2),
            'battery_current': round(battery_current, 2),
            'rover_mode': rover_mode,
            'detected_objects': detected_objects,
            'lidar_distance': round(lidar_distance, 1) if lidar_distance else None,
            'decision_made': decision,
            'confidence_score': round(confidence, 3) if confidence > 0 else None,
            'camera_frame_path': camera_frame
        })
    
    return data
 
def insert_roverx_data(conn, data):
    """Insert RoverX telemetry data into database"""
    cursor = conn.cursor()
    
    insert_sql = """
    INSERT INTO roverx_telemetry 
    (timestamp, latitude, longitude, gps_speed, battery_voltage, battery_current, 
     rover_mode, detected_objects, lidar_distance, decision_made, confidence_score, camera_frame_path)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    try:
        for record in data:
            cursor.execute(insert_sql, (
                record['timestamp'],
                record['latitude'],
                record['longitude'],
                record['gps_speed'],
                record['battery_voltage'],
                record['battery_current'],
                record['rover_mode'],
                record['detected_objects'],
                record['lidar_distance'],
                record['decision_made'],
                record['confidence_score'],
                record['camera_frame_path']
            ))
        
        conn.commit()
        print(f"✓ Inserted {len(data)} RoverX telemetry records")
        cursor.close()
        return True
    except Error as e:
        print(f"✗ Data insertion failed: {e}")
        conn.rollback()
        return False
 
def verify_data(conn):
    """Verify data was inserted"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM roverx_telemetry;")
        count = cursor.fetchone()[0]
        print(f"✓ Total records in roverx_telemetry table: {count}")
        
        # Show detections
        cursor.execute("""
            SELECT COUNT(*) FROM roverx_telemetry 
            WHERE detected_objects IS NOT NULL
        """)
        detections = cursor.fetchone()[0]
        print(f"✓ Object detections: {detections} records")
        
        # Show sample data
        cursor.execute("""
            SELECT timestamp, rover_mode, decision_made, confidence_score, 
                   (detected_objects->>'object') as detected_object
            FROM roverx_telemetry
            WHERE detected_objects IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        
        print("\nLatest 5 detections:")
        for row in cursor.fetchall():
            obj = row[4] if row[4] else "none"
            print(f"  {row[0]} | Mode: {row[1]} | Decision: {row[2]} | Object: {obj} | Confidence: {row[3]}")
        
        cursor.close()
        return True
    except Error as e:
        print(f"✗ Verification failed: {e}")
        return False
 
def main():
    print("=" * 70)
    print("RoverX Autonomous Rover - Telemetry Database Setup")
    print("=" * 70)
    
    conn = create_connection()
    if not conn:
        return
    
    print("\n[1/4] Creating RoverX telemetry table...")
    if not create_roverx_table(conn):
        conn.close()
        return
    
    print("\n[2/4] Generating simulated RoverX mission data...")
    data = generate_roverx_data(num_records=30)
    print(f"  Generated {len(data)} records")
    
    print("\n[3/4] Inserting data into database...")
    if not insert_roverx_data(conn, data):
        conn.close()
        return
    
    print("\n[4/4] Verifying data...")
    verify_data(conn)
    
    conn.close()
    print("\n" + "=" * 70)
    print("✓ RoverX database setup complete! Dashboard ready to use.")
    print("=" * 70)
 
if __name__ == "__main__":
    main()