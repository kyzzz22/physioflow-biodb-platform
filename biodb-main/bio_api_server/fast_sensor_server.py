from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
import jwt
import pandas as pd
import gzip, lz4.frame, brotli, base64, json, msgpack
from datetime import datetime

import env
import pvalid

app = FastAPI()

# CORS設定（必要なら調整）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# InfluxDBクライアント（同期版）
influx_client = InfluxDBClient(
    url=f"http://{env.INFLUX_HOST}:{env.INFLUX_PORT}",
    token=env.INFLUX_TOKEN,
    org=env.INFLUX_ORG
)
query_api = influx_client.query_api()

def decompress_and_parse(data_b64: str, compression: str, format: str):
    decoded = base64.b64decode(data_b64)
    if compression == "gzip":
        decompressed = gzip.decompress(decoded)
    elif compression == "lz4":
        decompressed = lz4.frame.decompress(decoded)
    elif compression == "brotli":
        decompressed = brotli.decompress(decoded)
    elif compression == "none":
        decompressed = decoded
    else:
        raise ValueError("Unsupported compression type")

    if format == "messagepack":
        return msgpack.unpackb(decompressed, raw=False)
    elif format == "json":
        return json.loads(decompressed.decode("utf-8"))
    else:
        raise ValueError("Unsupported format")

def prepare_data(df: pd.DataFrame, format="json", compression="none"):
    if format == "json":
        data_bytes = json.dumps(df.to_dict(orient="list")).encode("utf-8")
    elif format == "messagepack":
        data_bytes = msgpack.packb(df.to_dict(orient="list"))
    else:
        raise ValueError(f"Unsupported format: {format}")

    if compression == "gzip":
        compressed = gzip.compress(data_bytes)
    elif compression == "lz4":
        compressed = lz4.frame.compress(data_bytes)
    elif compression == "brotli":
        compressed = brotli.compress(data_bytes)
    elif compression == "none":
        compressed = data_bytes
    else:
        raise ValueError(f"Unsupported compression: {compression}")

    encoded = base64.b64encode(compressed).decode("utf-8")
    return encoded

def decode_jwt(raw_token: str):
    bearer, token = raw_token.split(" ", 1)
    if bearer != "Bearer":
        raise Exception("Bearer Error")
    payload = jwt.decode(token, env.APP_JWT_SECRET_KEY, algorithms=["HS256"])
    for k in ["iat", "nbf", "exp"]:
        payload[k] = datetime.fromtimestamp(payload[k])
    return payload

def check_jwt_exp(exp: str):
    if datetime.now() > exp:
        raise Exception("Jwt Expired")

@app.post("/data/read")
def read_data(request: pvalid.SensorDataReadRequestBody, Authorization: str = Header()):
    if not Authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        claims = decode_jwt(Authorization)
    except:
        raise HTTPException(status_code=400, detail="JWT Secret Key Error")
    try:
        check_jwt_exp(claims["exp"])
    except:
        raise HTTPException(status_code=400, detail="Expired JWT")
    try:
        participant_id = claims["participant_id"]
        jwt_role = claims["jwt_role"]
        start_time_jwt = datetime.fromisoformat(claims["start_time"])
        end_time_jwt = datetime.fromisoformat(claims["end_time"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    if request.start_time < start_time_jwt or request.end_time > end_time_jwt:
        raise HTTPException(status_code=400, detail="Request time out of range")

    try:
        field_str = " or ".join([f'r["_field"] == "{field}"' for field in request.rows])
        columns_str = ", ".join([f'"{field}"' for field in request.rows])

        query = f"""
        from(bucket: "{env.INFLUX_BUCKET}")
            |> range(start: {request.start_time.isoformat()}, stop: {request.end_time.isoformat()})
            |> filter(fn: (r) => r["_measurement"] == "{env.INFLUX_MEASUREMENT}")
            |> filter(fn: (r) => {field_str})
            |> filter(fn: (r) => r["participant"] == "{participant_id}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            |> keep(columns: [{columns_str}, "_time"])
        """

        df = query_api.query_data_frame(query=query, org=env.INFLUX_ORG)
        df = df.sort_values(by='_time')
        df["_time"] = df["_time"].astype(str)
        df.rename(columns={"_time": "time"}, inplace=True)
        df.drop(columns=["result", "table"], inplace=True)
        print(df)

        encoded_data = prepare_data(df, format=request.format, compression=request.compression)

        return JSONResponse({
            "compression": request.compression,
            "format": request.format,
            "data": encoded_data
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read data: {str(e)}")
