from datetime import timedelta, date
from functools import wraps
import os

from flasgger import Swagger
from flask import Flask, url_for, request, render_template, session, redirect, jsonify
from flask_cors import CORS
from flask_jwt_extended import create_access_token, get_jwt_identity, get_jwt, jwt_required, JWTManager
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


import env
import psql
import ptoken
import pvalid
import pexperiment

app = Flask(__name__)
app.config["SWAGGER"] = {
    "title": "API Documentation",
    "uiversion": 3,
    "static_url_path": "/auth/flasgger_static",
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/auth/apispec_1.json',
        }
    ],
}
swagger = Swagger(app)
CORS(app)
app.secret_key = env.APP_SECRET_KEY

# 本番環境では消す
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app.config['JSON_AS_ASCII'] = False

# JWT
app.config["JWT_SECRET_KEY"] = env.APP_JWT_SECRET_KEY
jwt = JWTManager(app)

GOOGLE_CLIENT_ID = env.GOOGLE_CLIENT_ID

def require_json(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.headers['Content-Type'] != 'application/json':
            return jsonify({"code": 400, "message": "Content Type Error"}), 400
        else:
            try:
                data_json = request.get_json()
            except:
                return jsonify({"code": 400, "message": "Json Empty Error"}), 400
            return f(*args, **kwargs, data_json=data_json)
    return wrapper

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/user/info", methods=["GET"])
@jwt_required()
def get_user_info():
    """
    ユーザー情報取得 API
    ---
    tags:
      - User
    security:
      - BearerAuth: []
    responses:
      200:
        description: ユーザー情報の取得成功
        schema:
          type: object
          properties:
            id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "ユーザーID"
            email:
              type: string
              example: "user@example.com"
              description: "ユーザーのメールアドレス"
            name:
              type: string
              example: "John Doe"
              description: "ユーザーの名前"
            sex:
              type: int
              enum: [0, 1, 2, 9]
              example: 1
              description: "0: 不明, 1: 男性, 2: 女性, 9: 適用不能"
            birthdate:
              type: string
              format: date
              example: "1990-01-01"
              description: "ユーザーの生年月日"
      400:
        description: 不正なリクエスト（JWTエラーまたはユーザーが見つからない場合）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Jwt Error | User Not Found"
      401:
        description: 認証エラー（トークンが必要）
    """
    try:
        jwt = get_jwt()
        is_webui_jwt = jwt.get("WebUI")
        is_service_jwt = jwt.get("WebService")
        if not is_webui_jwt and not is_service_jwt:
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    try:
        user_id = get_jwt_identity()
        user = psql.get_user_from_id(id=user_id)
    except:
        return jsonify({"code": 400, "message": "User Not Found"}), 400
    date_str = user["birth_date"].isoformat() if user["birth_date"] else None
    ret_data = {"id": user["id"], "email": user["email"], "name": user["name"], "sex": user["sex"], "birthdate": date_str}
    return jsonify(ret_data)

@app.route("/user/info", methods=["POST"])
@require_json
@jwt_required()
def update_user_info(data_json):
    """
    ユーザー情報更新 API
    ---
    tags:
      - User
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              example: "John Doe"
              description: "ユーザーの名前"
            sex:
              type: integer
              enum: [0, 1, 2, 9]
              example: 1
              description: "0: 不明, 1: 男性, 2: 女性, 9: 適用不能"
            birthdate:
              type: string
              format: date
              example: "1990-01-01"
              description: "ユーザーの生年月日"
    responses:
      200:
        description: ユーザー情報の更新成功
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
        description: 不正なリクエスト
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Jwt Error | Json Schema Error | User Not Found"
      500:
        description: サーバー内部エラー（データ更新失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed Update User Info"
    """
    try:
        is_webui_jwt = get_jwt()["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    try:
        name = data_json["name"]
        sex = data_json["sex"]
        birth_date = data_json["birthdate"]
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    user_id = get_jwt_identity()
    try:
        user = psql.get_user_from_id(id=user_id)
    except:
        return jsonify({"code": 400, "message": "User Not Found"}), 400
    try:
        psql.update_user_data(user["id"], name, sex, birth_date)
    except:
        return jsonify({"code": 500, "message": "Failed Update User Info"}), 500
    return jsonify({"code": 200, "message": "success"})

@app.route("/user", methods=["POST"])
@require_json
@jwt_required()
def create_experimenter(data_json):
    """
    ユーザー作成 API
    ---
    tags:
      - User
    summary: 新しいユーザーを作成する
    description: 
      認証済みの管理者ユーザーが，新しいユーザーを作成するためのAPI．
      作成されたユーザーはデフォルトで "normal" ロールを持つ．
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - email
            - role
          properties:
            email:
              type: string
              format: email
              example: "user@example.com"
            role:
              type: string
              enum: [normal]
              example: "normal"
              description: "ユーザーのロール（現在は 'normal' のみサポート）"
    responses:
      200:
        description: ユーザー作成成功
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
        description: 不正なリクエスト（JWTエラー、JSONスキーマエラー、または権限エラー）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Jwt Error | Json Schema Error | Role Error"
      500:
        description: サーバー内部エラー（ユーザー作成失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed Create User"
    """
    try:
        add_claim = get_jwt()
        is_webui_jwt = add_claim["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
        role = add_claim["userRole"]
        if role != "admin":
            raise Exception("Role Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    try:
        request_data = pvalid.PostUserRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        user = psql.add_user(request_data.email)
        # if request_data.role != "normal":
        #     psql.update_user_role(user["id"], request_data.role)
        return jsonify({"code": 200, "message": "success"})
    except:
        return jsonify({"code": 500, "message": "Failed Create User"}), 500

def _require_admin():
    """WebUI 管理员 JWT 校验（与 create_user 相同的鉴权模式）。返回错误响应或 None。"""
    try:
        add_claim = get_jwt()
        if not add_claim["WebUI"]:
            raise Exception("Jwt Error")
        if add_claim["userRole"] != "admin":
            raise Exception("Role Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    return None

def _require_read():
    """读取元数据（participant/实验注册表）的宽松鉴权：WebUI / WebService / sensor_read / sensor_write / event 角色均可。返回错误响应或 None。"""
    try:
        jwt = get_jwt()
        is_webui_jwt = jwt.get("WebUI")
        is_service_jwt = jwt.get("WebService")
        jwt_role = jwt.get("jwt_role")
        if not (is_webui_jwt or is_service_jwt or jwt_role in ("sensor_read", "sensor_write", "event")):
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    return None

@app.route("/experiment", methods=["POST"])
@require_json
@jwt_required()
def create_experiment(data_json):
    """
    実験登録 API（管理者）
    ---
    tags:
      - Experiment
    summary: 新しい実験（experiment）を登録する
    description: 実験のメタデータ（名称・ラベル・説明・データ辞書）を登録する．実験は時系列・イベント書き込み時の experiment タグ値と対応する．
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            experiment_id:
              type: string
              description: "実験ID（省略時は自動生成）"
            name:
              type: string
              description: "実験の一意な名称（時系列/イベント書き込みで使用する experiment 値）"
            label:
              type: string
              description: "人間可読なラベル"
            description:
              type: string
              description: "実験の説明"
            dictionary:
              type: object
              description: "データ辞書：チャンネル名 → 定義（label/unit/type など）"
    responses:
      200:
        description: 実験登録成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            experiment:
              type: object
      400:
        description: 不正なリクエスト（JWTエラー、JSONスキーマエラー、名称・ID重複）
      500:
        description: サーバー内部エラー
    """
    admin_error = _require_admin()
    if admin_error:
        return admin_error
    try:
        request_data = pvalid.ExperimentCreateRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        if pexperiment.is_name_taken(request_data.name):
            return jsonify({"code": 400, "message": "Experiment name already exists"}), 400
        experiment = pexperiment.create_experiment(
            name=request_data.name,
            label=request_data.label,
            description=request_data.description,
            dictionary=request_data.dictionary,
            created_by=str(get_jwt_identity()),
            experiment_id=request_data.experiment_id,
        )
        return jsonify({"code": 200, "message": "success", "experiment": experiment})
    except ValueError as e:
        return jsonify({"code": 400, "message": str(e)}), 400
    except:
        return jsonify({"code": 500, "message": "Failed Create Experiment"}), 500

@app.route("/experiments", methods=["GET"])
@jwt_required()
def get_experiments():
    """
    実験一覧取得 API（管理者）
    ---
    tags:
      - Experiment
    summary: 登録済みの実験一覧を取得する
    security:
      - BearerAuth: []
    responses:
      200:
        description: 実験一覧
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            experiments:
              type: array
              items:
                type: object
      400:
        description: JWTエラー
    """
    admin_error = _require_read()
    if admin_error:
        return admin_error
    try:
        return jsonify({"code": 200, "message": "success", "experiments": pexperiment.get_experiments()})
    except:
        return jsonify({"code": 500, "message": "Failed Get Experiments"}), 500

@app.route("/experiment/<experiment_id>", methods=["GET"])
@jwt_required()
def get_experiment(experiment_id):
    """
    実験詳細取得 API（管理者）
    ---
    tags:
      - Experiment
    summary: 指定した実験の詳細を取得する
    security:
      - BearerAuth: []
    parameters:
      - name: experiment_id
        in: path
        required: true
        type: string
    responses:
      200:
        description: 実験詳細
      400:
        description: JWTエラー
      404:
        description: 実験が見つからない
    """
    admin_error = _require_read()
    if admin_error:
        return admin_error
    try:
        experiment = pexperiment.get_experiment_by_id(experiment_id)
        if not experiment:
            return jsonify({"code": 404, "message": "Experiment Not Found"}), 404
        return jsonify({"code": 200, "message": "success", "experiment": experiment})
    except:
        return jsonify({"code": 500, "message": "Failed Get Experiment"}), 500

@app.route("/experiment/<experiment_id>", methods=["POST"])
@require_json
@jwt_required()
def update_experiment(experiment_id, data_json):
    """
    実験更新 API（管理者）
    ---
    tags:
      - Experiment
    summary: 指定した実験のメタデータを更新する
    security:
      - BearerAuth: []
    parameters:
      - name: experiment_id
        in: path
        required: true
        type: string
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
            label:
              type: string
            description:
              type: string
            dictionary:
              type: object
    responses:
      200:
        description: 更新成功
      400:
        description: JWTエラー / JSONスキーマエラー / 名称重複
      404:
        description: 実験が見つからない
    """
    admin_error = _require_admin()
    if admin_error:
        return admin_error
    try:
        request_data = pvalid.ExperimentUpdateRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        update_data = request_data.model_dump(exclude_unset=True, exclude_none=True)
        if "name" in update_data and pexperiment.is_name_taken(update_data["name"], exclude_experiment_id=experiment_id):
            return jsonify({"code": 400, "message": "Experiment name already exists"}), 400
        experiment = pexperiment.update_experiment(experiment_id, update_data)
        if not experiment:
            return jsonify({"code": 404, "message": "Experiment Not Found"}), 404
        return jsonify({"code": 200, "message": "success", "experiment": experiment})
    except:
        return jsonify({"code": 500, "message": "Failed Update Experiment"}), 500

@app.route("/experiment/<experiment_id>", methods=["DELETE"])
@jwt_required()
def delete_experiment(experiment_id):
    """
    実験削除 API（管理者）
    ---
    tags:
      - Experiment
    summary: 指定した実験を削除する
    security:
      - BearerAuth: []
    parameters:
      - name: experiment_id
        in: path
        required: true
        type: string
    responses:
      200:
        description: 削除成功
      400:
        description: JWTエラー
      404:
        description: 実験が見つからない
    """
    admin_error = _require_admin()
    if admin_error:
        return admin_error
    try:
        if not pexperiment.delete_experiment(experiment_id):
            return jsonify({"code": 404, "message": "Experiment Not Found"}), 404
        return jsonify({"code": 200, "message": "success"})
    except:
        return jsonify({"code": 500, "message": "Failed Delete Experiment"}), 500

@app.route("/experiment/<experiment_id>/dictionary", methods=["GET"])
@jwt_required()
def get_experiment_dictionary(experiment_id):
    """
    データ辞書取得 API（管理者）
    ---
    tags:
      - Experiment
    summary: 指定した実験のデータ辞書（チャンネル → 定義）を取得する
    security:
      - BearerAuth: []
    parameters:
      - name: experiment_id
        in: path
        required: true
        type: string
    responses:
      200:
        description: データ辞書
      400:
        description: JWTエラー
      404:
        description: 実験が見つからない
    """
    admin_error = _require_read()
    if admin_error:
        return admin_error
    try:
        dictionary = pexperiment.get_experiment_dictionary(experiment_id)
        if dictionary is None:
            return jsonify({"code": 404, "message": "Experiment Not Found"}), 404
        return jsonify({"code": 200, "message": "success", "dictionary": dictionary})
    except:
        return jsonify({"code": 500, "message": "Failed Get Dictionary"}), 500

@app.route("/experiment/<experiment_id>/dictionary", methods=["POST"])
@require_json
@jwt_required()
def update_experiment_dictionary(experiment_id, data_json):
    """
    データ辞書更新 API（管理者）
    ---
    tags:
      - Experiment
    summary: 指定した実験のデータ辞書（チャンネル → 定義）を全体置換で更新する
    security:
      - BearerAuth: []
    parameters:
      - name: experiment_id
        in: path
        required: true
        type: string
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - dictionary
          properties:
            dictionary:
              type: object
              description: "チャンネル名 → 定義（label/unit/type など）"
    responses:
      200:
        description: 更新成功
      400:
        description: JWTエラー / JSONスキーマエラー
      404:
        description: 実験が見つからない
    """
    admin_error = _require_admin()
    if admin_error:
        return admin_error
    try:
        request_data = pvalid.ExperimentDictionaryUpdateRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        experiment = pexperiment.update_experiment_dictionary(experiment_id, request_data.dictionary)
        if not experiment:
            return jsonify({"code": 404, "message": "Experiment Not Found"}), 404
        return jsonify({"code": 200, "message": "success", "experiment": experiment})
    except:
        return jsonify({"code": 500, "message": "Failed Update Dictionary"}), 500

@app.route("/participant", methods=["POST"])
@require_json
@jwt_required()
def create_participant(data_json):
    """
    被計測者作成 API
    ---
    tags:
      - Participant
    summary: 新しい被計測者を作成する
    description: 認証済みのユーザーが，新しい被計測者を作成するためのAPI．
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - email
          properties:
            email:
              type: string
              format: email
              example: "participant@example.com"
            name:
              type: string
              example: "Participant Name"
              description: "被計測者の名前（オプション）"
              minLength: 2
              maxLength: 36
            sex:
              type: integer
              enum: [0, 1, 2, 9]
              example: 1
              description: "被計測者の性別（オプション）0: 不明, 1: 男性, 2: 女性, 9: 適用不能"
            birthdate:
              type: string
              format: date
              example: "2000-01-01"
              description: "被計測者の生年月日（オプション）"
    responses:
      200:
        description: 被計測者作成成功
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
        description: 不正なリクエスト（JWTエラー、JSONスキーマエラー）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Jwt Error | Json Schema Error"
      500:
        description: サーバー内部エラー（被計測者作成失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed Create Participant"
    """
    try:
        is_webui_jwt = get_jwt()["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    try:
        request_data = pvalid.PostParticipantRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        participant_data = psql.add_participant(request_data.email)
        if request_data.name is not None or request_data.sex is not None or request_data.birthdate is not None:
            psql.update_participant_data(
                participant_id=participant_data["id"],
                name=request_data.name,
                sex=request_data.sex,
                birth_date=request_data.birthdate,
                is_enable=None,
            )
        return jsonify({"code": 200, "message": "success", "id": participant_data["id"]})
    except:
        return jsonify({"code": 500, "message": "Failed Create Participant"}), 500

@app.route("/participant", methods=["GET"])
@jwt_required()
def get_all_participant():
    """
    被計測者一覧取得 API
    ---
    tags:
      - Participant
    summary: すべての被計測者の一覧を取得する
    description: 認証済みのユーザーが，すべての被計測者の一覧を取得するためのAPI．
    security:
      - BearerAuth: []
    responses:
      200:
        description: 被計測者一覧の取得成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "success"
            participants:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                    pattern: "^[A-Za-z0-9_-]{21}$"
                  email:
                    type: string
                    format: email
                    example: "participant@example.com"
                  name:
                    type: string
                    example: "Participant Name"
                    description: "被計測者の名前"
                  sex:
                    type: integer
                    enum: [0, 1, 2, 9]
                    example: 1
                    description: "被計測者の性別 0: 不明, 1: 男性, 2: 女性, 9: 適用不能"
                  birth_date:
                    type: string
                    format: date
                    example: "2000-01-01"
                    description: "被計測者の生年月日"
                  is_enable:
                    type: boolean
                    example: true
                    description: "被計測者の有効/無効"
      400:
        description: 認証エラー
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Jwt Error"
      500:
        description: サーバーエラー
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "failed fetch participant"
    """
    try:
        jwt = get_jwt()
        is_webui_jwt = jwt.get("WebUI")
        is_service_jwt = jwt.get("WebService")
        jwt_role = jwt.get("jwt_role")
        if not (is_webui_jwt or is_service_jwt or jwt_role in ("sensor_read", "sensor_write", "event")):
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    try:
        participants = psql.get_all_participant()
        for participant in participants:
            if participant["birth_date"] is not None:
                participant["birth_date"] = participant["birth_date"].isoformat()
        return jsonify({"code": 200, "message": "success", "participants": participants})
    except:
        return jsonify({"code": 500, "message": "failed fetch participant"})

@app.route("/participant/<participant_id>", methods=["POST"])
@require_json
@jwt_required()
def update_participant(participant_id: str, data_json):
    """
    被計測者情報更新 API
    ---
    tags:
      - Participant
    summary: 指定された被計測者の情報を更新する
    description: 認証済みのユーザーが，指定された被計測者の情報を更新するためのAPI．
    security:
      - BearerAuth: []
    parameters:
      - name: participant_id
        in: path
        required: true
        schema:
          type: string
          pattern: "^[A-Za-z0-9_-]{21}$"
        description: "更新する対象の被計測者ID"
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              example: "Participant Name"
            sex:
              type: integer
              enum: [0, 1, 2, 9]
              example: 1
              description: "被計測者の性別 0: 不明, 1: 男性, 2: 女性, 9: 適用不能"
            birth_date:
              type: string
              format: date
              example: "2000-01-01"
              description: "被計測者の生年月日"
            is_enable:
              type: boolean
              example: true
              description: "被計測者の有効/無効"
    """
    try:
        add_claim = get_jwt()
        is_webui_jwt = add_claim["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
        role = add_claim["userRole"]
        if role != "admin":
            raise Exception("Role Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    try:
        request_body = pvalid.PostParticipantDataRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        psql.update_participant_data(
            participant_id=participant_id,
            name=request_body.name,
            sex=request_body.sex,
            birth_date=request_body.birthdate,
            is_enable=request_body.is_enable
        )
        return jsonify({"code": 200, "message": "success"})
    except:
        return jsonify({"code": 500, "message": "failed update data"})

@app.route("/participant/<participant_id>", methods=["GET"])
@jwt_required()
def get_participant(participant_id: str):
    """
    被計測者情報取得 API
    ---
    tags:
      - Participant
    summary: 指定された被計測者の情報を取得する
    description: 認証済みのユーザーが，指定された被計測者の情報を取得するためのAPI．
    security:
      - BearerAuth: []
    parameters:
      - name: participant_id
        in: path
        required: true
        schema:
          type: string
          pattern: "^[A-Za-z0-9_-]{21}$"
        description: "取得する対象の被計測者ID"
    responses:
      200:
        description: 被計測者情報の取得成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "success"
            participant:
              type: object
              properties:
                id:
                  type: string
                  pattern: "^[A-Za-z0-9_-]{21}$"
                email:
                  type: string
                  format: email
                  example: "participant@example.com"
    """
    try:
        is_webui_jwt = get_jwt()["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    try:
        participant = psql.get_user_from_id(participant_id)
        if participant["birth_date"] is not None:
            participant["birth_date"] = participant["birth_date"].isoformat()
        return jsonify({"code": 200, "message": "success", "participant": participant})
    except:
        return jsonify({"code": 500, "message": "failed fetch participant"}), 500

@app.route("/google/callback", methods=["POST"])
def google_callback():
    """
    Google OAuth コールバック API
    ---
    tags:
      - Authentication
    summary: Google の OAuth 認証を処理し，JWT アクセストークンを発行する
    description: 
      Google OAuth の認証コードを受け取り，検証後にユーザー情報を取得し，JWT アクセストークンを発行する．
      ユーザーが未登録の場合はエラー
    security:
      - BearerAuth: []
    parameters:
      - name: Authorization
        in: header
        required: true
        schema:
          type: string
          example: "Bearer ya29.a0AfH6SM..."
        description: "Google OAuth 認証コード（Authorization ヘッダーの Bearer トークンとして送信）"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: 
            - role
          properties:
            role:
              type: string
              enum: ["manage", "service"]
              description: "要求するJWTの種類.これによってJWTの権限範囲が変わる."
    responses:
      200:
        description: 認証成功（JWT アクセストークンを発行）
        schema:
          type: object
          properties:
            access_token:
              type: string
              example: "eyJhbGciOiJIUz..."
      400:
        description: 不正なリクエスト（email 情報が取得できなかった場合, roleを指定していない場合, roleが想定外の入力の場合）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Bad Request | Require role | Invalid role"
      401:
        description: 認証エラー（Google の OAuth 検証に失敗した場合）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Authenticated Error"
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"code": 400, "message": "Bad Request: Missing or invalid Authorization header"}), 400
    authcode = auth_header[7:]
    try:
        # Google の署名時刻と本機時計の数秒差により、クリック直後の iat が
        # 未来になり verify が失敗するため、clock_skew を許容する（既定は 0）
        idinfo = id_token.verify_oauth2_token(
            authcode,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=300,
        )
        try:
            email = idinfo["email"]
        except:
            return jsonify({"code": 400, "message": "Bad Request"}), 400
        try:
            user = psql.get_user_from_email(email)
        except:
            return jsonify({"code": 401, "message": "Not found account"}), 401
        try:
            role = str(request.get_json()["role"])
        except:
            return jsonify({"code": 400, "message": "Require role"}), 400
        if role == "manage":
            additional_claim = {"WebUI": True, "userRole": user["role"]}
            access_token = create_access_token(identity=user["id"], expires_delta=timedelta(minutes=10), additional_claims=additional_claim)
        elif role == "service":
            additional_claim = {"WebService": True, "userRole": user["role"]}
            access_token = create_access_token(identity=user["id"], expires_delta=timedelta(minutes=180), additional_claims=additional_claim)
        else:
            return jsonify({"code": 400, "message": "Invalid role"}), 400
        return jsonify({"access_token": access_token}), 200
    except:
        return jsonify({"code": 401, "message": "Authenticated Error"}), 401

@app.route("/token", methods=["POST"])
@require_json
@jwt_required()
def create_token(data_json):
    """
    長期トークン発行 API
    ---
    tags:
      - Authentication
    summary: 長期トークンを発行する
    description: 
      認証済みのユーザーが，新しい長期トークンを発行するための API．
      トークンは指定したスコープ (`scopes`) で利用可能．
      `expiration_days` の範囲内でトークンの有効期限を設定できる．
    security:
      - BearerAuth: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required: 
            - scopes
            - expiration_days
          properties:
            scopes:
              type: array
              items:
                type: string
              example: ["all"]
              description: "このトークンで許可されるスコープの一覧"
            expiration_days:
              type: integer
              minimum: 1
              maximum: 365
              example: 30
              description: "トークンの有効期間（日数）"
            description:
              type: string
              example: "This is an API token for data access"
              description: "トークンの補足情報（オプション）"
    responses:
      200:
        description: トークン発行成功
        schema:
          type: object
          properties:
            token:
              type: string
              pattern: "^[A-Za-z0-9_-]{43,44}$"
      400:
        description: 不正なリクエスト（JSON スキーマエラー、JWTエラー）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Jwt Error | Json Schema Error"
      500:
        description: サーバー内部エラー（トークン生成失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 500
            message:
              type: string
              example: "Failed generate token"
    """
    try:
        is_webui_jwt = get_jwt()["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    user_id = get_jwt_identity()
    try:
        request_data = pvalid.CreateTokenRequestBody.model_validate(data_json)
        if len(request_data.scopes) <= 0:
            raise ValueError("Invalid Length")
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        raw_token = ptoken.create_token(
            user_id=user_id,
            scopes=request_data.scopes,
            expiration_days=request_data.expiration_days,
            description=request_data.description
            )
    except:
        return jsonify({"code": 500, "message": "Failed generate token"}), 500
    return jsonify({"token": raw_token})

@app.route("/token/<tokenid>", methods=["DELETE"])
@jwt_required()
def delete_token(tokenid):
    """
    長期トークン削除 API
    ---
    tags:
      - Authentication
    summary: 指定されたトークンを削除する
    description: 
      認証済みのユーザーが，自身の発行した長期トークンを削除するための API．
      JWT による認証が必要であり，対象の `tokenid` が現在のユーザーのものである必要がある．
    security:
      - BearerAuth: []
    parameters:
      - name: tokenid
        in: path
        required: true
        schema:
          type: string
          pattern: "^[0-9a-f]{64}$"
        description: "削除する対象のトークンID"
    responses:
      200:
        description: トークン削除成功
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
        description: 不正なリクエスト（JWT エラー または 削除失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Jwt Error | Failed"
    """
    try:
        is_webui_jwt = get_jwt()["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    user_id = get_jwt_identity()
    if ptoken.delete_token(token_id=tokenid, user_id=user_id):
        return jsonify({"code": 200, "message": "success"}), 200
    else:
        return jsonify({"code": 400, "message": "Failed"}), 400

@app.route("/token/<tokenid>", methods=["POST"])
@require_json
@jwt_required()
def update_token(tokenid, data_json):
    """
    長期トークン更新 API
    ---
    tags:
      - Authentication
    summary: 指定されたトークンの有効・無効を更新する
    description: 
      認証済みのユーザーが，自身の発行した長期トークンの状態 (`is_active`) を更新するための API．
      JWT による認証が必要であり，対象の `tokenid` が現在のユーザーのものである必要がある．
    security:
      - BearerAuth: []
    parameters:
      - name: tokenid
        in: path
        required: true
        schema:
          type: string
          pattern: "^[0-9a-f]{64}$"
        description: "更新する対象のトークンID"
      - name: body
        in: body
        required: true
        schema:
          required:
            - is_active
          type: object
          properties:
            is_active:
              type: boolean
              example: true
              description: "トークンの有効状態（True: 有効, False: 無効）"
    responses:
      200:
        description: トークン更新成功
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
        description: 不正なリクエスト（JWT エラー、JSON スキーマエラー、または更新失敗）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Jwt Error | Json Schema Error | Failed"
    """
    try:
        is_webui_jwt = get_jwt()["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    user_id = get_jwt_identity()
    try:
        request_data = pvalid.UpdateTokenRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    if ptoken.update_token(token_id=tokenid, is_active=request_data.is_active, user_id=user_id):
        return jsonify({"code": 200, "message": "success"}), 200
    else:
        return jsonify({"code": 400, "message": "Failed"}), 400

@app.route("/token", methods=["GET"])
@jwt_required()
def get_token_list():
    """
    長期トークン一覧取得 API
    ---
    tags:
      - Authentication
    summary: ユーザーの発行した長期トークンの一覧を取得する
    description: 
      認証済みのユーザーが，自身の発行した長期トークンの一覧を取得するAPI．
      JWTによる認証が必要であり，WebUIのJWTである必要がある．
    security:
      - BearerAuth: []
    responses:
      200:
        description: トークン一覧の取得成功
        schema:
          type: object
          properties:
            tokens:
              type: array
              items:
                type: object
                properties:
                  token_id:
                    type: string
                    pattern: "^[0-9a-f]{64}$"
                    description: "トークンの一意な識別子"
                  user_id:
                    type: string
                    pattern: "^[A-Za-z0-9_-]{21}$"
                    description: "このトークンを所有するユーザーのID"
                  created_at:
                    type: string
                    example: "Thu, 16 Jan 2025 09:07:38 GMT"
                    description: "トークンの作成日時 (MongoDBのフォーマット)"
                  expired_at:
                    type: string
                    example: "Wed, 16 Apr 2025 09:07:38 GMT"
                    description: "トークンの有効期限 (MongoDBのフォーマット)"
                  scopes:
                    type: array
                    items:
                      type: string
                    example: ["all"]
                    description: "このトークンで許可されるスコープの一覧"
                  is_active:
                    type: boolean
                    example: true
                    description: "トークンの有効状態（True: 有効, False: 無効）"
                  description:
                    type: string
                    example: "testtoken"
                    description: "トークンの補足情報（オプション）"
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
              example: "Jwt Error"
    """
    try:
        is_webui_jwt = get_jwt()["WebUI"]
        if not is_webui_jwt:
            raise Exception("Jwt Error")
    except:
        return jsonify({"code": 400, "message": "Jwt Error"}), 400
    user_id = get_jwt_identity()
    token_list = ptoken.get_token_list(user_id=user_id)
    return jsonify({"tokens": token_list})

@app.route("/jwt/sensors/writejwt", methods=["POST"])
@require_json
def get_sensor_write_jwt(data_json):
    """
    センサーデータ書き込み用 JWT 発行 API
    ---
    tags:
      - Authentication
    summary: センサーデータの書き込み権限を持つJWTを発行する
    description: 
      認証済みのユーザーが，センサーデータの書き込み権限を持つJWTを発行するAPI．
      提供された長期トークン (`token`) のスコープを検証し，適切な権限がある場合にJWTを発行する．
      `start_time` から `end_time` の範囲でのアクセスが可能になる．
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
            - token
            - participant_id
            - start_time
            - end_time
          properties:
            user_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "リクエストを行うユーザーのID"
            token:
              type: string
              pattern: "^[A-Za-z0-9_-]{43,44}$"
              description: "ユーザーの認証用長期トークン"
            participant_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "センサーデータを書き込む対象の参加者ID"
            start_time:
              type: string
              format: date-time
              example: "2025-01-01T00:00:00Z"
              description: "JWT の有効開始時間"
            end_time:
              type: string
              format: date-time
              example: "2025-01-01T01:00:00Z"
              description: "JWT の有効終了時間"
    responses:
      200:
        description: JWT 発行成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "success"
            jwt:
              type: string
              example: "eyJhbGciOiJIUz..."
              description: "発行された JWT"
      400:
        description: 不正なリクエスト（JSON スキーマエラー または 無効なトークン）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Json Schema Error | Token is invalid"
      401:
        description: 認証エラー（権限なし）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Not Found experimenter or participant id | This token do not have permission for writing sensor data"
    """
    try:
        request_data = pvalid.GetJwtSensorsRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    if ptoken.check_token(raw_token=request_data.token, user_id=request_data.user_id):
        scopes = ptoken.get_token_scope(raw_token=request_data.token)
        # TODO: 仮実装．実際はちゃんと認可範囲をsensors writeがあるとか確認が必要
        if "all" in scopes:
            try:
                psql.get_participant_from_id(id=request_data.participant_id)
                psql.get_user_from_id(id=request_data.user_id)
                additional_claim = {
                    "participant_id": request_data.participant_id,
                    "start_time": request_data.start_time.isoformat(),
                    "end_time": request_data.end_time.isoformat(),
                    "jwt_role": "sensor_write"
                    }
                if request_data.experiment_id:
                    additional_claim["experiment"] = request_data.experiment_id
                jwt = create_access_token(
                    identity=request_data.user_id,
                    expires_delta=timedelta(minutes=10),
                    additional_claims=additional_claim
                    )
                return jsonify({"code": 200, "message": "success", "jwt": jwt})
            except:
                return jsonify({"code": 401, "message": "Not Found experimenter or participant id"}), 401
        else:
            return jsonify({"code": 401, "message": "This token do not have permission for writing sensor data"}), 401
    else:
        return jsonify({"code": 400, "message": "Token is invalid"}), 400

@app.route("/jwt/sensors/readjwt", methods=["POST"])
@require_json
def get_sensor_read_jwt(data_json):
    """
    センサーデータ読み取り用 JWT 発行 API
    ---
    tags:
      - Authentication
    summary: センサーデータの読み取り権限を持つ JWT を発行する
    description: 
      認証済みのユーザーが，センサーデータの読み取り権限を持つ JWT を発行する API．
      提供された長期トークン (`token`) のスコープを検証し，適切な権限がある場合に JWT を発行する．
      `start_time` から `end_time` の範囲でのアクセスが可能になる．
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
            - token
            - participant_id
            - start_time
            - end_time
          properties:
            user_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "リクエストを行うユーザーのID"
            token:
              type: string
              pattern: "^[A-Za-z0-9_-]{43,44}$"
              description: "ユーザーの認証用長期トークン"
            participant_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "センサーデータを読み取る対象の参加者ID"
            start_time:
              type: string
              format: date-time
              example: "2025-01-01T00:00:00Z"
              description: "JWT の有効開始時間"
            end_time:
              type: string
              format: date-time
              example: "2025-01-01T01:00:00Z"
              description: "JWT の有効終了時間"
    responses:
      200:
        description: JWT 発行成功
        schema:
          type: object
          properties:
            jwt:
              type: string
              example: "eyJhbGciOiJIUz..."
              description: "発行された JWT"
      400:
        description: 不正なリクエスト（JSON スキーマエラー または 無効なトークン）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Json Schema Error | Token is invalid"
      401:
        description: 認証エラー（権限なし）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Not Found experimenter or participant id | This token do not have permission for reading sensor data"
    """
    try:
        request_data = pvalid.GetJwtSensorsRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    if ptoken.check_token(raw_token=request_data.token, user_id=request_data.user_id):
        scopes = ptoken.get_token_scope(raw_token=request_data.token)
        # TODO: 仮実装．実際はちゃんと認可範囲をsensors readがあるとか確認が必要
        if "all" in scopes:
            try:
                psql.get_participant_from_id(id=request_data.participant_id)
                psql.get_user_from_id(id=request_data.user_id)
                additional_claim = {
                    "participant_id": request_data.participant_id,
                    "start_time": request_data.start_time.isoformat(),
                    "end_time": request_data.end_time.isoformat(),
                    "jwt_role": "sensor_read"
                    }
                if request_data.experiment_id:
                    additional_claim["experiment"] = request_data.experiment_id
                jwt = create_access_token(
                    identity=request_data.user_id,
                    expires_delta=timedelta(minutes=10),
                    additional_claims=additional_claim
                    )
                return jsonify({"jwt": jwt})
            except:
                return jsonify({"code": 401, "message": "Not Found experimenter or participant id"}), 401
        else:
            return jsonify({"code": 401, "message": "This token do not have permission for reading sensor data"}), 401
    else:
        return jsonify({"code": 400, "message": "Token is invalid"}), 400

@app.route("/jwt/admin", methods=["POST"])
@require_json
def get_admin_jwt(data_json):
    """
    WebUI 管理 JWT 発行 API（長期トークン → admin）
    長期トークン（scope=all）を持つ admin ユーザーにのみ発行する．
    Google OAuth を使わない bio_console から実験レジストリ（experiment CRUD）等を操作するために使用．
    """
    try:
        user_id = data_json.get("user_id", "")
        token = data_json.get("token", "")
        if not (isinstance(user_id, str) and isinstance(token, str) and user_id and token):
            raise ValueError("invalid body")
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    if not ptoken.check_token(raw_token=token, user_id=user_id):
        return jsonify({"code": 400, "message": "Token is invalid"}), 400
    scopes = ptoken.get_token_scope(raw_token=token)
    if "all" not in scopes:
        return jsonify({"code": 401, "message": "This token do not have permission for admin operation"}), 401
    try:
        user = psql.get_user_from_id(id=user_id)
        if user.get("role") != "admin":
            return jsonify({"code": 401, "message": "User is not admin"}), 401
    except:
        return jsonify({"code": 401, "message": "Not Found user"}), 401
    jwt = create_access_token(
        identity=user_id,
        expires_delta=timedelta(minutes=10),
        additional_claims={"WebUI": True, "userRole": "admin"}
    )
    return jsonify({"jwt": jwt})

@app.route("/jwt/events", methods=["POST"])
@require_json
def get_events_jwt(data_json):
    """
    イベントデータ用 JWT 発行 API
    ---
    tags:
      - Authentication
    summary: イベントデータにアクセスするための JWT を発行する
    description: 
      認証済みのユーザーが，イベントデータの取得権限を持つ JWT を発行する API．
      提供された長期トークン (`token`) のスコープを検証し，適切な権限がある場合に JWT を発行する．
      `start_time` から `end_time` の範囲でのアクセスが可能になる．
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
            - token
            - participant_id
            - start_time
            - end_time
          properties:
            user_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "リクエストを行うユーザーのID"
            token:
              type: string
              pattern: "^[A-Za-z0-9_-]{43,44}$"
              description: "ユーザーの認証用長期トークン"
            participant_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "イベントデータを取得する対象の参加者ID"
            start_time:
              type: string
              format: date-time
              example: "2025-01-01T00:00:00Z"
              description: "JWT の有効開始時間"
            end_time:
              type: string
              format: date-time
              example: "2025-01-01T01:00:00Z"
              description: "JWT の有効終了時間"
    responses:
      200:
        description: JWT 発行成功
        schema:
          type: object
          properties:
            jwt:
              type: string
              example: "eyJhbGciOiJIUz..."
              description: "発行された JWT"
      400:
        description: 不正なリクエスト（JSON スキーマエラー または 無効なトークン）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Json Schema Error | Token is invalid"
      401:
        description: 認証エラー（権限なし）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Not Found experimenter or participant id | This token does not have permission for accessing event data"
    """
    try:
        request_data = pvalid.GetJwtEventsRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    if ptoken.check_token(raw_token=request_data.token, user_id=request_data.user_id):
        scopes = ptoken.get_token_scope(raw_token=request_data.token)
        # TODO: 仮実装．実際はちゃんと認可範囲をsensors readがあるとか確認が必要
        if "all" in scopes:
            try:
                psql.get_participant_from_id(id=request_data.participant_id)
                psql.get_user_from_id(id=request_data.user_id)
                additional_claim = {
                    "user_id": request_data.participant_id,
                    "start_time": request_data.start_time.isoformat(),
                    "end_time": request_data.end_time.isoformat(),
                    "jwt_role": "event"
                    }
                if request_data.experiment_id:
                    additional_claim["experiment"] = request_data.experiment_id
                jwt = create_access_token(
                    identity=request_data.user_id,
                    expires_delta=timedelta(minutes=10),
                    additional_claims=additional_claim
                    )
                return jsonify({"jwt": jwt})
            except:
                return jsonify({"code": 401, "message": "Not Found experimenter or participant id"}), 401
        else:
            return jsonify({"code": 401, "message": "This token do not have permission for accessing event data"}), 401
    else:
        return jsonify({"code": 400, "message": "Token is invalid"}), 400

@app.route("/jwt/service/sensors/readjwt", methods=["POST"])
@require_json
@jwt_required()
def get_sensor_read_jwt_by_service(data_json):
    """
    センサーデータ読み取り用 JWT 発行 API
    ---
    tags:
      - Authentication
    summary: センサーデータの読み取り権限を持つ JWT を発行する
    description: 
      認証済みのユーザーが，センサーデータの読み取り権限を持つ JWT を発行する API．
      WebService スコープを持つ JWT で利用可能．
      `start_time` から `end_time` の範囲でのアクセスが可能になる．
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
            - participant_id
            - start_time
            - end_time
          properties:
            user_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "リクエストを行うユーザーのID"
            participant_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "センサーデータを読み取る対象の参加者ID"
            start_time:
              type: string
              format: date-time
              example: "2025-01-01T00:00:00Z"
              description: "JWT の有効開始時間"
            end_time:
              type: string
              format: date-time
              example: "2025-01-01T01:00:00Z"
              description: "JWT の有効終了時間"
    responses:
      200:
        description: JWT 発行成功
        schema:
          type: object
          properties:
            jwt:
              type: string
              example: "eyJhbGciOiJIUz..."
              description: "発行された JWT"
      400:
        description: 不正なリクエスト（JSON スキーマエラー または 無効なトークン）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Json Schema Error | Invalid jwt"
      401:
        description: 認証エラー（権限なし）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Not Found experimenter or participant id"
    """
    try:
        request_data = pvalid.GetJwtServiceRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        jwt_user = get_jwt_identity()
        if jwt_user != request_data.user_id:
            raise Exception("not match user")
        add_claim = get_jwt()
        if add_claim["WebService"] != True:
            raise Exception("Not WebService JWT")
    except:
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        psql.get_user_from_id(id=request_data.user_id)
        psql.get_participant_from_id(id=request_data.participant_id)
        additional_claim = {
            "participant_id": request_data.participant_id,
            "start_time": request_data.start_time.isoformat(),
            "end_time": request_data.end_time.isoformat(),
            "jwt_role": "sensor_read"
            }
        if request_data.experiment_id:
            additional_claim["experiment"] = request_data.experiment_id
        jwt = create_access_token(
            identity=request_data.user_id,
            expires_delta=timedelta(minutes=10),
            additional_claims=additional_claim
            )
        return jsonify({"jwt": jwt})
    except:
        return jsonify({"code": 401, "message": "Not Found experimenter or participant id"}), 401

@app.route("/jwt/service/events", methods=["POST"])
@require_json
@jwt_required()
def get_event_jwt_by_service(data_json):
    """
    イベントデータ用 JWT 発行 API
    ---
    tags:
      - Authentication
    summary: イベントデータの権限を持つ JWT を発行する
    description: 
      認証済みのユーザーが，イベントデータの権限を持つ JWT を発行する API．
      WebService スコープを持つ JWT で利用可能．
      `start_time` から `end_time` の範囲でのアクセスが可能になる．
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
            - participant_id
            - start_time
            - end_time
          properties:
            user_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "リクエストを行うユーザーのID"
            participant_id:
              type: string
              pattern: "^[A-Za-z0-9_-]{21}$"
              description: "センサーデータを読み取る対象の参加者ID"
            start_time:
              type: string
              format: date-time
              example: "2025-01-01T00:00:00Z"
              description: "JWT の有効開始時間"
            end_time:
              type: string
              format: date-time
              example: "2025-01-01T01:00:00Z"
              description: "JWT の有効終了時間"
    responses:
      200:
        description: JWT 発行成功
        schema:
          type: object
          properties:
            jwt:
              type: string
              example: "eyJhbGciOiJIUz..."
              description: "発行された JWT"
      400:
        description: 不正なリクエスト（JSON スキーマエラー または 無効なトークン）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "Json Schema Error | Invalid jwt"
      401:
        description: 認証エラー（権限なし）
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 401
            message:
              type: string
              example: "Not Found experimenter or participant id"
    """
    try:
        request_data = pvalid.GetJwtServiceRequestBody.model_validate(data_json)
    except:
        return jsonify({"code": 400, "message": "Json Schema Error"}), 400
    try:
        jwt_user = get_jwt_identity()
        if jwt_user != request_data.user_id:
            raise Exception("not match user")
        add_claim = get_jwt()
        if add_claim["WebService"] != True:
            raise Exception("Not WebService JWT")
    except:
        return jsonify({"code": 400, "message": "Invalid jwt"}), 400
    try:
        psql.get_participant_from_id(id=request_data.participant_id)
        psql.get_user_from_id(id=request_data.user_id)
        additional_claim = {
            "user_id": request_data.participant_id,
            "start_time": request_data.start_time.isoformat(),
            "end_time": request_data.end_time.isoformat(),
            "jwt_role": "event"
            }
        if request_data.experiment_id:
            additional_claim["experiment"] = request_data.experiment_id
        jwt = create_access_token(
            identity=request_data.user_id,
            expires_delta=timedelta(minutes=10),
            additional_claims=additional_claim
            )
        return jsonify({"jwt": jwt})
    except:
        return jsonify({"code": 401, "message": "Not Found experimenter or participant id"}), 401
