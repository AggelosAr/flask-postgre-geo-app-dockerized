from app import app
from flask import request, jsonify, Response
from datetime import datetime, date
import psycopg2
from collections import defaultdict
from shapely.geometry import Point
import os
from app.ocean_data.oceans import OCEAN_POLYGONS

IS_DEPOLYED: bool =  bool(os.environ.get('IS_DEPLOYED', '').lower() == 'true')


# TODO handle exceptions

    
type Vessels = list[tuple[float | None, float | None]]
type OceanTimes = dict[str, float]
# this should be a list not a tuple TODO !!
type OceanTimeRanges =  dict[str, list[tuple[int, int]]]




@app.route('/put_ship_data', methods=['PUT'])
def put_ship_data() -> Response:
    try:

        if len(request.args) != 4:
            raise ValueError("Exactly four parameters (mmsi, lon, lat, tstamp) are required.")
        
        required_params = ["mmsi", "lon", "lat", "tstamp"]
        if not all(param in request.args for param in required_params):
            raise ValueError("Missing required parameters. Required: mmsi, lon, lat, tstamp.")
        
        mmsi = int(request.args.get('mmsi'))
        lon = float(request.args.get('lon'))
        lat = float(request.args.get('lat'))
        tstamp = datetime.strptime(request.args.get('tstamp'), "%Y-%m-%d %H:%M:%S")

        resp = f"Position updated for MMSI: {mmsi}, Lon: {lon}, Lat: {lat}, Tstamp: {tstamp}"

        insert_data(mmsi, lon, lat, tstamp)
        
        return jsonify(resp), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
   


@app.route("/get_ship_data", methods=['GET'])
def get_ship_data() -> Response:
    try:

        if len(request.args) != 3:
            raise ValueError("Exactly three parameters (mmsi, start_date, end_date) are required.")
        
        required_params = ["mmsi", "start_date", "end_date"]
        if not all(param in request.args for param in required_params):
            raise ValueError("Missing required parameters. Required: mmsi, start_date, end_date.")

      
        mmsi = int(request.args.get('mmsi'))#
        start_date = datetime.strptime(request.args.get('start_date'), "%Y-%m-%d %H:%M:%S")
        end_date = datetime.strptime(request.args.get('end_date'), "%Y-%m-%d %H:%M:%S")

        resp = get_oceans(mmsi, start_date, end_date)
        return jsonify(resp), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400




def insert_data(mmsi: int, lon: float, lat: float, tstamp: date) -> None:
    
    conn = get_db_connection()
    cur = conn.cursor()

    table_name = f'mmsi_{mmsi}'

    if not table_exists(table_name, cur):
        raise ValueError(f"Table '{table_name}' does not exist.")

    query = f"""
            INSERT INTO {table_name} 
                (lon, lat, tstamp) 
            VALUES 
                ({lon}, {lat}, '{tstamp}')
            """
    cur.execute(query)
    conn.commit()
    cur.close()
    conn.close()


# We have the trajectory of the vessel
# do a linear serach and for each point 
# see if it inside the bounding box of the ocean
def get_oceans(mmsi: int, start_date: date, end_date: date) -> OceanTimes:

    conn = get_db_connection()
    cur = conn.cursor()

    table_name = f'mmsi_{mmsi}'

    if not table_exists(table_name, cur):
        raise ValueError(f"Table '{table_name}' does not exist.")

    query = f"""
            SELECT * 
            FROM {table_name}
            WHERE tstamp BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY tstamp ASC
            """
    cur.execute(query)

    # this is a map of ranges 
    # handle case where it left the ocean and come back, hence the list of lists
    # e.g. Atlantic -> [ [ENTRY_TIME, LAST_TIME], [ENTRY_TIME, LAST_TIME], ... ]
    ocean_time_ranges: OceanTimeRanges = {
        "Indian" : [[None, None]],
        "Pacific" : [[None, None]],
        "Atlantic" : [[None, None]],
    }
    prev_ocean = None
    vessels = []
    
    for row in cur.fetchall():
        prev_ocean = update_ocean_ranges(prev_ocean, row, vessels, ocean_time_ranges)
        
    cur.close()
    conn.close()

    #if not IS_DEPOLYED:
    #    make_png_from_points(table_name, vessels)
    
    return collapse_ranges(ocean_time_ranges)


def find_ocean(lon: float, lat: float) -> str | None:
    for ocean, polygon in OCEAN_POLYGONS.items():
        if polygon.contains(Point(lon, lat)):
            return ocean


def update_ocean_ranges(prev_ocean: str | None, 
                        row:  tuple[any, ...], 
                        vessels: Vessels, 
                        ocean_time_ranges: OceanTimeRanges) -> str | None:
    
    lon, lat, ts = row[1], row[2], row[3]
    ocean = find_ocean(lon, lat)
    vessels.append((lon, lat))

    # case 1 ->  we found ocean 
    # if ENTRY_TIME doesn't exist create one 
    # Else update the LAST_TIME
    if ocean:
        
        last_visit = ocean_time_ranges[ocean][-1]
        if last_visit[0] is None:
            last_visit[0] = ts
        else:
            last_visit[1] = ts

    # case 2 -> we did not find any oceans
    # There is a case it may reenter so update the last ocean 
    # by appendning a [None, None]
    # if you found one ocean last time and now you didn't find any. 
    # you are out of the box so add a new interval to the last entry 
    elif prev_ocean:
        ocean_time_ranges[prev_ocean].append([None, None])
            
    return ocean
        

def collapse_ranges(ranges: OceanTimeRanges) -> OceanTimes:
    collapsed_ranges: OceanTimes = defaultdict(int)
    for ocean, time_ranges in ranges.items():
        for start_time, end_time in time_ranges:
            if start_time is None and  end_time is None:
                continue

            if start_time is None or  end_time is None:
                # this means the vessel sunk
                # only end time must be none
                continue

            time_in_hours = (end_time - start_time).total_seconds() / 3600
            collapsed_ranges[ocean] += time_in_hours
    
    return collapsed_ranges
    


def get_db_connection():
    conn = psycopg2.connect(host=os.environ.get('HOST_MACHINE'),
                            database=os.environ['POSTGRESQL_DB'],
                            user=os.environ['POSTGRES_USERNAME'],
                            password=os.environ['POSTGRES_PASSWORD'],
                            port=5432)
    return conn



def table_exists(table_name: str, cur) -> bool:
    query = f"""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = '{table_name}'
            );
            """
    cur.execute(query)
    return cur.fetchone()[0]

"""
def make_png_from_points(filename: str, points: list) -> None:
    import matplotlib.pyplot as plt
    import cartopy.crs as ccrs
    
    fig, ax = plt.subplots(subplot_kw={'projection': ccrs.Robinson()})
    ax.set_global()

    for ocean, polygon in OCEAN_POLYGONS.items():
        ax.add_geometries([polygon], ccrs.PlateCarree(), edgecolor='black', facecolor='none', label=ocean)

    lons, lats = zip(*points)
    ax.scatter(lons, lats, c='red', marker='o', transform=ccrs.PlateCarree(), label='Vessel Points')

    ax.coastlines()
    ax.gridlines()

    plt.savefig(f"{filename}.png", dpi=300) 
    #plt.legend()
    #plt.show()
"""
