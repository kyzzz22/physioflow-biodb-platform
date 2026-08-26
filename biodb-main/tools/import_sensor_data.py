#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "PyYAML>=6.0,<7",
# ]
# ///
"""Import one EEG/MyBeat session into BioDB through its public APIs.

This is a deliberately local, one-off importer.  It never accesses the
database directly and it keeps its resume state beside the raw input data.
"""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import json
import os
import re
import stat
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time as clock_time, timedelta
from itertools import islice
from pathlib import Path
from statistics import median
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import yaml


EEG = "eeg"
MYBEAT = "mybeat"
SOURCE_ORDER = (EEG, MYBEAT)
CHUNK_SIZES = {EEG: 4096, MYBEAT: 1024}
JWT_REFRESH_SECONDS = 8 * 60
MYBEAT_MAX_CLOCK_RESIDUAL_SECONDS = 2.0
VERIFY_ATTEMPTS = 6
VERIFY_RETRY_SECONDS = 2


class ImportError(RuntimeError):
    """A problem that should be shown to the operator without a traceback."""


class ApiError(ImportError):
    """A non-successful response from BioDB."""


@dataclass(frozen=True)
class ImportConfig:
    base_url: str
    participant_id: str
    experimenter_id: str
    timezone: ZoneInfo
    long_token: str
    sources: dict[str, Path]


@dataclass(frozen=True)
class SourceProfile:
    name: str
    path: Path
    sha256: str
    rows: int
    fields: tuple[str, ...]
    start_time: datetime
    end_time: datetime
    mybeat_phase_seconds: float | None = None
    mybeat_residual_seconds: tuple[float, float] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import the s135 EEG and MyBeat CSV files into BioDB."
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="path to import.yaml (must not be readable by group or others)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="write data; without this option the command only performs a dry run",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="import at most this many records from each source (for a pilot run)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="do not read back the first newly written chunk of each source",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")
    return args


def require_private_file(path: Path) -> None:
    if not path.is_file():
        raise ImportError(f"configuration file does not exist: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ImportError(
            f"configuration file must be private (run: chmod 600 {path})"
        )


def load_config(path: Path) -> ImportConfig:
    require_private_file(path)
    try:
        config_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ImportError(f"cannot parse YAML configuration: {exc}") from exc

    if not isinstance(config_data, dict):
        raise ImportError("configuration must be a YAML mapping")

    required = ("participant_id", "experimenter_id", "long_token", "sources")
    missing = [key for key in required if not config_data.get(key)]
    if missing:
        raise ImportError(f"configuration is missing: {', '.join(missing)}")

    source_data = config_data["sources"]
    if not isinstance(source_data, dict) or set(source_data) != set(SOURCE_ORDER):
        raise ImportError("sources must contain exactly eeg and mybeat")

    try:
        timezone = ZoneInfo(str(config_data.get("timezone", "Asia/Tokyo")))
    except Exception as exc:
        raise ImportError("timezone must be a valid IANA timezone name") from exc

    source_paths: dict[str, Path] = {}
    for source in SOURCE_ORDER:
        source_path = path.parent / str(source_data[source])
        if not source_path.is_file():
            raise ImportError(f"{source} CSV does not exist: {source_path}")
        source_paths[source] = source_path

    base_url = str(config_data.get("api_base_url", "http://127.0.0.1:5002")).rstrip(
        "/"
    )
    if not base_url.startswith(("http://", "https://")):
        raise ImportError("api_base_url must start with http:// or https://")

    return ImportConfig(
        base_url=base_url,
        participant_id=str(config_data["participant_id"]),
        experimenter_id=str(config_data["experimenter_id"]),
        timezone=timezone,
        long_token=str(config_data["long_token"]),
        sources=source_paths,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalise_field_name(source: str, raw_name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", raw_name.lower()).strip("_")
    if not cleaned:
        raise ImportError(f"cannot make a field name from {raw_name!r}")
    return f"{source}_{cleaned}"


def value_as_number(raw_value: str, *, field: str, row_number: int) -> int | float | None:
    value = raw_value.strip()
    if value in ("", "-"):
        return None
    try:
        if re.fullmatch(r"[+-]?\d+", value):
            return int(value)
        return float(value)
    except ValueError as exc:
        raise ImportError(
            f"non-numeric value for {field!r} at CSV row {row_number}: {raw_value!r}"
        ) from exc


def localise_naive(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone)
    return value.replace(tzinfo=timezone)


def parse_eeg_timestamp(value: str, timezone: ZoneInfo) -> datetime:
    try:
        return localise_naive(datetime.fromisoformat(value.strip()), timezone)
    except ValueError as exc:
        raise ImportError(f"invalid EEG timestamp: {value!r}") from exc


def parse_clock(value: str) -> clock_time:
    try:
        return datetime.strptime(value.strip(), "%H:%M:%S").time()
    except ValueError as exc:
        raise ImportError(f"invalid MyBeat clock value: {value!r}") from exc


def mybeat_layout(path: Path) -> tuple[date, list[str]]:
    try:
        with path.open("r", encoding="cp932", newline="") as input_file:
            reader = csv.reader(input_file)
            metadata = list(islice(reader, 5))
            header = next(reader)
    except (OSError, UnicodeError, StopIteration) as exc:
        raise ImportError(f"cannot read MyBeat CSV: {path}") from exc

    if len(metadata) < 4 or len(metadata[3]) < 2 or metadata[3][0] != "Start":
        raise ImportError("MyBeat CSV does not have the expected Start metadata row")
    if not header or header[0] != "time" or "RRI" not in header:
        raise ImportError("MyBeat CSV does not have the expected time and RRI columns")
    try:
        session_date = datetime.strptime(metadata[3][1], "%Y/%m/%d").date()
    except ValueError as exc:
        raise ImportError(f"invalid MyBeat Start date: {metadata[3][1]!r}") from exc
    return session_date, header


def profile_eeg(path: Path, timezone: ZoneInfo) -> SourceProfile:
    first_time: datetime | None = None
    last_time: datetime | None = None
    previous_time: datetime | None = None
    rows = 0

    try:
        with path.open("r", encoding="ascii", newline="") as input_file:
            reader = csv.DictReader(input_file)
            raw_fields = reader.fieldnames or []
            if "timestamp" not in raw_fields:
                raise ImportError("EEG CSV does not have a timestamp column")
            fields = tuple(
                normalise_field_name(EEG, field)
                for field in raw_fields
                if field != "timestamp"
            )
            if len(fields) != len(set(fields)):
                raise ImportError("EEG CSV field names are not unique after normalisation")

            for row in reader:
                rows += 1
                timestamp = parse_eeg_timestamp(row["timestamp"], timezone)
                if previous_time is not None and timestamp <= previous_time:
                    raise ImportError("EEG timestamps must be strictly increasing")
                first_time = first_time or timestamp
                last_time = timestamp
                previous_time = timestamp
    except OSError as exc:
        raise ImportError(f"cannot read EEG CSV: {path}") from exc

    if rows == 0 or first_time is None or last_time is None:
        raise ImportError("EEG CSV has no data rows")
    return SourceProfile(
        name=EEG,
        path=path,
        sha256=sha256_file(path),
        rows=rows,
        fields=fields,
        start_time=first_time,
        end_time=last_time,
    )


def profile_mybeat(path: Path, timezone: ZoneInfo) -> SourceProfile:
    session_date, header = mybeat_layout(path)
    rri_index = header.index("RRI")
    fields = tuple(normalise_field_name(MYBEAT, field) for field in header[1:])
    if len(fields) != len(set(fields)):
        raise ImportError("MyBeat CSV field names are not unique after normalisation")

    rows = 0
    cumulative_seconds = 0.0
    first_clock: datetime | None = None
    previous_clock: clock_time | None = None
    day_offset = 0
    phase_candidates: list[float] = []

    try:
        with path.open("r", encoding="cp932", newline="") as input_file:
            reader = csv.reader(input_file)
            list(islice(reader, 5))
            next(reader)
            for csv_row_number, row in enumerate(reader, start=7):
                if len(row) != len(header):
                    raise ImportError(
                        f"MyBeat CSV row {csv_row_number} has {len(row)} columns; "
                        f"expected {len(header)}"
                    )
                clock = parse_clock(row[0])
                if previous_clock is not None and clock < previous_clock:
                    day_offset += 1
                observed = datetime.combine(
                    session_date + timedelta(days=day_offset), clock, tzinfo=timezone
                )
                rri = value_as_number(row[rri_index], field="RRI", row_number=csv_row_number)
                if rri is None or rri <= 0:
                    raise ImportError(f"invalid RRI at MyBeat CSV row {csv_row_number}")

                if first_clock is None:
                    first_clock = observed
                else:
                    cumulative_seconds += float(rri) / 1000.0
                observed_elapsed = (observed - first_clock).total_seconds()
                # The CSV clock is only second-precision.  Its centre is used to
                # estimate the unknown initial phase of the cumulative RRI clock.
                phase_candidates.append(observed_elapsed + 0.5 - cumulative_seconds)
                previous_clock = clock
                rows += 1
    except (OSError, UnicodeError) as exc:
        raise ImportError(f"cannot read MyBeat CSV: {path}") from exc

    if rows == 0 or first_clock is None:
        raise ImportError("MyBeat CSV has no data rows")

    phase = median(phase_candidates)
    residuals = [candidate - phase for candidate in phase_candidates]
    residual_range = (min(residuals), max(residuals))
    if max(abs(value) for value in residual_range) > MYBEAT_MAX_CLOCK_RESIDUAL_SECONDS:
        raise ImportError(
            "MyBeat RRI timestamps differ from the CSV clock by more than "
            f"{MYBEAT_MAX_CLOCK_RESIDUAL_SECONDS:g} seconds"
        )

    return SourceProfile(
        name=MYBEAT,
        path=path,
        sha256=sha256_file(path),
        rows=rows,
        fields=fields,
        start_time=first_clock + timedelta(seconds=phase),
        end_time=first_clock + timedelta(seconds=phase + cumulative_seconds),
        mybeat_phase_seconds=phase,
        mybeat_residual_seconds=residual_range,
    )


def profile_sources(config: ImportConfig) -> dict[str, SourceProfile]:
    return {
        EEG: profile_eeg(config.sources[EEG], config.timezone),
        MYBEAT: profile_mybeat(config.sources[MYBEAT], config.timezone),
    }


def iter_eeg_records(profile: SourceProfile, timezone: ZoneInfo) -> Iterator[tuple[datetime, dict[str, int | float | None]]]:
    with profile.path.open("r", encoding="ascii", newline="") as input_file:
        reader = csv.DictReader(input_file)
        raw_fields = reader.fieldnames or []
        for csv_row_number, row in enumerate(reader, start=2):
            timestamp = parse_eeg_timestamp(row["timestamp"], timezone)
            values = {
                normalise_field_name(EEG, field): value_as_number(
                    row[field], field=field, row_number=csv_row_number
                )
                for field in raw_fields
                if field != "timestamp"
            }
            yield timestamp, values


def iter_mybeat_records(profile: SourceProfile, timezone: ZoneInfo) -> Iterator[tuple[datetime, dict[str, int | float | None]]]:
    if profile.mybeat_phase_seconds is None:
        raise AssertionError("MyBeat profile does not have a clock phase")
    session_date, header = mybeat_layout(profile.path)
    rri_index = header.index("RRI")
    first_clock: datetime | None = None
    previous_clock: clock_time | None = None
    day_offset = 0
    cumulative_seconds = 0.0

    with profile.path.open("r", encoding="cp932", newline="") as input_file:
        reader = csv.reader(input_file)
        list(islice(reader, 5))
        next(reader)
        for csv_row_number, row in enumerate(reader, start=7):
            clock = parse_clock(row[0])
            if previous_clock is not None and clock < previous_clock:
                day_offset += 1
            observed = datetime.combine(
                session_date + timedelta(days=day_offset), clock, tzinfo=timezone
            )
            rri = value_as_number(row[rri_index], field="RRI", row_number=csv_row_number)
            if rri is None or rri <= 0:
                raise ImportError(f"invalid RRI at MyBeat CSV row {csv_row_number}")
            if first_clock is None:
                first_clock = observed
            else:
                cumulative_seconds += float(rri) / 1000.0

            values = {
                normalise_field_name(MYBEAT, field): value_as_number(
                    raw_value, field=field, row_number=csv_row_number
                )
                for field, raw_value in zip(header[1:], row[1:], strict=True)
            }
            timestamp = first_clock + timedelta(
                seconds=profile.mybeat_phase_seconds + cumulative_seconds
            )
            yield timestamp, values
            previous_clock = clock


def iter_source_records(profile: SourceProfile, timezone: ZoneInfo) -> Iterator[tuple[datetime, dict[str, int | float | None]]]:
    if profile.name == EEG:
        return iter_eeg_records(profile, timezone)
    if profile.name == MYBEAT:
        return iter_mybeat_records(profile, timezone)
    raise AssertionError(f"unknown source: {profile.name}")


def iter_batches(
    records: Iterator[tuple[datetime, dict[str, int | float | None]]],
    *,
    skip: int,
    limit: int,
    batch_size: int,
) -> Iterator[tuple[int, list[tuple[datetime, dict[str, int | float | None]]]]]:
    for _ in range(skip):
        try:
            next(records)
        except StopIteration as exc:
            raise ImportError("import state exceeds the number of source records") from exc

    offset = skip
    remaining = limit - skip
    while remaining > 0:
        batch = list(islice(records, min(batch_size, remaining)))
        if not batch:
            break
        yield offset, batch
        offset += len(batch)
        remaining -= len(batch)


def api_time(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


def encode_sensor_container(
    batch: list[tuple[datetime, dict[str, int | float | None]]], fields: tuple[str, ...]
) -> dict[str, str]:
    data: dict[str, list[Any]] = {"time": []}
    data.update({field: [] for field in fields})
    for timestamp, values in batch:
        data["time"].append(api_time(timestamp))
        for field in fields:
            data[field].append(values[field])

    raw_json = json.dumps(data, separators=(",", ":"), allow_nan=False).encode("utf-8")
    compressed = gzip.compress(raw_json, mtime=0)
    return {
        "format": "json",
        "compression": "gzip",
        "data": base64.b64encode(compressed).decode("ascii"),
    }


def decode_sensor_container(container: dict[str, Any]) -> dict[str, Any]:
    if container.get("format") != "json" or container.get("compression") != "gzip":
        raise ApiError("sensor read API returned an unexpected data format")
    try:
        compressed = base64.b64decode(container["data"])
        decoded = gzip.decompress(compressed)
        data = json.loads(decoded.decode("utf-8"))
    except (KeyError, ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError("cannot decode sensor read API response") from exc
    if not isinstance(data, dict):
        raise ApiError("sensor read API did not return an object")
    return data


def post_json(
    base_url: str, path: str, payload: dict[str, Any], *, authorization: str | None = None
) -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    request = Request(f"{base_url}{path}", data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=120) as response:
            decoded = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip().replace("\n", " ")
        raise ApiError(f"{path} returned HTTP {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise ApiError(f"cannot reach {path}: {exc.reason}") from exc

    try:
        result = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ApiError(f"{path} returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise ApiError(f"{path} returned an unexpected JSON value")
    return result


class SensorJwtIssuer:
    def __init__(self, config: ImportConfig, start_time: datetime, end_time: datetime):
        self.config = config
        self.start_time = start_time
        self.end_time = end_time
        self.write_jwt: str | None = None
        self.write_jwt_created_at = 0.0

    def _issue(self, permission: str) -> str:
        response = post_json(
            self.config.base_url,
            f"/auth/jwt/sensors/{permission}jwt",
            {
                "user_id": self.config.experimenter_id,
                "token": self.config.long_token,
                "participant_id": self.config.participant_id,
                "start_time": api_time(self.start_time),
                "end_time": api_time(self.end_time),
            },
        )
        jwt = response.get("jwt")
        if not isinstance(jwt, str) or not jwt:
            raise ApiError(f"sensor {permission} JWT was not issued")
        return jwt

    def get_write_jwt(self) -> str:
        now = time.monotonic()
        if self.write_jwt is None or now - self.write_jwt_created_at >= JWT_REFRESH_SECONDS:
            self.write_jwt = self._issue("write")
            self.write_jwt_created_at = now
        return self.write_jwt

    def get_read_jwt(self) -> str:
        return self._issue("read")


def state_path_for(config_path: Path) -> Path:
    return config_path.parent / ".import-state.json"


def new_state(config: ImportConfig) -> dict[str, Any]:
    return {
        "version": 1,
        "participant_id": config.participant_id,
        "experimenter_id": config.experimenter_id,
        "timezone": config.timezone.key,
        "sources": {},
    }


def load_state(path: Path, config: ImportConfig, profiles: dict[str, SourceProfile]) -> dict[str, Any]:
    if not path.exists():
        return new_state(config)
    try:
        state_data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImportError(f"cannot read import state: {path}") from exc
    if not isinstance(state_data, dict) or state_data.get("version") != 1:
        raise ImportError("unsupported import state format")

    for key, expected in (
        ("participant_id", config.participant_id),
        ("experimenter_id", config.experimenter_id),
        ("timezone", config.timezone.key),
    ):
        if state_data.get(key) != expected:
            raise ImportError(f"import state has a different {key}")

    source_state = state_data.get("sources")
    if not isinstance(source_state, dict):
        raise ImportError("import state has invalid sources")
    for source, profile in profiles.items():
        previous = source_state.get(source)
        if previous is not None and previous.get("sha256") != profile.sha256:
            raise ImportError(f"{source} CSV changed after an import started")
    return state_data


def save_state(path: Path, state_data: dict[str, Any]) -> None:
    temporary_path = path.with_name(f"{path.name}.tmp")
    encoded = json.dumps(state_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary_path.write_text(encoded, encoding="utf-8")
    os.chmod(temporary_path, 0o600)
    temporary_path.replace(path)
    os.chmod(path, 0o600)


def source_state(state_data: dict[str, Any], profile: SourceProfile) -> dict[str, Any]:
    sources = state_data["sources"]
    state = sources.get(profile.name)
    if state is None:
        state = {"sha256": profile.sha256, "records_imported": 0, "chunks": []}
        sources[profile.name] = state
    if state.get("sha256") != profile.sha256:
        raise ImportError(f"{profile.name} CSV changed after an import started")
    imported = state.get("records_imported")
    if not isinstance(imported, int) or imported < 0 or imported > profile.rows:
        raise ImportError(f"invalid {profile.name} import state")
    return state


def verify_batch(
    config: ImportConfig,
    jwt_issuer: SensorJwtIssuer,
    profile: SourceProfile,
    batch: list[tuple[datetime, dict[str, int | float | None]]],
) -> None:
    authorization = f"Bearer {jwt_issuer.get_read_jwt()}"
    last_error = ""
    for attempt in range(1, VERIFY_ATTEMPTS + 1):
        response = post_json(
            config.base_url,
            "/sensor/data/read",
            {
                "format": "json",
                "compression": "gzip",
                "rows": list(profile.fields),
                "start_time": api_time(batch[0][0]),
                "end_time": api_time(batch[-1][0]),
            },
            authorization=authorization,
        )
        data = decode_sensor_container(response)
        returned_times = data.get("time")
        if isinstance(returned_times, list) and len(returned_times) == len(batch):
            missing_fields = [field for field in profile.fields if field not in data]
            if not missing_fields:
                print(f"  verified {profile.name}: {len(batch)} rows read back")
                return
            last_error = f"missing fields {', '.join(missing_fields)}"
        else:
            actual_rows = len(returned_times) if isinstance(returned_times, list) else "invalid"
            last_error = f"expected {len(batch)} timestamps, got {actual_rows}"
        if attempt < VERIFY_ATTEMPTS:
            time.sleep(VERIFY_RETRY_SECONDS)
    raise ImportError(f"{profile.name} read-back failed: {last_error}")


def print_profile(profile: SourceProfile) -> None:
    print(f"{profile.name}: {profile.rows} rows")
    print(f"  input: {profile.path}")
    print(f"  time: {api_time(profile.start_time)} to {api_time(profile.end_time)}")
    print(f"  fields: {', '.join(profile.fields)}")
    if profile.mybeat_phase_seconds is not None and profile.mybeat_residual_seconds is not None:
        low, high = profile.mybeat_residual_seconds
        print(
            "  MyBeat RRI reconstruction: "
            f"initial phase {profile.mybeat_phase_seconds:.3f}s, "
            f"clock residual {low:.3f}s to {high:.3f}s"
        )


def import_source(
    config: ImportConfig,
    profile: SourceProfile,
    state_data: dict[str, Any],
    state_path: Path,
    jwt_issuer: SensorJwtIssuer,
    *,
    limit: int | None,
    execute: bool,
    verify: bool,
) -> None:
    target_records = min(profile.rows, limit) if limit is not None else profile.rows
    state = source_state(state_data, profile)
    already_imported = state["records_imported"]
    if already_imported >= target_records:
        print(f"{profile.name}: first {target_records} rows are already recorded in import state")
        return

    if not execute:
        print(
            f"{profile.name}: dry run — would write {target_records - already_imported} rows "
            f"in chunks of {CHUNK_SIZES[profile.name]}"
        )
        return

    first_written_batch: list[tuple[datetime, dict[str, int | float | None]]] | None = None
    records = iter_source_records(profile, config.timezone)
    for offset, batch in iter_batches(
        records,
        skip=already_imported,
        limit=target_records,
        batch_size=CHUNK_SIZES[profile.name],
    ):
        container = encode_sensor_container(batch, profile.fields)
        response = post_json(
            config.base_url,
            "/sensor/data/write",
            container,
            authorization=f"Bearer {jwt_issuer.get_write_jwt()}",
        )
        if response.get("code") != 200:
            raise ApiError(f"sensor write did not succeed for {profile.name} at row {offset}")

        state["records_imported"] = offset + len(batch)
        state["chunks"].append(
            {
                "start_record": offset,
                "rows": len(batch),
                "start_time": api_time(batch[0][0]),
                "end_time": api_time(batch[-1][0]),
                "payload_sha256": hashlib.sha256(
                    container["data"].encode("ascii")
                ).hexdigest(),
            }
        )
        save_state(state_path, state_data)
        print(f"  wrote {profile.name} rows {offset} to {offset + len(batch) - 1}")
        if first_written_batch is None:
            first_written_batch = batch

    if verify and first_written_batch is not None:
        verify_batch(config, jwt_issuer, profile, first_written_batch)


def main() -> int:
    args = parse_args()
    config = load_config(args.config.resolve())
    profiles = profile_sources(config)
    for source in SOURCE_ORDER:
        print_profile(profiles[source])

    if not args.execute:
        print("dry run only — pass --execute to write to BioDB")
        for source in SOURCE_ORDER:
            target_records = min(profiles[source].rows, args.limit) if args.limit else profiles[source].rows
            print(
                f"{source}: would write {target_records} rows in "
                f"chunks of {CHUNK_SIZES[source]}"
            )
        return 0

    session_start = min(profile.start_time for profile in profiles.values())
    session_end = max(profile.end_time for profile in profiles.values())
    state_path = state_path_for(args.config.resolve())
    state_data = load_state(state_path, config, profiles)
    jwt_issuer = SensorJwtIssuer(config, session_start, session_end)
    for source in SOURCE_ORDER:
        import_source(
            config,
            profiles[source],
            state_data,
            state_path,
            jwt_issuer,
            limit=args.limit,
            execute=True,
            verify=not args.no_verify,
        )
    print("import completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
