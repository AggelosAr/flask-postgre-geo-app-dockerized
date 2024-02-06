**Project Initialization:**
   - Navigate to the project directory.
   - Run `docker-compose up --build` to bring up the containers.


## Database Structure
The database is split into 4 tables, with each table representing a separate vessel. Each table contains entries corresponding to the specific MMSI.


## Screenshots
Screenshots of request-response pairs for all 4 MMSIs within a specified date range are available in the `screenshots` folder. The bounding polygons for the oceans were manually created, implying that the accuracy of results, particularly in close proximity to coastlines, may be limited. Refer to the plots folder for visual representations of the paths taken by each vessel. Also in plot2 you can see a point manually entered.


## TODO 
Make the ocean bounding boxes better.


## API Endpoints
The endpoints generally incorporate validations.

### PUT Endpoint: /get_ship_data
- **Method:** GET
- **Input Parameters:**
    - `mmsi` (Vessel Identifier)
    - `start_date` (Earliest date)
    - `end_date` (Latest date)
- **Example Usage:**
    - `/get_ship_data?mmsi=1&start_date=2023-06-01%2000:12:00&end_date=2023-11-30%2000:12:00`
- **Returns:**
    ```json
    {
       "Position updated for MMSI: 1, Lon: -39.780807, Lat: 35.291355, Tstamp: 2023-09-30 23:10:00"
    }
    ```

### PUT Endpoint: /put_ship_data
- **Method:** PUT
- **Query Parameters:**
    - `mmsi` (Vessel Identifier)
    - `lon` (Longitude)
    - `lat` (Latitude)
    - `tstamp` (Timestamp)
- **Example Usage:**
    - `/put_ship_data?mmsi=1&lon=-39.780807&lat=35.291355&tstamp=2023-09-30%2023:10:00`
- **Returns:**
    ```json
    {
        "Atlantic": 549.8152777777777
    }
    ```