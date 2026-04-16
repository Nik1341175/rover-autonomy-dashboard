import psycopg2
import serial
import pynmea2
import time

# ============================================================
# DATABASE CREDENTIALS — fill these in
# ============================================================
DB_HOST     = "your-pukki-host"
DB_PORT     = 5432
DB_NAME     = "your_db_name"
DB_USER     = "your_user"
DB_PASSWORD = "your_password"

# ============================================================
# SETTINGS
# ============================================================
GPS_PORT      = "/dev/ttyAMA0"   # typical on Raspberry Pi, change if needed
GPS_BAUD      = 38400            # Holybro M10 default
LIDAR_PORT    = "/dev/ttyUSB0"   # change to your LiDAR port
SEND_INTERVAL = 3                # send data every 3 seconds

# Battery voltage range for your battery pack
# Adjust these to match your actual battery
BATTERY_MIN_V = 10.5   # voltage when empty (0%)
BATTERY_MAX_V = 12.6   # voltage when full (100%)


# ============================================================
# CONNECT TO DATABASE
# ============================================================
def connect_db():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )
    print("✓ Connected to Pukki database")
    return conn


# ============================================================
# READ GPS
# Returns (latitude, longitude, speed) or (None, None, None)
# ============================================================
def read_gps(gps_serial):
    try:
        line = gps_serial.readline().decode("utf-8", errors="ignore")
        if line.startswith("$GNRMC") or line.startswith("$GPRMC"):
            msg = pynmea2.parse(line)
            if msg.status == "A":  # A = valid fix
                lat   = msg.latitude
                lon   = msg.longitude
                speed = msg.spd_over_grnd * 0.514444  # knots → m/s
                return lat, lon, speed
    except Exception as e:
        print(f"GPS read error: {e}")
    return None, None, None


# ============================================================
# READ LIDAR
# This is a simple example — adjust to your LiDAR model
# ============================================================
def read_lidar(lidar_serial):
    try:
        lidar_serial.write(b'\x02')          # request measurement
        response = lidar_serial.read(9)       # read response bytes
        if len(response) == 9:
            distance_cm = (response[3] << 8) + response[2]
            return float(distance_cm)
    except Exception as e:
        print(f"LiDAR read error: {e}")
    return None


# ============================================================
# READ BATTERY VOLTAGE
# This assumes you have a voltage divider on an ADC (e.g. ADS1115)
# If you don't have battery monitoring, this returns None safely
# ============================================================
def read_battery():
    try:
        import board
        import busio
        import adafruit_ads1x15.ads1115 as ADS
        from adafruit_ads1x15.analog_in import AnalogIn

        i2c      = busio.I2C(board.SCL, board.SDA)
        ads      = ADS.ADS1115(i2c)
        channel  = AnalogIn(ads, ADS.P0)

        voltage  = channel.voltage * 3.0   # multiply by voltage divider ratio
        percent  = (voltage - BATTERY_MIN_V) / (BATTERY_MAX_V - BATTERY_MIN_V) * 100
        percent  = max(0.0, min(100.0, percent))  # clamp between 0 and 100

        return round(voltage, 2), round(percent, 1)

    except Exception:
        # If no battery hardware found, just return None
        return None, None


# ============================================================
# SEND ONE ROW TO DATABASE
# ============================================================
def send_to_db(conn, lat, lon, speed, voltage, percent, lidar, obj, conf):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO rover_telemetry
            (latitude, longitude, speed,
             battery_voltage, battery_percent,
             lidar_cm,
             detected_object, confidence)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (lat, lon, speed, voltage, percent, lidar, obj, conf))
    conn.commit()
    cursor.close()


# ============================================================
# OBJECT DETECTION
# Import your existing detection function here.
# We assume it returns (label, confidence) or (None, None)
# Replace this with your actual import.
# ============================================================
def read_detection():
    try:
        from your_detection_script import get_latest_detection
        label, confidence = get_latest_detection()
        return label, confidence
    except Exception as e:
        print(f"Detection read error: {e}")
    return None, None


# ============================================================
# MAIN LOOP
# ============================================================
def main():
    conn        = connect_db()
    gps_serial  = serial.Serial(GPS_PORT, GPS_BAUD, timeout=1)
    lidar_serial = serial.Serial(LIDAR_PORT, 115200, timeout=1)

    print("✓ Rover sender started. Sending data every", SEND_INTERVAL, "seconds.")

    while True:
        # Read all sensors
        lat, lon, speed          = read_gps(gps_serial)
        voltage, percent         = read_battery()
        lidar                    = read_lidar(lidar_serial)
        obj, conf                = read_detection()

        # Send to database
        try:
            send_to_db(conn, lat, lon, speed, voltage, percent, lidar, obj, conf)
            print(f"✓ Sent — GPS:({lat},{lon}) speed:{speed} bat:{percent}% lidar:{lidar}cm obj:{obj}({conf})")
        except Exception as e:
            print(f"✗ DB send failed: {e}")
            # Try to reconnect
            try:
                conn = connect_db()
            except:
                pass

        time.sleep(SEND_INTERVAL)


if __name__ == "__main__":
    main()