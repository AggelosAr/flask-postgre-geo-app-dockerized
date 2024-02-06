from app import app
from flask import request, jsonify
from datetime import datetime, date
import psycopg2
from collections import defaultdict
from shapely.geometry import Point
 
#import matplotlib.pyplot as plt-> USED FOR PLOTS
#import cartopy.crs as ccrs-> USED FOR PLOTS

import os

from app.ocean_data.oceans import OCEAN_POLYGONS



# Time spent (in hours) in each ocean
type OceanTimes = dict[str, float]
# this should be a list not a tuple TODO !!
type OceanRanges =  dict[str, list[tuple[int, int]]]


@app.route('/put_ship_data', methods=['PUT'])
def put_ship_data():
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
   



# Route for handling GET requests
@app.route("/get_ship_data", methods=['GET'])
def get_ship_data():
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





def insert_data(mmsi: int, lon: float, lat: float, tstamp: date):
    # each table will be names mmsi1, mmsi2, mmsi3 etc.
    # For each vessel we will have a seperate table
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
    print("Data inserted successfully")

   


def get_oceans(mmsi: int, start_date: date, end_date: date) -> OceanTimes:

    conn = get_db_connection()
    cur = conn.cursor()

    # here we have the trajectory of the vessel
    # do a linear serach and for each point 
    # 1 see if it inside the bounding box of the ocean

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
    ocean_times = {
        "Indian" : [[None, None]],
        "Pacific" : [[None, None]],
        "Atlantic" : [[None, None]],
    }
    

    last_ocean = None

    #testing can be turned on with a flag  -> USED FOR PLOTS
    #vessel_points = []

    for row in cur.fetchall():
        
        lon = row[1]
        lat = row[2] 
        ts = row[3]

        cur_ocean = find_ocean(lon, lat)

        #testing -> USED FOR PLOTS
        #vessel_points.append((lon, lat))


        # 2 cases
        # case 1 ->  we found ocean 
        if cur_ocean:
            
            # Retrieve the last visit
            last_visit = ocean_times[cur_ocean][-1]
            # if ENTRY_TIME doesn't exist create one 
            if last_visit[0] is None:
                last_visit[0] = ts
            # Else update the LAST_TIME 
            else:
                last_visit[1] = ts


        # case 2 -> we did not find any oceans
        # e.g. it is not in any of the 3 oceans we want
        # ! ignore it !
        # Although there is a case it may reenter so update the 
        # last ocean by appendning a [None, None]
        # Since we retrieve the last_visit by looking at the end of the list. 
        else:

            # if you found one ocean last time and now you didn't find any. 
            # you are out of the box so add a new interval to the last entry 
            if last_ocean:
                ocean_times[last_ocean].append([None, None])
             
        last_ocean = cur_ocean
        

    cur.close()
    conn.close()


    
    #testing -> USED FOR PLOTS
    """
    fig, ax = plt.subplots(subplot_kw={'projection': ccrs.Robinson()})
    ax.set_global()

    for ocean, polygon in OCEAN_POLYGONS.items():
        ax.add_geometries([polygon], ccrs.PlateCarree(), edgecolor='black', facecolor='none', label=ocean)

    lons, lats = zip(*vessel_points)
    ax.scatter(lons, lats, c='red', marker='o', transform=ccrs.PlateCarree(), label='Vessel Points')

    ax.coastlines()
    ax.gridlines()

    plt.savefig(f"{table_name}.png", dpi=300)  # Adjust dpi as needed
    #plt.legend()
    #plt.show()
    """
    return collapse_ranges(ocean_times)



def collapse_ranges(ocean_times: OceanRanges) -> OceanTimes:
    single_ocean_times = defaultdict(int)
    for ocean, time_ranges in ocean_times.items():
        for start_time, end_time in time_ranges:
            if start_time is None and  end_time is None:
                continue

            if start_time is None or  end_time is None:
                # this means the vessel sunk
                # only end time must be none
                continue
            single_ocean_times[ocean] += (end_time - start_time).total_seconds() / 3600
    
    return single_ocean_times
    





def find_ocean(lon: float, lat: float):
    point = Point(lon, lat)
    for ocean, polygon in OCEAN_POLYGONS.items():
        
        if polygon.contains(point):
            return ocean

   
def get_db_connection():
    conn = psycopg2.connect(host='db', #localhost for local dev
                            database=os.environ['POSTGRESQL_DB'],
                            user=os.environ['POSTGRESQL_USERNAME'],
                            password=os.environ['POSTGRESQL_PASSWORD'],
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