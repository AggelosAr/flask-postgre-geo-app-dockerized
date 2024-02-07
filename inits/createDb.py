#https://github.com/NaysanSaran/pandas2postgresql/blob/master/notebooks/Psycopg2_Bulk_Insert_Speed_Benchmark.ipynb
import pandas as pd
import numpy as np

import psycopg2
import os, sys

PATH = os.path.join(os.getcwd(), "inits", "csvs")
IS_DEPOLYED: bool =  bool(os.environ.get('IS_DEPLOYED', '').lower() == 'true')

#type return here TODO
def connect():
    connect_params = {
        "host"      : os.environ.get('HOST_MACHINE'),
        "database"  : os.environ.get('POSTGRESQL_DB'),
        "user"      : os.environ.get('POSTGRES_USERNAME'),
        "password"  : os.environ.get('POSTGRES_PASSWORD'),
        "port"      : 5432
    }

    conn = None
    try:
        conn = psycopg2.connect(**connect_params)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        sys.exit(1) 
    return conn



# Each table will be named mmsi1, mmsi2, mmsi3 etc.
# For each vessel we will have a seperate table
def insert_data(conn, file_name: str) -> None:

    table = file_name.split(".")[0]

    csv_file_path = os.path.join(PATH, file_name)
    df = pd.read_csv(csv_file_path, index_col=0)
   
    df.drop(["mmsi", "position", "speed"], axis=1, inplace=True)

    tuples = [tuple(x) for x in df.to_numpy()]
    cols = ",".join(list(df.columns))

    query  = "INSERT INTO %s(%s) VALUES(%%s,%%s,%%s)" % (table, cols)

    cursor = conn.cursor()
    try:

        cursor.execute(f"SELECT to_regclass('{table}')")
        table_exists = cursor.fetchone()[0]

        if table_exists:
            print(f"Table '{table}' already exists. Skipping table creation.")
            return

        cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id SERIAL PRIMARY KEY,
                        lon FLOAT,
                        lat FLOAT,
                        tstamp TIMESTAMP
        )
        """)
      
        cursor.executemany(query, tuples)
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        print("Error: %s" % error)
        conn.rollback()
        cursor.close()
        return

    cursor.close()
    
    print(f"Created table: {table} - Rows added: {len(df)}")
  

def initDb() -> None:
    conn = connect()
    for csv_file_name in os.listdir(PATH):
        insert_data(conn, csv_file_name)
    conn.close()
    