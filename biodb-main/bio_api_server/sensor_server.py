import base64
from datetime import datetime
import gzip
import json

import brotli
from flasgger import Swagger
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import get_jwt_identity, get_jwt, jwt_required, JWTManager
from influxdb_client import InfluxDBClient
import lz4
import lz4.frame
import msgpack
import pandas as pd

import env
import pvalid

app = Flask(__name__)
app.config["SWAGGER"] = {
    "title": "API Documentation",
    "uiversion": 3,
    "static_url_path": "/sensor/flasgger_static",
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/sensor/apispec_1.json',
            "rule_filter": lambda rule: True,  # all in
            "model_filter": lambda tag: True,  # all in
        }
    ],
}
swagger = Swagger(app)
CORS(app)

# JWT
app.config["JWT_SECRET_KEY"] = env.APP_JWT_SECRET_KEY
jwt = JWTManager(app)

# InfluxDB Client
influx_client = InfluxDBClient(
    url=f"http://{env.INFLUX_HOST}:{env.INFLUX_PORT}",
    token=env.INFLUX_TOKEN,
    org=env.INFLUX_ORG
)
write_api = influx_client.write_api()
query_api = influx_client.query_api()

def decompress_and_parse(request: pvalid.SensorDataWriteRequestBody):
    decoeded_data = base64.b64decode(request.data)
    if request.compression == "gzip":
        decompressed_data = gzip.decompress(decoeded_data)
    elif request.compression == "lz4":
        decompressed_data = lz4.frame.decompress(decoeded_data)
    elif request.compression == "brotli":
        decompressed_data = brotli.decompress(decoeded_data)
    elif request.compression == "none":
        decompressed_data = decoeded_data
    else:
        raise ValueError("Unsupported compression type")
    
    if request.format == "messagepack":
        return msgpack.unpackb(decompressed_data, raw=False)
    elif request.format == "json":
        return json.loads(decompressed_data.decode("utf-8"))
    else:
        raise ValueError("Unsupported format")

def prepare_data(df: pd.DataFrame, format="json", compression="none"):
    """
    DataFrameを指定された形式と圧縮方式で変換
    """
    if format == "json":
        data_bytes = json.dumps(df.to_dict(orient="list")).encode("utf-8")
    elif format == "messagepack":
        data_bytes = msgpack.packb(df.to_dict(orient="list"))
    else:
        raise ValueError(f"Unsupported format: {format}")

    if compression == "gzip":
        compressed_data = gzip.compress(data_bytes)
    elif compression == "lz4":
        compressed_data = lz4.frame.compress(data_bytes)
    elif compression == "brotli":
        compressed_data = brotli.compress(data_bytes)
    elif compression == "none":
        compressed_data = data_bytes
    else:
        raise ValueError(f"Unsupported compression: {compression}")

    encoded_data = base64.b64encode(compressed_data).decode("utf-8")
    return encoded_data

@app.route("/data/write", methods=["POST"])
@jwt_required()
def write_data():
    """
    センサーデータ書き込み API
    ---
    tags:
      - Sensor Data
    summary: センサーデータを InfluxDB に書き込む
    description: 
      認証済みのユーザーが、センサーデータを InfluxDB に書き込む API。
      書き込みには `sensor_write` 権限を持つ JWT が必要であり、JWT に指定された `start_time` から `end_time` の範囲内である必要がある。
      データは `Base64` でエンコードされ、圧縮形式 (`gzip`, `lz4`, `brotli`, `none`) とフォーマット (`json`, `messagepack`) が指定される。
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - compression
            - format
            - data
          properties:
            compression:
              type: string
              enum: ["gzip", "lz4", "brotli", "none"]
              example: "gzip"
              description: "圧縮方式 (`gzip`, `lz4`, `brotli`, `none`)"
            format:
              type: string
              enum: ["json", "messagepack"]
              example: "json"
              description: "データフォーマット (`json`, `messagepack`)"
            data:
              type: string
              example: "H4sIAAAAAAAAE8tIzcnJBwCGphA2BQAAAA=="
              description: "Base64 エンコードされた圧縮データ"
    responses:
      200:
        description: センサーデータ書き込み成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "success"
      400:
        description: 不正なリクエスト（JWT エラー、リクエストボディエラー）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Invalid jwt | Invalid request body"
      500:
        description: サーバー内部エラー（書き込み失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed write data"
    """
    addclaim = get_jwt()
    try:
        participant_id = addclaim["participant_id"]
        if str(addclaim["jwt_role"]) != "sensor_write":
            raise Exception("jwt error")
        start_time_jwt = datetime.fromisoformat(str(addclaim["start_time"]))
        end_time_jwt = datetime.fromisoformat(str(addclaim["end_time"]))
    except:
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        request_data = pvalid.SensorDataWriteRequestBody.model_validate(request.get_json())
    except:
        return jsonify({"code": 400, "message": "Invalid request body"}), 400
    try:
        data = decompress_and_parse(request=request_data)
        data_df = pd.DataFrame(data=data)
        data_df["participant"] = participant_id
        data_df["time"] = pd.to_datetime(data_df["time"])
        if not ((data_df["time"] >= start_time_jwt) & (data_df["time"] <= end_time_jwt)).all():
            raise Exception("Time Error")
        data_df.set_index("time", inplace=True)

        write_api.write(env.INFLUX_BUCKET,
                        env.INFLUX_ORG,
                        record=data_df,
                        data_frame_measurement_name=env.INFLUX_MEASUREMENT,
                        data_frame_tag_columns=["participant"]
                        )
        return jsonify({"code": 200, "message": "success"})
    except Exception as e:
        return jsonify({"code": 500, "message": "Failed write data", "err": f"{e}"}), 500

@app.route("/data/read", methods=["POST"])
@jwt_required()
def read_data():
    """
    センサーデータ取得 API
    ---
    tags:
      - Sensor Data
    summary: 指定された期間のセンサーデータを取得する
    description: 
      認証済みのユーザーが、センサーデータを取得する API。
      読み取りには `sensor_read` 権限を持つ JWT が必要であり、JWT に指定された `start_time` から `end_time` の範囲内である必要がある。
      データは `Base64` でエンコードされ、圧縮形式 (`gzip`, `lz4`, `brotli`, `none`) とフォーマット (`json`, `messagepack`) が指定される。
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - compression
            - format
            - rows
            - start_time
            - end_time
          properties:
            compression:
              type: string
              enum: ["gzip", "lz4", "brotli", "none"]
              example: "gzip"
              description: "圧縮方式 (`gzip`, `lz4`, `brotli`, `none`)"
            format:
              type: string
              enum: ["json", "messagepack"]
              example: "json"
              description: "データフォーマット (`json`, `messagepack`)"
            rows:
              type: array
              items:
                type: string
              example: ["EEG_RAW_TP10", "RRI"]
              description: "取得するセンサーデータの項目リスト"
            start_time:
              type: string
              format: date-time
              example: "2025-01-01T00:00:00Z"
              description: "取得開始時間"
            end_time:
              type: string
              format: date-time
              example: "2025-01-01T01:00:00Z"
              description: "取得終了時間"
    responses:
      200:
        description: センサーデータ取得成功
        schema:
          type: object
          properties:
            compression:
              type: string
              example: "gzip"
            format:
              type: string
              example: "json"
            data:
              type: string
              example: "H4sIAAAAAAAAE8tIzcnJBwCGphA2BQAAAA=="
              description: "Base64 エンコードされた圧縮データ"
      400:
        description: 不正なリクエスト（JWT エラー、リクエストボディエラー）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Invalid jwt | Invalid request body"
      500:
        description: サーバー内部エラー（データ取得失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed read data"
            error:
              type: string
              example: "Database query error"
    """
    addclaim = get_jwt()
    try:
        participant_id = addclaim["participant_id"]
        if str(addclaim["jwt_role"]) != "sensor_read":
            raise Exception("jwt error")
        start_time_jwt = datetime.fromisoformat(str(addclaim["start_time"]))
        end_time_jwt = datetime.fromisoformat(str(addclaim["end_time"]))
    except:
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        request_data = pvalid.SensorDataReadRequestBody.model_validate(request.get_json())
        if start_time_jwt > request_data.start_time or request_data.end_time > end_time_jwt:
            raise Exception("Time Error")
    except:
        return jsonify({"code": 400, "message": "Invalid request body"}), 400
    try:
        field_str = None
        columns_str = None
        for field in request_data.rows:
            if not field_str:
                field_str = f'''r["_field"] == "{field}"'''
            else:
                field_str += f''' or r["_field"] == "{field}"'''
            if not columns_str:
                columns_str = f'''"{field}"'''
            else:
                columns_str += f''', "{field}"'''
        query = f"""
        from(bucket: "{env.INFLUX_BUCKET}")
            |> range(start: {request_data.start_time.isoformat()}, stop: {request_data.end_time.isoformat()})
            |> filter(fn: (r) => r["_measurement"] == "{env.INFLUX_MEASUREMENT}")
            |> filter(fn: (r) => {field_str})
            |> filter(fn: (r) => r["participant"] == "{participant_id}")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
            |> keep(columns: [{columns_str}, "_time"])
        """
        data_df = query_api.query_data_frame(query=query, org=env.INFLUX_ORG)
        data_df = data_df.sort_values(by='_time')
        data_df["_time"] = data_df["_time"].astype(str)
        data_df.rename(columns={"_time": "time"}, inplace=True)
        data_df.drop(columns=["result", "table"], inplace=True)
        ret_data = prepare_data(df=data_df, format=request_data.format, compression=request_data.compression)
        body = pvalid.SensorDataWriteRequestBody(compression=request_data.compression, format=request_data.format, data=ret_data).model_dump()
        return jsonify(body)
    except Exception as e:
        return jsonify({"code": 500, "message": "Failed read data", "error": f"{e}"}), 500

