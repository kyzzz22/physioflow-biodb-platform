import aiohttp
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import jwt
import pandas as pd
import numpy as np
import gzip, lz4.frame, brotli, base64, json, msgpack
from datetime import datetime, timedelta

import env
import pvalid
import p_victoria_metrics
import pevent
import pexperiment
import panalysis
import pml

CONNECTOR_LIMIT = 200
CHUNK_DURATION_SECONDS = 5
# 动态分片参数：将整个时间窗划分为不超过 TARGET_CHUNK_COUNT 个分片，
# 避免大时间窗读回产生数百万次 VM export 请求（固定 5s 分片的隐患）。
TARGET_CHUNK_COUNT = 2000
MIN_CHUNK_SECONDS = 5
MAX_CHUNK_SECONDS = 3600


def resolve_chunk_timedelta(start_dt: datetime, end_dt: datetime, chunk_seconds: float | None = None) -> timedelta:
    """根据请求时间窗自动计算读回分片大小（秒）。

    - 显式指定 chunk_seconds 时直接使用（由 pvalid 校验 1s~86400s）。
    - 未指定时按总时长 / TARGET_CHUNK_COUNT 动态计算，落在 [MIN, MAX] 区间。
    """
    if chunk_seconds is not None:
        return timedelta(seconds=chunk_seconds)
    total_seconds = max((end_dt - start_dt).total_seconds(), MIN_CHUNK_SECONDS)
    dynamic_seconds = max(min(total_seconds / TARGET_CHUNK_COUNT, MAX_CHUNK_SECONDS), MIN_CHUNK_SECONDS)
    return timedelta(seconds=dynamic_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_session
    connector = aiohttp.TCPConnector(limit=CONNECTOR_LIMIT, ssl=False if env.VICTORIA_METRICS_HOST.startswith("http://") else None)
    http_session = aiohttp.ClientSession(connector=connector)
    yield
    await http_session.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

async def prepare_data(victoria_data, format="json", compression="none"):
    data_bytes = await asyncio.to_thread(
        lambda: json.dumps(victoria_data).encode("utf-8") if format == "json" else msgpack.packb(victoria_data)
    )

    compressed = await asyncio.to_thread({
        "gzip": lambda: gzip.compress(data_bytes),
        "lz4": lambda: lz4.frame.compress(data_bytes),
        "brotli": lambda: brotli.compress(data_bytes),
        "none": lambda: data_bytes,
    }[compression])

    return base64.b64encode(compressed).decode("utf-8")

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


# 以下ルーティング

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
        experimenter_id = claims["sub"]
        jwt_role = claims["jwt_role"]
        start_time_jwt = datetime.fromisoformat(claims["start_time"])
        end_time_jwt = datetime.fromisoformat(claims["end_time"])
        experiment_id = claims.get("experiment")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    if request.start_time < start_time_jwt or request.end_time > end_time_jwt:
        raise HTTPException(status_code=400, detail="Request time out of range")

    try:
        chunk_td = resolve_chunk_timedelta(request.start_time, request.end_time, request.chunk_seconds)
        results = await p_victoria_metrics.victoria_metrics_export_and_format_data(
            session=http_session,
            base_metric_name=env.VICTORIA_METRICS_BASE_METRIC_NAME,
            field_indices_list=request.rows,
            participant_id_val=participant_id,
            experimenter_id_val=experimenter_id,
            experiment_id_val=experiment_id,
            overall_start_dt=request.start_time,
            overall_end_dt=request.end_time,
            chunk_timedelta=chunk_td,
            export_url=env.VICTORIA_METRICS_HOST + env.VICTORIA_METRICS_EXPORT_PATH
        )

        encoded = await prepare_data(results, format=request.format, compression=request.compression)
        ret_data = pvalid.SensorDataWriteRequestBody(compression=request.compression, format=request.format, data=encoded).model_dump()
        return JSONResponse(ret_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@app.post("/data/quality")
async def data_quality(
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
        experimenter_id = claims["sub"]
        jwt_role = claims["jwt_role"]
        start_time_jwt = datetime.fromisoformat(claims["start_time"])
        end_time_jwt = datetime.fromisoformat(claims["end_time"])
        experiment_id = claims.get("experiment")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    if request.start_time < start_time_jwt or request.end_time > end_time_jwt:
        raise HTTPException(status_code=400, detail="Request time out of range")

    try:
        chunk_td = resolve_chunk_timedelta(request.start_time, request.end_time, request.chunk_seconds)
        results = await p_victoria_metrics.victoria_metrics_export_and_format_data(
            session=http_session,
            base_metric_name=env.VICTORIA_METRICS_BASE_METRIC_NAME,
            field_indices_list=request.rows,
            participant_id_val=participant_id,
            experimenter_id_val=experimenter_id,
            experiment_id_val=experiment_id,
            overall_start_dt=request.start_time,
            overall_end_dt=request.end_time,
            chunk_timedelta=chunk_td,
            export_url=env.VICTORIA_METRICS_HOST + env.VICTORIA_METRICS_EXPORT_PATH
        )
        quality = p_victoria_metrics.compute_data_quality_stats(results)
        return JSONResponse({"code": 200, "message": "success", "quality": quality})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@app.post("/data/features")
async def data_features(
    request: pvalid.SensorDataReadRequestBody,
    Authorization: str = Header()
):
    """
    特征统计（解析支援第一步）：读回时序后计算逐通道时域+频域特征。

    鉴权与 /data/read 一致（sensor_read 角色）。
    返回 {code, message, features: {total_points, columns, sample_rate_hz}}
    """
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
        experimenter_id = claims["sub"]
        jwt_role = claims["jwt_role"]
        start_time_jwt = datetime.fromisoformat(claims["start_time"])
        end_time_jwt = datetime.fromisoformat(claims["end_time"])
        experiment_id = claims.get("experiment")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    if request.start_time < start_time_jwt or request.end_time > end_time_jwt:
        raise HTTPException(status_code=400, detail="Request time out of range")

    try:
        chunk_td = resolve_chunk_timedelta(request.start_time, request.end_time, request.chunk_seconds)
        results = await p_victoria_metrics.victoria_metrics_export_and_format_data(
            session=http_session,
            base_metric_name=env.VICTORIA_METRICS_BASE_METRIC_NAME,
            field_indices_list=request.rows,
            participant_id_val=participant_id,
            experimenter_id_val=experimenter_id,
            experiment_id_val=experiment_id,
            overall_start_dt=request.start_time,
            overall_end_dt=request.end_time,
            chunk_timedelta=chunk_td,
            export_url=env.VICTORIA_METRICS_HOST + env.VICTORIA_METRICS_EXPORT_PATH
        )
        features = p_victoria_metrics.compute_feature_stats(results)
        return JSONResponse({"code": 200, "message": "success", "features": features})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@app.post("/data/export")
async def export_data(
    request: pvalid.SensorDataExportRequestBody,
    Authorization: str = Header()
):
    """
    联合导出/归档：跨 VictoriaMetrics 时序 + MongoDB 事件 + 实验元数据的合并导出。

    鉴权与 /data/read 一致（sensor_read 角色，时间窗必须落在 JWT 范围内）。
    返回信封：{code, message, sensor, events, experiment}
    - sensor: 读回结果（同 /data/read 的格式化 JSON）
    - events: 按 participant + 时间窗过滤的事件列表（含 experiment_id）
    - experiment: 实验注册表元数据（含数据字典），无可用的实验时返回 null
    """
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
        experimenter_id = claims["sub"]
        jwt_role = claims["jwt_role"]
        start_time_jwt = datetime.fromisoformat(claims["start_time"])
        end_time_jwt = datetime.fromisoformat(claims["end_time"])
        experiment_id = claims.get("experiment") or request.experiment_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    if request.start_time < start_time_jwt or request.end_time > end_time_jwt:
        raise HTTPException(status_code=400, detail="Request time out of range")

    try:
        chunk_td = resolve_chunk_timedelta(request.start_time, request.end_time, request.chunk_seconds)
        results = await p_victoria_metrics.victoria_metrics_export_and_format_data(
            session=http_session,
            base_metric_name=env.VICTORIA_METRICS_BASE_METRIC_NAME,
            field_indices_list=request.rows,
            participant_id_val=participant_id,
            experimenter_id_val=experimenter_id,
            experiment_id_val=experiment_id,
            overall_start_dt=request.start_time,
            overall_end_dt=request.end_time,
            chunk_timedelta=chunk_td,
            export_url=env.VICTORIA_METRICS_HOST + env.VICTORIA_METRICS_EXPORT_PATH
        )

        payload = {"code": 200, "message": "success", "sensor": results}

        if request.include_events:
            events = await asyncio.to_thread(
                pevent.get_events,
                user_id=participant_id,
                experiment_id=experiment_id,
                start_time=request.start_time,
                end_time=request.end_time,
            )
            payload["events"] = events

        if request.include_experiment:
            if experiment_id:
                experiment = await asyncio.to_thread(pexperiment.get_experiment_by_id, experiment_id)
            else:
                experiment = None
            payload["experiment"] = experiment

        return JSONResponse(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")


@app.post("/data/write")
def write_data(
    request: pvalid.SensorDataWriteRequestBody,
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
        experimenter_id = claims["sub"]
        jwt_role = claims["jwt_role"]
        start_time_jwt = datetime.fromisoformat(claims["start_time"])
        end_time_jwt = datetime.fromisoformat(claims["end_time"])
        experiment_id = claims.get("experiment")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT")
    
    if jwt_role != "sensor_write":
        raise HTTPException(status_code=403, detail="Unauthorized role")
    
    try:
        data = decompress_and_parse(data_b64=request.data, compression=request.compression, format=request.format)
        data_df = pd.DataFrame(data=data)
        data_df["participant"] = participant_id
        data_df["experimenter"] = experimenter_id
        if experiment_id:
            data_df["experiment"] = experiment_id
        data_df["time"] = pd.to_datetime(data_df["time"])
        if not ((data_df["time"] >= start_time_jwt) & (data_df["time"] <= end_time_jwt)).all():
            raise Exception("Time Error")
        data_df.set_index("time", inplace=True)
    except:
        raise HTTPException(status_code=400, detail="Bad Data Error")
    
    try:
        tag_columns = ["participant", "experimenter"]
        if experiment_id:
            tag_columns.append("experiment")
        payload = p_victoria_metrics.dataframe_to_line_protocol(
            data_df,
            env.VICTORIA_METRICS_BASE_METRIC_NAME,
            tag_columns=tag_columns
        )
        status = p_victoria_metrics.write_to_victoria_metrics(
            payload=payload,
            vm_write_url=env.VICTORIA_METRICS_HOST + env.VICTORIA_METRICS_WRITE_PATH,
            auth=None,
            timeout=60
        )
        if status:
            return JSONResponse({"code": 200, "message": "success"})
        else:
            raise HTTPException(status_code=500, detail=f"{payload}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")


# ---- ML 训练 / 推理 / 分析结果管理 ----

async def _export_series_data(claims: dict, request) -> dict:
    """按 JWT claim + 请求参数读回时序（供训练/推理复用）。"""
    participant_id = claims["participant_id"]
    experimenter_id = claims["sub"]
    experiment_id = claims.get("experiment")
    chunk_td = resolve_chunk_timedelta(request.start_time, request.end_time, request.chunk_seconds)
    return await p_victoria_metrics.victoria_metrics_export_and_format_data(
        session=http_session,
        base_metric_name=env.VICTORIA_METRICS_BASE_METRIC_NAME,
        field_indices_list=request.rows,
        participant_id_val=participant_id,
        experimenter_id_val=experimenter_id,
        experiment_id_val=experiment_id,
        overall_start_dt=request.start_time,
        overall_end_dt=request.end_time,
        chunk_timedelta=chunk_td,
        export_url=env.VICTORIA_METRICS_HOST + env.VICTORIA_METRICS_EXPORT_PATH
    )


def _decode_sensor_read_jwt(Authorization: str, request) -> dict:
    """通用鉴权：解析 JWT、校验角色与时间窗。返回 claims dict。"""
    try:
        claims = decode_jwt(Authorization)
    except:
        raise HTTPException(status_code=400, detail="JWT Secret Key Error")
    try:
        check_jwt_exp(claims["exp"])
    except:
        raise HTTPException(status_code=400, detail="Expired JWT")
    try:
        jwt_role = claims["jwt_role"]
        start_time_jwt = datetime.fromisoformat(claims["start_time"])
        end_time_jwt = datetime.fromisoformat(claims["end_time"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    if request.start_time < start_time_jwt or request.end_time > end_time_jwt:
        raise HTTPException(status_code=400, detail="Request time out of range")
    return claims


@app.post("/analysis/train/kmeans")
async def train_kmeans(
    request: pvalid.KMeansTrainRequestBody,
    Authorization: str = Header()
):
    """
    KMeans 聚类训练：读回时序 → 特征矩阵 → 训练 → 模型与分析结果落库。

    返回 {code, message, model_id, analysis_id, metrics, parameters}
    """
    claims = _decode_sensor_read_jwt(Authorization, request)
    participant_id = claims["participant_id"]
    experimenter_id = claims["sub"]
    experiment_id = claims.get("experiment")

    try:
        results = await _export_series_data(claims, request)
        X, usable_rows = await asyncio.to_thread(pml.result_to_matrix, results, request.rows)
        if X.shape[0] == 0 or X.shape[1] == 0:
            raise HTTPException(status_code=400, detail="No usable data in the requested window")

        model = pml.KMeans(
            n_clusters=request.n_clusters,
            max_iter=request.max_iter,
            random_state=request.random_state,
        )
        await asyncio.to_thread(model.fit, X)
        parameters = model.to_parameters()
        metrics = {
            "inertia": model.inertia_,
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_clusters": model.n_clusters,
            "label_distribution": pml.label_distribution(model.labels_),
        }

        model_id = f"kmeans_{parameters.get('random_state')}_{participant_id}"
        # 存为一次分析结果（训练即产生一个 analysis 记录）
        analysis = await asyncio.to_thread(
            panalysis.save_analysis,
            model_id=model_id,
            analysis_type="kmeans_train",
            participant_id=participant_id,
            experiment_id=experiment_id,
            rows=usable_rows,
            start_time=request.start_time,
            end_time=request.end_time,
            parameters=parameters,
            metrics=metrics,
            result={"label_distribution": metrics["label_distribution"]},
            created_by=experimenter_id,
        )
        return JSONResponse({
            "code": 200,
            "message": "success",
            "model_id": model_id,
            "analysis_id": analysis["analysis_id"],
            "metrics": metrics,
            "parameters": parameters,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Train error: {str(e)}")


@app.post("/analysis/train/regression")
async def train_regression(
    request: pvalid.LinearRegressionTrainRequestBody,
    Authorization: str = Header()
):
    """
    线性回归训练：rows 最后一列作为目标 y，其余列为特征 X。

    返回 {code, message, model_id, analysis_id, metrics, parameters}
    """
    claims = _decode_sensor_read_jwt(Authorization, request)
    participant_id = claims["participant_id"]
    experimenter_id = claims["sub"]
    experiment_id = claims.get("experiment")

    if len(request.rows) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 rows (features + target)")

    try:
        results = await _export_series_data(claims, request)
        X, usable_rows = await asyncio.to_thread(pml.result_to_matrix, results, request.rows)
        if X.shape[0] == 0 or X.shape[1] < 2:
            raise HTTPException(status_code=400, detail="No usable data in the requested window")

        feature_rows = usable_rows[:-1]
        target_row = usable_rows[-1]
        # 重新按 feature/target 拆分矩阵
        X_all, usable_all = await asyncio.to_thread(pml.result_to_matrix, results, request.rows)
        target_col = len(feature_rows)  # usable_rows 与列顺序一致
        Xf = X_all[:, :target_col]
        y = X_all[:, target_col]

        model = pml.LinearRegression(ridge_alpha=request.ridge_alpha)
        await asyncio.to_thread(model.fit, Xf, y)
        y_pred = await asyncio.to_thread(model.predict, Xf)
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2)) if len(y) > 1 else 0.0
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None

        parameters = model.to_parameters()
        parameters["features"] = feature_rows
        parameters["target"] = target_row
        metrics = {
            "n_samples": int(Xf.shape[0]),
            "n_features": int(Xf.shape[1]),
            "r2": round(r2, 6) if r2 is not None else None,
            "mse": float(ss_res / len(y)) if len(y) else None,
        }

        model_id = f"reg_{participant_id}"
        analysis = await asyncio.to_thread(
            panalysis.save_analysis,
            model_id=model_id,
            analysis_type="linear_regression_train",
            participant_id=participant_id,
            experiment_id=experiment_id,
            rows=request.rows,
            start_time=request.start_time,
            end_time=request.end_time,
            parameters=parameters,
            metrics=metrics,
            result={"r2": metrics["r2"], "mse": metrics["mse"]},
            created_by=experimenter_id,
        )
        return JSONResponse({
            "code": 200,
            "message": "success",
            "model_id": model_id,
            "analysis_id": analysis["analysis_id"],
            "metrics": metrics,
            "parameters": parameters,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Train error: {str(e)}")


@app.post("/analysis/predict")
async def predict_data(
    request: pvalid.PredictRequestBody,
    Authorization: str = Header()
):
    """
    模型推理：按 model_id 加载已训练模型参数，对新时间窗数据预测。

    返回 {code, message, analysis_id, predictions, label_distribution}
    """
    claims = _decode_sensor_read_jwt(Authorization, request)
    participant_id = claims["participant_id"]
    experimenter_id = claims["sub"]
    experiment_id = claims.get("experiment")

    try:
        analysis = await asyncio.to_thread(panalysis.get_analyses, participant_id=participant_id, model_id=request.model_id)
        if not analysis:
            raise HTTPException(status_code=404, detail=f"Model not found: {request.model_id}")
        model_analysis = analysis[0]
        parameters = model_analysis["parameters"]

        model_type = model_analysis["type"]
        results = await _export_series_data(claims, request)

        if model_type.startswith("kmeans"):
            model = pml.KMeans.from_parameters(parameters)
            X, usable_rows = await asyncio.to_thread(pml.result_to_matrix, results, request.rows)
            if X.shape[1] != model.centroids_.shape[1]:
                raise HTTPException(status_code=400, detail=f"Feature mismatch: expected {model.centroids_.shape[1]} features, got {X.shape[1]}")
            labels = await asyncio.to_thread(model.predict, X)
            predictions = [int(v) for v in labels]
            result = {"label_distribution": pml.label_distribution(labels)}
        elif model_type.startswith("linear_regression"):
            model = pml.LinearRegression.from_parameters(parameters)
            X, usable_rows = await asyncio.to_thread(pml.result_to_matrix, results, request.rows)
            if X.shape[1] != len(parameters.get("coef", [])):
                raise HTTPException(status_code=400, detail=f"Feature mismatch: expected {len(parameters.get('coef', []))} features, got {X.shape[1]}")
            pred = await asyncio.to_thread(model.predict, X)
            predictions = [round(float(v), 6) for v in pred]
            result = {"mean_pred": round(float(np.mean(pred)), 6) if len(pred) else None}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported model type: {model_type}")

        analysis_record = await asyncio.to_thread(
            panalysis.save_analysis,
            model_id=request.model_id,
            analysis_type=f"{model_type}_predict",
            participant_id=participant_id,
            experiment_id=experiment_id,
            rows=request.rows,
            start_time=request.start_time,
            end_time=request.end_time,
            parameters={},
            metrics={},
            result=result,
            created_by=experimenter_id,
        )
        return JSONResponse({
            "code": 200,
            "message": "success",
            "analysis_id": analysis_record["analysis_id"],
            "model_id": request.model_id,
            "model_type": model_type,
            "predictions": predictions,
            "result": result,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Predict error: {str(e)}")


@app.get("/analysis/results")
async def list_analyses(
    Authorization: str = Header(),
    analysis_type: str | None = None,
    limit: int = 100,
):
    """
    查询分析结果列表（按当前 JWT 的 participant_id 过滤）。
    """
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
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    try:
        results = await asyncio.to_thread(
            panalysis.get_analyses,
            participant_id=participant_id,
            analysis_type=analysis_type,
            limit=limit,
        )
        return JSONResponse({"code": 200, "message": "success", "analyses": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@app.delete("/analysis/results/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    Authorization: str = Header(),
):
    """
    删除分析结果（仅限当前 JWT participant 拥有的记录）。
    """
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
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT")

    if jwt_role != "sensor_read":
        raise HTTPException(status_code=403, detail="Unauthorized role")

    try:
        existing = await asyncio.to_thread(panalysis.get_analysis_by_id, analysis_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        if existing.get("participant_id") != participant_id:
            raise HTTPException(status_code=403, detail="Not owner")
        deleted = await asyncio.to_thread(panalysis.delete_analysis, analysis_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return JSONResponse({"code": 200, "message": "success", "deleted": True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")