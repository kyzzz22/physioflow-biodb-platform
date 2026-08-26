import base64
from datetime import datetime, date, timezone

from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr
from typing import Optional, List, Literal, Dict

class CreateTokenRequestBody(BaseModel):
    scopes: List[str]
    expiration_days: int = Field(ge=1,le=365)
    description: str = Field(default="", description="additional data")

class UpdateTokenRequestBody(BaseModel):
    is_active: bool

class GetJwtSensorsRequestBody(BaseModel):
    user_id: str
    token: str
    participant_id: str
    start_time: datetime
    end_time: datetime
    experiment_id: Optional[str] = Field(default=None, description="实验ID（可选）。若提供，写入/读取的时序数据将限定到该实验维度")

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class SensorDataWriteRequestBody(BaseModel):
    compression: Literal["gzip", "lz4", "brotli", "none"]
    format: Literal["json", "messagepack"]
    data: str = Field(..., description="Base64 encoded compressed data")

    @field_validator("data")
    def validate_base64(cls, value):
        try:
            base64.b64decode(value)
            return value
        except Exception:
            raise ValueError("Invalid Base64 encoded data")
        
class SensorDataReadRequestBody(BaseModel):
    compression: Literal["gzip", "lz4", "brotli", "none"]
    format: Literal["json", "messagepack"]
    rows: List[str]
    start_time: datetime
    end_time: datetime
    chunk_seconds: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=86400.0,
        description="读回分片大小（秒）。不提供时按时间窗自动计算（目标 ~500 个分片，5s~3600s 内）"
    )

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class SensorDataExportRequestBody(SensorDataReadRequestBody):
    include_events: bool = Field(default=True, description="是否包含事件数据（MongoDB events，按 participant+时间窗过滤）")
    include_experiment: bool = Field(default=True, description="是否包含实验元数据（experiments 注册表）")
    experiment_id: Optional[str] = Field(default=None, description="实验ID。不提供时使用 JWT 的 experiment claim（若有）")


class KMeansTrainRequestBody(BaseModel):
    rows: List[str] = Field(..., min_length=1, description="参与聚类的通道（读回 rows）")
    start_time: datetime
    end_time: datetime
    n_clusters: int = Field(default=3, ge=2, le=20, description="聚类数 k")
    max_iter: int = Field(default=100, ge=10, le=1000)
    random_state: int = Field(default=42)
    chunk_seconds: Optional[float] = Field(default=None, ge=1.0, le=86400.0)

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class LinearRegressionTrainRequestBody(BaseModel):
    rows: List[str] = Field(..., min_length=2, description="特征通道（读回 rows），最后一列作为目标变量 y")
    start_time: datetime
    end_time: datetime
    ridge_alpha: float = Field(default=0.0, ge=0.0, le=100.0, description="岭正则系数（0 表示普通最小二乘）")
    chunk_seconds: Optional[float] = Field(default=None, ge=1.0, le=86400.0)

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class PredictRequestBody(BaseModel):
    model_id: str = Field(..., min_length=1, description="已训练模型 ID（训练接口返回的 model_id）")
    rows: List[str] = Field(..., min_length=1, description="推理用通道（读回 rows），顺序/数量需与训练一致")
    start_time: datetime
    end_time: datetime
    chunk_seconds: Optional[float] = Field(default=None, ge=1.0, le=86400.0)

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class EventDataCreateRequestBody(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None
    user_id: str
    event: str
    description: Optional[str] = None
    details: Optional[Dict] = None
    experiment_id: Optional[str] = Field(default=None, description="实验ID（可选）。事件所属实验；若 JWT 带 experiment claim 则以 JWT 为准")

    @model_validator(mode="after")
    def validate_time(self):
        if self.start_time is not None and self.start_time.tzinfo is None:
            self.start_time = self.start_time.replace(tzinfo=timezone.utc)
        if self.end_time is not None and self.end_time.tzinfo is None:
            self.end_time = self.end_time.replace(tzinfo=timezone.utc)
        if self.end_time is None:
            self.end_time = self.start_time
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class PermissionsCreatePostBody(BaseModel):
    user_id: str
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class PermissionUpdatePostBody(BaseModel):
    status: Literal["approved", "rejected"]

class EventData(BaseModel):
    event_id: str
    user_id: str
    start_time: datetime
    end_time: datetime
    event: str
    description: Optional[str] = None
    details: Optional[Dict] = None
    experiment_id: Optional[str] = None
    created_by: str

    @model_validator(mode="after")
    def validate_time(self):
        if self.start_time is not None and self.start_time.tzinfo is None:
            self.start_time = self.start_time.replace(tzinfo=timezone.utc)
        if self.end_time is not None and self.end_time.tzinfo is None:
            self.end_time = self.end_time.replace(tzinfo=timezone.utc)
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class EventDateUpdatePostBody(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    event: Optional[str] = None
    description: Optional[str] = None
    details: Optional[Dict] = None
    experiment_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_time(self):
        if self.start_time is not None and self.start_time.tzinfo is None:
            self.start_time = self.start_time.replace(tzinfo=timezone.utc)
        if self.end_time is not None and self.end_time.tzinfo is None:
            self.end_time = self.end_time.replace(tzinfo=timezone.utc)
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class GetJwtEventsRequestBody(BaseModel):
    user_id: str
    token: str
    participant_id: str
    start_time: datetime
    end_time: datetime
    experiment_id: Optional[str] = Field(default=None, description="实验ID（可选）。事件 JWT 可限定到实验维度")

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class GetJwtServiceRequestBody(BaseModel):
    user_id: str
    participant_id: str
    start_time: datetime
    end_time: datetime
    experiment_id: Optional[str] = Field(default=None, description="实验ID（可选）。Service JWT 可限定到实验维度")

    @model_validator(mode="after")
    def validate_time(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self

class PostParticipantRequestBody(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(default=None, min_length=2, max_length=36)
    sex: Optional[int] = Field(default=None, ge=0, le=10)
    birthdate: Optional[date] = None

class PostParticipantDataRequestBody(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=36)
    sex: Optional[int] = Field(default=None, ge=0, le=10)
    birthdate: Optional[date] = None
    is_enable: Optional[bool] = None

class PostUserRequestBody(BaseModel):
    email: EmailStr
    role: Literal["normal"]

class ExperimentCreateRequestBody(BaseModel):
    experiment_id: Optional[str] = Field(default=None, description="实验ID（可选）。不提供时自动生成 UUID")
    name: str = Field(..., min_length=1, max_length=128, description="实验唯一名称（时序/事件写入时使用的 experiment 标签值）")
    label: Optional[str] = Field(default=None, description="实验可读标签")
    description: Optional[str] = Field(default=None, description="实验描述")
    dictionary: Optional[Dict] = Field(default=None, description="数据字典：通道名 → 定义（label/unit/type 等）")

class ExperimentUpdateRequestBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128, description="实验唯一名称")
    label: Optional[str] = None
    description: Optional[str] = None
    dictionary: Optional[Dict] = None

class ExperimentDictionaryUpdateRequestBody(BaseModel):
    dictionary: Dict = Field(..., description="数据字典：通道名 → 定义（label/unit/type 等）")