from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
import jwt
import pandas as pd
import gzip, lz4.frame, brotli, base64, json, msgpack, asyncio
from datetime import datetime

import env
import pvalid

@asynccontextmanager
async def lifespan(app: FastAPI):
    global influx_client
    influx_client = InfluxDBClientAsync(
        url=f"http://{env.INFLUX_HOST}:{env.INFLUX_PORT}",
        token=env.INFLUX_TOKEN,
        org=env.INFLUX_ORG,
        timeout=500000
    )
    yield
    await influx_client.__aexit__(None, None, None)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

async def to_dataframe_from_result(results) -> pd.DataFrame:
    dfs = []
    async for table in results:
        dfs.append(vars(table)["values"])
    if dfs:
        return pd.DataFrame(dfs)
    return pd.DataFrame()

async def prepare_data(df: pd.DataFrame, format="json", compression="none"):
    data_bytes = await asyncio.to_thread(
        lambda: json.dumps(df.to_dict(orient="list")).encode("utf-8") if format == "json" else msgpack.packb(df.to_dict(orient="list"))
    )

    compressed = await asyncio.to_thread({
        "gzip": lambda: gzip.compress(data_bytes),
        "lz4": lambda: lz4.frame.compress(data_bytes),
        "brotli": lambda: brotli.compress(data_bytes),
        "none": lambda: data_bytes,
    }[compression])

    return base64.b64encode(compressed).decode("utf-8")

@app.post("/data/read")
async def read_data(
    request: pvalid.SensorDataReadRequestBody,
    Authorization: str = Header()
):
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
        raise HTTPException(status_code=401, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    if request.start_time < start_time_jwt or request.end_time > end_time_jwt:
        raise HTTPException(status_code=400, detail="Request time out of range")

    field_str = " or ".join([f'r["_field"] == "{r}"' for r in request.rows])
    columns_str = ", ".join([f'"{r}"' for r in request.rows])

    query = f"""
    from(bucket: "{env.INFLUX_BUCKET}")
        |> range(start: {request.start_time.isoformat()}, stop: {request.end_time.isoformat()})
        |> filter(fn: (r) => r["_measurement"] == "{env.INFLUX_MEASUREMENT}")
        |> filter(fn: (r) => {field_str})
        |> filter(fn: (r) => r["participant"] == "{participant_id}")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> keep(columns: [{columns_str}, "_time"])
    """

    try:
        results = await influx_client.query_api().query_stream(query=query, org=env.INFLUX_ORG)
        df = await to_dataframe_from_result(results)
        df = df.sort_values(by='_time')
        df["_time"] = df["_time"].astype(str)
        df.rename({"_time": "time"}, axis=1, inplace=True)
        df.drop(labels=["result", "table"], inplace=True, axis=1)

        encoded = await prepare_data(df, format=request.format, compression=request.compression)
        return JSONResponse({
            "compression": request.compression,
            "format": request.format,
            "data": encoded
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")
