from datetime import datetime, timezone

from flasgger import Swagger
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import get_jwt_identity, get_jwt, jwt_required, JWTManager

import env
import pevent
import pvalid

app = Flask(__name__)
app.config["SWAGGER"] = {
    "title": "API Documentation",
    "uiversion": 3,
    "static_url_path": "/event/flasgger_static",
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/event/apispec_1.json',
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

def parse_iso8601(s: str | None, *, default=None):
    if s is None:
        if default is not None:
            return default
        raise ValueError("missing datetime string")
    s = str(s).strip()
    if not s:
        if default is not None:
            return default
        raise ValueError("empty datetime string")

    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

@app.route("/events", methods=["POST"])
@jwt_required()
def create_event():
    """
    イベント作成 API
    ---
    tags:
      - Events
    summary: 新しいイベントを作成する
    description: 
      認証済みのユーザーが，新しいイベントを作成する API．
      イベントを作成するには `event` 権限を持つ JWT が必要であり、JWT に指定された `start_time` から `end_time` の範囲内である必要がある．
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - start_time
            - event
          properties:
            user_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "イベントの対象ユーザー ID"
            start_time:
              type: string
              format: date-time
              example: "2025-01-01T12:00:00Z"
              description: "イベントの開始時間"
            end_time:
              type: string
              format: date-time
              example: "2025-01-01T12:30:00Z"
              description: "イベントの終了時間（オプション）"
            event:
              type: string
              example: "Running"
              description: "イベントの種類（例: 'Running', 'Sleeping', 'Eating'）"
            description:
              type: string
              example: "Morning jogging session"
              description: "イベントの説（オプション）"
            details:
              type: object
              example: {"location": "park", "duration": "30min"}
              description: "イベントの追加詳細情報（オプション）"
    responses:
      200:
        description: イベント作成成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "success"
            event_id:
              type: uuid
              description: "作成されたイベントの ID"
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
        description: サーバー内部エラー（イベント作成失敗）
        schema:
          type: object
          properties:
            error:
              type: string
              example: "Database insert error"
    """
    create_user_id = get_jwt_identity()
    addclaim = get_jwt()
    try:
        user_id = str(addclaim["user_id"])
        if addclaim["jwt_role"] != "event":
            raise Exception("jwt Error")
        start_time_jwt = parse_iso8601(str(addclaim["start_time"]))
        end_time_jwt = parse_iso8601(str(addclaim["end_time"]))
    except:
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        request_body = pvalid.EventDataCreateRequestBody.model_validate(request.get_json())
        if user_id != request_body.user_id:
            raise Exception("user missmatch")
    except:
        return jsonify({"code": 400, "message": "Invalid request body"}), 400
    if not (start_time_jwt <= request_body.start_time <= end_time_jwt) or (request_body.end_time and not (start_time_jwt <= request_body.end_time <= end_time_jwt)):
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    # experiment 归属：JWT claim 优先（不可伪造，R2）；请求体值须与 claim 一致，否则拒绝
    jwt_experiment = addclaim.get("experiment")
    request_experiment = request_body.experiment_id
    if jwt_experiment and request_experiment and jwt_experiment != request_experiment:
        return jsonify({"code": 400, "message": "Invalid request body"}), 400
    experiment_id = jwt_experiment or request_experiment
    try:
        event_id = pevent.create_event(start_time=request_body.start_time,
                                   end_time=request_body.end_time,
                                   user_id=request_body.user_id,
                                   event=request_body.event,
                                   description=request_body.description,
                                   details=request_body.details,
                                   created_by=create_user_id,
                                   experiment_id=experiment_id)
    except Exception as e:
        return jsonify({"error": f"{e}"}), 500
    return jsonify({"code": 200, "message": "success", "event_id": event_id})

@app.route("/events", methods=["GET"])
@jwt_required()
def get_events():
    """
    イベント取得 API
    ---
    tags:
      - Events
    summary: 指定された条件に一致するイベントを取得する
    description: 
      認証済みのユーザーが，指定された条件に一致するイベントの一覧を取得する API．
      取得には `event` 権限を持つ JWT が必要であり，JWT に指定された `start_time` から `end_time` の範囲内である必要がある．
    security:
      - BearerAuth: []
    parameters:
      - name: role
        in: query
        required: true
        schema:
          type: string
          enum: ["experimenter", "participant"]
        description: "取得するイベントの対象 (`experimenter`: 実行者が作成者のイベント, `participant`: 対象ユーザーのイベント)"
      - name: start_time
        in: query
        required: false
        schema:
          type: string
          format: date-time
        description: "取得開始時間（指定がない場合は JWT の start_time）"
      - name: end_time
        in: query
        required: false
        schema:
          type: string
          format: date-time
        description: "取得終了時間（指定がない場合は JWT の end_time）"
    responses:
      200:
        description: イベント取得成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "success"
            event_list:
              type: array
              items:
                type: object
                properties:
                  event_id:
                    type: uuid
                    description: "イベント ID"
                  user_id:
                    type: string
                    pattern: "^[A-Za-z0-9_-]{21}$"
                    description: "イベントの対象ユーザー ID"
                  start_time:
                    type: string
                    format: date-time
                    example: "2025-01-01T12:00:00Z"
                  end_time:
                    type: string
                    format: date-time
                    example: "2025-01-01T12:30:00Z"
                  event:
                    type: string
                    example: "Running"
                    description: "イベントの種類"
                  description:
                    type: string
                    example: "Morning jogging session"
                    description: "イベントの説明"
                  created_by:
                    type: string
                    pattern: "^[A-Za-z0-9_-]{21}$"
                    description: "イベント作成者の ID"
      400:
        description: 不正なリクエスト（JWT エラー、クエリパラメータエラー）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Invalid jwt | require query parameter | invalid query parameter"
      500:
        description: サーバー内部エラー（イベント取得失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed to fetch events"
    """
    exe_user_id = get_jwt_identity()
    addclaim = get_jwt()
    try:
        user_id = str(addclaim["user_id"])
        if addclaim["jwt_role"] != "event":
            raise Exception("jwt Error")
        start_time_jwt = parse_iso8601(str(addclaim["start_time"]))
        end_time_jwt = parse_iso8601(str(addclaim["end_time"]))
    except:
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    role_str = request.args.get("role")
    try:
        start_time = parse_iso8601(request.args.get("start_time"))
    except (ValueError, TypeError):
        start_time = start_time_jwt
    try:
        end_time = parse_iso8601(request.args.get("end_time"))
    except (ValueError, TypeError):
        end_time = end_time_jwt
    if not (start_time_jwt <= start_time <= end_time_jwt) or not (start_time_jwt <= end_time <= end_time_jwt):
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    experiment_id = request.args.get("experiment_id")
    if role_str:
        if role_str == "experimenter":
            event_list = pevent.get_events(created_user_id=exe_user_id, user_id=user_id, start_time=start_time, end_time=end_time, experiment_id=experiment_id)
        elif role_str == "participant":
            event_list = pevent.get_events(user_id=user_id, start_time=start_time, end_time=end_time, experiment_id=experiment_id)
        else:
            return jsonify({"code": 400, "message": "invalid query parameter"}), 400
        return jsonify({"code": 200, "message": "success", "event_list": event_list})
    else:
        return jsonify({"code": 400, "message": "require query parameter"}), 400

@app.route("/events/<event_id>", methods=["DELETE"])
@jwt_required()
def delete_event(event_id: str):
    """
    イベント削除 API
    ---
    tags:
      - Events
    summary: 指定されたイベントを削除する
    description: 
      認証済みのユーザーが，自分が作成したイベントを削除する API．
      削除には `event` 権限を持つ JWT が必要であり，JWT に指定された `start_time` から `end_time` の範囲内である必要がある．
      削除対象のイベントの作成者 (`created_by`) が現在のユーザーと一致している場合のみ削除可能．
    security:
      - BearerAuth: []
    parameters:
      - name: event_id
        in: path
        required: true
        schema:
          type: uuid
        description: "削除対象のイベント ID"
    responses:
      200:
        description: イベント削除成功
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
        description: 不正なリクエスト（JWT エラー）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Invalid jwt"
      401:
        description: 権限エラー（イベントが存在しない，削除権限なし）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Event not found | Unauthorized"
      500:
        description: サーバー内部エラー（イベント削除失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed to delete event"
    """
    exe_user_id = get_jwt_identity()
    addclaim = get_jwt()
    try:
        user_id = str(addclaim["user_id"])
        if addclaim["jwt_role"] != "event":
            raise Exception("jwt Error")
        start_time_jwt = parse_iso8601(str(addclaim["start_time"]))
        end_time_jwt = parse_iso8601(str(addclaim["end_time"]))
    except:
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        event = pevent.get_event_by_event_id(event_id=event_id)
    except:
        return jsonify({"code": 401, "message": "Event not found"}), 401
    if not (start_time_jwt <= event.start_time.replace(tzinfo=timezone.utc) <= end_time_jwt) or not (start_time_jwt <= event.end_time.replace(tzinfo=timezone.utc) <= end_time_jwt):
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    if event.created_by != exe_user_id or event.user_id != user_id:
        return jsonify({"code": 401, "message": "Unauthorized"}), 401
    pevent.delete_event(event_id=event_id)
    return jsonify({"code": 200, "message": "success"})

@app.route("/events/<event_id>", methods=["POST"])
@jwt_required()
def update_event(event_id: str):
    """
    イベント更新 API
    ---
    tags:
      - Events
    summary: 指定されたイベントの情報を更新する
    description: 
      認証済みのユーザーが，指定されたイベントの情報を更新する API．
      更新には `event` 権限を持つ JWT が必要であり，JWT に指定された `start_time` から `end_time` の範囲内である必要がある．
      また，イベントの作成者 (`created_by`) が現在のユーザーと一致している場合のみ更新が可能．
      更新可能なフィールドは `start_time`，`end_time`，`event`，`description`，`details` である．
    security:
      - BearerAuth: []
    parameters:
      - name: event_id
        in: path
        required: true
        schema:
          type: string
        description: "更新対象のイベント ID"
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            start_time:
              type: string
              format: date-time
              example: "2025-01-01T12:00:00Z"
              description: "更新後のイベント開始時間（オプション）"
            end_time:
              type: string
              format: date-time
              example: "2025-01-01T12:30:00Z"
              description: "更新後のイベント終了時間（オプション）"
            event:
              type: string
              example: "Running"
              description: "更新後のイベントの種類（オプション）"
            description:
              type: string
              example: "Morning jogging session"
              description: "更新後のイベントの説明（オプション）"
            details:
              type: object
              example: {"location": "park", "duration": "30min"}
              description: "更新後のイベント詳細情報（オプション）"
    responses:
      200:
        description: イベント更新成功
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
        description: 不正なリクエスト（JWT エラー、リクエストボディエラー、無効な更新）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Invalid jwt | Invalid request body | Invalid change"
      401:
        description: 権限エラー（更新権限なし）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Unauthorized"
      500:
        description: サーバー内部エラー（イベント更新失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed update data"
    """
    exe_user_id = get_jwt_identity()
    addclaim = get_jwt()
    try:
        user_id = str(addclaim["user_id"])
        if addclaim["jwt_role"] != "event":
            raise Exception("jwt Error")
        start_time_jwt = parse_iso8601(str(addclaim["start_time"]))
        end_time_jwt = parse_iso8601(str(addclaim["end_time"]))
    except:
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        event = pevent.get_event_by_event_id(event_id=event_id)
    except:
        return jsonify({"code": 400, "message": "No Exist Event ID"})
    if event.created_by != exe_user_id or event.user_id != user_id:
        return jsonify({"code": 401, "message": "Unauthorized"}), 401
    if not (start_time_jwt <= event.start_time.replace(tzinfo=timezone.utc) <= end_time_jwt) or not (start_time_jwt <= event.end_time.replace(tzinfo=timezone.utc) <= end_time_jwt):
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        post_data = pvalid.EventDateUpdatePostBody.model_validate(request.get_json())
    except:
        return jsonify({"code": 400, "message": "Invalid request body"}), 400
    # experiment 归属：更新 experiment 时须与 JWT claim 一致（不可伪造，R2）
    jwt_experiment = addclaim.get("experiment")
    if post_data.experiment_id and jwt_experiment and post_data.experiment_id != jwt_experiment:
        return jsonify({"code": 400, "message": "Invalid request body"}), 400
    updated_event = event.model_copy(update=post_data.model_dump(exclude_none=True))
    try:
        updated_event = pvalid.EventData.model_validate(updated_event.model_dump())
    except:
        return jsonify({"code": 400, "message": "Invalid change"}), 400
    if not (start_time_jwt <= updated_event.start_time.replace(tzinfo=timezone.utc) <= end_time_jwt) or not (start_time_jwt <= updated_event.end_time.replace(tzinfo=timezone.utc) <= end_time_jwt):
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        pevent.update_event(updated_event)
        return jsonify({"code": 200, "message": "success"})
    except:
        return jsonify({"code": 500, "message": "Failed update data"}), 500