"""
Employee Attendance & Analytics API - STARTER

Run:  uvicorn app.main:app --port 8000
Env:  MONGO_URI, MONGO_DB (a local .env is loaded for convenience)

This file was written quickly by a colleague who has left the company. The happy path
works, but nobody has reviewed it. Read PROBLEM_STATEMENT.docx for what is expected of you,
openapi.yaml for the contract and DATA_MODEL.md for what is stored in MongoDB.
"""
import os
import re
from datetime import datetime, timedelta, timezone, date
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query 
from pydantic import BaseModel
from pymongo import MongoClient, ReturnDocument
from decimal import Decimal, ROUND_HALF_UP

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
db = client[os.getenv("MONGO_DB", "attendance_db")]

IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def compute_late_minutes(punch_in: datetime, shift_start: str) -> int:
    h, m = map(int, shift_start.split(":"))
    start = punch_in.replace(hour=h, minute=m, second=0, microsecond=0)
    elapsed_seconds = int((punch_in - start).total_seconds())
    if elapsed_seconds > 10 * 60:
        return elapsed_seconds // 60

    return 0



def compute_work_hours(punch_in: datetime, punch_out: datetime) -> float:
    punch_in = punch_in.replace(microsecond=0)
    punch_out = punch_out.replace(microsecond=0)

    if punch_out < punch_in:
        raise ValueError("Punch-out cannot be before punch-in")

    seconds = (punch_out - punch_in).total_seconds()
    hours = Decimal(str(seconds)) / Decimal("3600")

    return float(
        hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )



def compute_overtime(punch_out: datetime, shift_end: str, date_str: str) -> int:
    h, m = map(int, shift_end.split(":"))
    end = datetime.fromisoformat(date_str).replace(hour=h, minute=m, tzinfo=IST)
    minutes=int((punch_out - end).total_seconds() // 60)
    return minutes if minutes >= 30 else 0


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class EmployeeIn(BaseModel):
    emp_code: str
    name: str
    email: str
    department: str
    shift_start: str = "09:30"
    shift_end: str = "18:30"
    joined_on: str


class PunchInIn(BaseModel):
    emp_code: str
    punched_at: Optional[int] = None
    status: str = "PRESENT"


# --------------------------------------------------------------------------- #
# Endpoints provided
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    try:
        db.command("hello")
        return {"status": "ok"}
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable"
        )


from pymongo.errors import DuplicateKeyError

db.employees.create_index("emp_code", unique=True)


@app.post("/employees", status_code=201)
def create_employee(body: EmployeeIn):
    if db.employees.find_one({"emp_code": body.emp_code}):
        raise HTTPException(409, "emp_code already exists")

    doc = body.model_dump()
    doc["created_at"] = datetime.now()

    try:
        db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "emp_code already exists")

    doc.pop("_id", None)
    return doc


@app.get("/employees")
def list_employees(department: Optional[str] = None, page: int = 1, page_size: int = 20):
    q = {}
    if department:
        q["department"] = department

    skip = (page - 1) * page_size  
    total = db.employees.count_documents(q)  

    items = list(
        db.employees.find(q, {"_id": 0})
        .sort("emp_code", 1) 
        .skip(skip)
        .limit(page_size))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchInIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if emp is None:
        raise HTTPException(404, "employee not found")

    ts = datetime.fromtimestamp(body.punched_at / 1000) if body.punched_at else datetime.now()
    d = ts.date().isoformat()

    shift_start = emp["shift_start"]
    if emp["shift_end"] <= shift_start and ts.strftime("%H:%M") < emp["shift_end"]:
        d = (ts.date() - timedelta(days=1)).isoformat()

    if db.attendance_logs.find_one({"emp_code": body.emp_code, "date": d}):
        raise HTTPException(409, "already punched in for this date")

    doc = {
        "emp_code": body.emp_code,
        "date": d,
        "status": body.status,
        "punch_in": ts,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": compute_late_minutes(ts, emp["shift_start"]),
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }

    try:
        res = db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "already punched in for this date")

    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    return doc


from fastapi import Query

@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = {}
    if emp_code:
        q["emp_code"] = emp_code
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
    if status:
        q["status"] = status

    total = db.attendance_logs.count_documents(q)

    page_docs = list(
        db.attendance_logs.find(q, {"_id": 0})
        .sort("date", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "items": page_docs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

# Employee Out Model:
class PunchOutRequest(BaseModel):
    emp_code: str
    punched_at: Optional[int] = None


class RegularizeIn(BaseModel):
    reason: str
    regularized_by: str
    status: Optional[str] = None
    punch_in: Optional[int] = None
    punch_out: Optional[int] = None


@app.post("/attendance/punch-out")
def punch_out(body: PunchOutRequest):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, "Employee not found")

    value = body.punched_at
    if value is None:
        punched_at = datetime.now(timezone.utc).replace(
            microsecond=0, tzinfo=None
        )
    else:
        if type(value) is not int or not 100000000000 <= value <= 4102444800000:
            raise HTTPException(422, "Invalid epoch milliseconds")
        punched_at = datetime.fromtimestamp(
            value / 1000, timezone.utc
        ).replace(microsecond=0, tzinfo=None)

    record = db.attendance_logs.find_one(
        {
            "emp_code": body.emp_code,
            "punch_in": {"$lte": punched_at}
        },
        sort=[("punch_in", -1)]
    )

    if not record:
        raise HTTPException(404, "No punch-in found")

    if record.get("punch_out") is not None:
        raise HTTPException(409, "Already punched out")

    if punched_at <= record["punch_in"] or (
        punched_at - record["punch_in"]
    ).total_seconds() > 86400:
        raise HTTPException(422, "Invalid punch-out time")

    seconds = (punched_at - record["punch_in"]).total_seconds()
    hours = float(
        (Decimal(str(seconds)) / Decimal("3600")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )

    shift_end = datetime.strptime(
        record["date"] + " " + emp["shift_end"],
        "%Y-%m-%d %H:%M"
    ).replace(tzinfo=IST)

    if emp["shift_end"] <= emp["shift_start"]:
        shift_end += timedelta(days=1)

    shift_end_utc = shift_end.astimezone(timezone.utc).replace(tzinfo=None)
    overtime = int((punched_at - shift_end_utc).total_seconds() // 60)
    overtime = overtime if overtime >= 30 else 0

    updated = db.attendance_logs.find_one_and_update(
        {"_id": record["_id"], "punch_out": None},
        {"$set": {
            "punch_out": punched_at,
            "work_hours": hours,
            "overtime_minutes": overtime,
            "half_day": hours < 4.50
        }},
        return_document=ReturnDocument.AFTER
    )

    if not updated:
        raise HTTPException(409, "Already punched out")

    updated.pop("_id", None)

    for field in ("punch_in", "punch_out"):
        value = updated.get(field)
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            updated[field] = int(value.timestamp() * 1000)

    return updated

@app.patch("/attendance/{emp_code}/{date}")
def regularize_attendance(emp_code: str, date: str, body: RegularizeIn):
    try:
        attendance_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "Invalid date")

    if len(body.reason) < 5 or len(body.reason) > 200:
        raise HTTPException(422, "Reason must be 5-200 characters")

    if not 1 <= len(body.regularized_by) <= 50:
        raise HTTPException(422, "Invalid regularized_by")

    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, "Employee not found")

    record = db.attendance_logs.find_one({
        "emp_code": emp_code,
        "date": date
    })
    if not record:
        raise HTTPException(404, "Attendance record not found")

    allowed_statuses = {"PRESENT", "WFH", "ON_DUTY", "ABSENT", "LEAVE"}
    status = body.status if body.status is not None else record["status"]

    if status not in allowed_statuses:
        raise HTTPException(422, "Invalid status")

    changes_requested = (
        "status" in body.model_fields_set
        or "punch_in" in body.model_fields_set
        or "punch_out" in body.model_fields_set
    )
    if not changes_requested:
        raise HTTPException(422, "No changes provided")

    punch_in = record.get("punch_in")
    punch_out = record.get("punch_out")

    if "punch_in" in body.model_fields_set:
        if body.punch_in is None:
            raise HTTPException(422, "punch_in cannot be null")
        if type(body.punch_in) is not int or not 100000000000 <= body.punch_in <= 4102444800000:
            raise HTTPException(422, "Invalid punch_in")
        punch_in = datetime.fromtimestamp(
            body.punch_in / 1000, timezone.utc
        ).replace(microsecond=0, tzinfo=None)

    if "punch_out" in body.model_fields_set:
        if body.punch_out is None:
            raise HTTPException(422, "punch_out cannot be null")
        if type(body.punch_out) is not int or not 100000000000 <= body.punch_out <= 4102444800000:
            raise HTTPException(422, "Invalid punch_out")
        punch_out = datetime.fromtimestamp(
            body.punch_out / 1000, timezone.utc
        ).replace(microsecond=0, tzinfo=None)

    if status in {"ABSENT", "LEAVE"}:
        if "punch_in" in body.model_fields_set or "punch_out" in body.model_fields_set:
            raise HTTPException(422, "Cannot supply punch times for ABSENT or LEAVE")
        punch_in = None
        punch_out = None
        late_minutes = 0
        work_hours = None
        overtime_minutes = 0
        half_day = False
    else:
        if punch_in is None:
            raise HTTPException(422, "Presence status requires punch_in")

        local_in = punch_in.replace(tzinfo=timezone.utc).astimezone(IST)
        if local_in.date() != attendance_date:
            raise HTTPException(422, "punch_in must be on the attendance date")
        if punch_out is not None:
            duration = (punch_out - punch_in).total_seconds()
            if duration <= 0 or duration > 86400:
                raise HTTPException(422, "Invalid punch_out time")

        shift_start_hour, shift_start_minute = map(
            int, emp["shift_start"].split(":")
        )
        shift_start = local_in.replace(
            hour=shift_start_hour,
            minute=shift_start_minute,
            second=0,
            microsecond=0
        )
        late_seconds = int((local_in - shift_start).total_seconds())
        late_minutes = late_seconds // 60 if late_seconds > 600 else 0

        if punch_out is None:
            work_hours = None
            overtime_minutes = 0
            half_day = False
        else:
            seconds = (punch_out - punch_in).total_seconds()
            work_hours = float(
                (Decimal(str(seconds)) / Decimal("3600")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            )

            shift_end = datetime.strptime(
                date + " " + emp["shift_end"], "%Y-%m-%d %H:%M"
            ).replace(tzinfo=IST)

            if emp["shift_end"] <= emp["shift_start"]:
                shift_end += timedelta(days=1)

            shift_end_utc = shift_end.astimezone(timezone.utc).replace(tzinfo=None)
            overtime_minutes = int(
                (punch_out - shift_end_utc).total_seconds() // 60
            )
            if overtime_minutes < 30:
                overtime_minutes = 0

            half_day = work_hours < 4.50

    final_values = {
        "status": status,
        "punch_in": punch_in,
        "punch_out": punch_out,
        "late_minutes": late_minutes,
        "work_hours": work_hours,
        "overtime_minutes": overtime_minutes,
        "half_day": half_day
    }

    changes = {}
    for field, new_value in final_values.items():
        old_value = record.get(field)
        if old_value != new_value:
            changes[field] = {"from": old_value, "to": new_value}

    if not changes:
        raise HTTPException(422, "No changes to apply")

    history_entry = {
        "at": datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None),
        "by": body.regularized_by,
        "reason": body.reason,
        "changes": changes
    }

    query = {"_id": record["_id"]}
    for field in ("status", "punch_in", "punch_out"):
        query[field] = record.get(field)

    updated = db.attendance_logs.find_one_and_update(
        query,
        {
            "$set": final_values,
            "$push": {"history": history_entry}
        },
        return_document=ReturnDocument.AFTER
    )

    if not updated:
        raise HTTPException(409, "Attendance record changed; retry")

    updated.pop("_id", None)
    for field in ("punch_in", "punch_out"):
        value = updated.get(field)
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            updated[field] = int(value.timestamp() * 1000)

    for entry in updated.get("history", []):
        value = entry.get("at")
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            entry["at"] = int(value.timestamp() * 1000)

        for field in ("punch_in", "punch_out"):
            if field in entry.get("changes", {}):
                for side in ("from", "to"):
                    value = entry["changes"][field].get(side)
                    if value is not None:
                        if value.tzinfo is None:
                            value = value.replace(tzinfo=timezone.utc)
                        entry["changes"][field][side] = int(value.timestamp() * 1000)

    return updated
@app.get("/admin/explain/{endpoint}")
def explain_endpoint(
    endpoint: str,
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    if endpoint != "attendance_list":
        raise HTTPException(
            422,
            "Only attendance_list is implemented here; analytics explain requires the actual analytics pipelines"
        )

    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(422, "Invalid pagination")

    query = {}

    if emp_code:
        query["emp_code"] = emp_code
    if status:
        query["status"] = status

    if date_from or date_to:
        date_filter = {}
        if date_from:
            try:
                datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(422, "Invalid date_from")
            date_filter["$gte"] = date_from
        if date_to:
            try:
                datetime.strptime(date_to, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(422, "Invalid date_to")
            date_filter["$lte"] = date_to
        query["date"] = date_filter

    result = db.command(
        "explain",
        {
            "find": "attendance_logs",
            "filter": query,
            "sort": {"date": -1},
            "skip": (page - 1) * page_size,
            "limit": page_size
        },
        verbosity="executionStats"
    )

    return {
        "endpoint": endpoint,
        "collection": "attendance_logs",
        "explain": result
    }


# MongoDB Full Aggregation Pipeline

def create_analytics_indexes():
    db.employees.create_index("emp_code", unique=True)
    db.employees.create_index([("department", 1), ("joined_on", 1)])
    db.attendance_logs.create_index(
        [("emp_code", 1), ("date", 1)],
        unique=True
    )


@app.on_event("startup")
def startup_analytics_indexes():
    create_analytics_indexes()

PRESENT_STATUSES = ["PRESENT", "WFH", "ON_DUTY"]


def get_month_dates(month: str):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(422, "month must be in YYYY-MM format")

    first_day = datetime.strptime(month, "%Y-%m").date()
    next_month = (
        first_day.replace(day=28) + timedelta(days=4)
    ).replace(day=1)

    return first_day.isoformat(), next_month.isoformat()


def round_half_up_expression(value, places=2):
    factor = 10 ** places
    return {
        "$divide": [
            {"$floor": {"$add": [{"$multiply": [value, factor]}, 0.5]}},
            factor
        ]
    }


@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly(
    emp_code: str,
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
):
    month_start, next_month = get_month_dates(month)

    pipeline = [
        {"$match": {"emp_code": emp_code}},
        {
            "$lookup": {
                "from": "attendance_logs",
                "let": {"code": "$emp_code"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$emp_code", "$$code"]},
                                    {"$gte": ["$date", month_start]},
                                    {"$lt": ["$date", next_month]}
                                ]
                            }
                        }
                    }
                ],
                "as": "logs"
            }
        },
        {
            "$set": {
                "joined_date": "$joined_on",
                "start_date": {
                    "$cond": [
                        {"$gt": ["$joined_on", month_start]},
                        "$joined_on",
                        month_start
                    ]
                }
            }
        },
        {
            "$set": {
                "working_days": {
                    "$cond": [
                        {"$gte": ["$start_date", next_month]},
                        0,
                        {
                            "$sum": {
                                "$map": {
                                    "input": {
                                        "$range": [
                                            0,
                                            {
                                                "$dateDiff": {
                                                    "startDate": {
                                                        "$dateFromString": {
                                                            "dateString": "$start_date"
                                                        }
                                                    },
                                                    "endDate": {
                                                        "$dateFromString": {
                                                            "dateString": next_month
                                                        }
                                                    },
                                                    "unit": "day"
                                                }
                                            }
                                        ]
                                    },
                                    "as": "day",
                                    "in": {
                                        "$cond": [
                                            {
                                                "$in": [
                                                    {
                                                        "$dayOfWeek": {
                                                            "$dateAdd": {
                                                                "startDate": {
                                                                    "$dateFromString": {
                                                                        "dateString": "$start_date"
                                                                    }
                                                                },
                                                                "unit": "day",
                                                                "amount": "$$day"
                                                            }
                                                        }
                                                    },
                                                    [2, 3, 4, 5, 6]
                                                ]
                                            },
                                            1,
                                            0
                                        ]
                                    }
                                }
                            }
                        }
                    ]
                },
                "present_days": {
                    "$sum": {
                        "$map": {
                            "input": {
                                "$filter": {
                                    "input": "$logs",
                                    "as": "log",
                                    "cond": {
                                        "$and": [
                                            {"$in": ["$$log.status", PRESENT_STATUSES]},
                                            {
                                                "$in": [
                                                    {
                                                        "$dayOfWeek": {
                                                            "$dateFromString": {
                                                                "dateString": "$$log.date"
                                                            }
                                                        }
                                                    },
                                                    [2, 3, 4, 5, 6]
                                                ]
                                            }
                                        ]
                                    }
                                }
                            },
                            "as": "log",
                            "in": {
                                "$cond": [
                                    {"$eq": [{"$ifNull": ["$$log.half_day", False]}, True]},
                                    0.5,
                                    1
                                ]
                            }
                        }
                    }
                },
                "leave_days": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "log",
                            "cond": {"$eq": ["$$log.status", "LEAVE"]}
                        }
                    }
                },
                "late_count": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "log",
                            "cond": {"$gt": [{"$ifNull": ["$$log.late_minutes", 0]}, 0]}
                        }
                    }
                },
                "total_late_minutes": {
                    "$sum": {
                        "$map": {
                            "input": "$logs",
                            "as": "log",
                            "in": {"$ifNull": ["$$log.late_minutes", 0]}
                        }
                    }
                },
                "total_overtime_minutes": {
                    "$sum": {
                        "$map": {
                            "input": "$logs",
                            "as": "log",
                            "in": {"$ifNull": ["$$log.overtime_minutes", 0]}
                        }
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "emp_code": 1,
                "month": {"$literal": month},
                "working_days": 1,
                "present_days": 1,
                "leave_days": 1,
                "late_count": 1,
                "total_late_minutes": 1,
                "total_overtime_minutes": 1,
                "attendance_pct": {
                    "$cond": [
                        {"$gt": ["$working_days", 0]},
                        round_half_up_expression(
                            {
                                "$multiply": [
                                    {"$divide": ["$present_days", "$working_days"]},
                                    100
                                ]
                            },
                            2
                        ),
                        None
                    ]
                }
            }
        }
    ]

    result = list(db.employees.aggregate(pipeline))

    if not result:
        raise HTTPException(404, "Employee not found")

    return result[0]


@app.get("/analytics/departments/summary")
def department_summary(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    department: Optional[str] = None
):
    month_start, next_month = get_month_dates(month)
    last_day = (date.fromisoformat(next_month) - timedelta(days=1)).isoformat()

    employee_filter = {"joined_on": {"$lte": last_day}}
    if department is not None:
        employee_filter["department"] = department

    pipeline = [
        {"$match": employee_filter},
        {
            "$lookup": {
                "from": "attendance_logs",
                "let": {"code": "$emp_code"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$emp_code", "$$code"]},
                                    {"$gte": ["$date", month_start]},
                                    {"$lt": ["$date", next_month]}
                                ]
                            }
                        }
                    }
                ],
                "as": "logs"
            }
        },
        {
            "$set": {
                "present_days": {
                    "$sum": {
                        "$map": {
                            "input": {
                                "$filter": {
                                    "input": "$logs",
                                    "as": "log",
                                    "cond": {
                                        "$and": [
                                            {"$in": ["$$log.status", PRESENT_STATUSES]},
                                            {
                                                "$in": [
                                                    {
                                                        "$dayOfWeek": {
                                                            "$dateFromString": {
                                                                "dateString": "$$log.date"
                                                            }
                                                        }
                                                    },
                                                    [2, 3, 4, 5, 6]
                                                ]
                                            }
                                        ]
                                    }
                                }
                            },
                            "as": "log",
                            "in": {
                                "$cond": [
                                    {"$eq": [{"$ifNull": ["$$log.half_day", False]}, True]},
                                    0.5,
                                    1
                                ]
                            }
                        }
                    }
                },
                "late_count": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "log",
                            "cond": {"$gt": [{"$ifNull": ["$$log.late_minutes", 0]}, 0]}
                        }
                    }
                },
                "total_late_minutes": {
                    "$sum": {
                        "$map": {
                            "input": "$logs",
                            "as": "log",
                            "in": {"$ifNull": ["$$log.late_minutes", 0]}
                        }
                    }
                },
                "leave_count": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "log",
                            "cond": {"$eq": ["$$log.status", "LEAVE"]}
                        }
                    }
                },
                "on_duty_count": {
                    "$size": {
                        "$filter": {
                            "input": "$logs",
                            "as": "log",
                            "cond": {"$eq": ["$$log.status", "ON_DUTY"]}
                        }
                    }
                },
                "work_hours_logs": {
                    "$filter": {
                        "input": "$logs",
                        "as": "log",
                        "cond": {
                            "$and": [
                                {"$in": ["$$log.status", PRESENT_STATUSES]},
                                {"$ne": [{"$ifNull": ["$$log.work_hours", None]}, None]}
                            ]
                        }
                    }
                }
            }
        },
        {
            "$set": {
                "work_hours_sum": {
                    "$sum": {
                        "$map": {
                            "input": "$work_hours_logs",
                            "as": "log",
                            "in": "$$log.work_hours"
                        }
                    }
                },
                "work_hours_count": {"$size": "$work_hours_logs"}
            }
        },
        {
            "$group": {
                "_id": "$department",
                "headcount": {"$sum": 1},
                "present_days": {"$sum": "$present_days"},
                "late_count": {"$sum": "$late_count"},
                "total_late_minutes": {"$sum": "$total_late_minutes"},
                "leave_count": {"$sum": "$leave_count"},
                "on_duty_count": {"$sum": "$on_duty_count"},
                "work_hours_sum": {"$sum": "$work_hours_sum"},
                "work_hours_count": {"$sum": "$work_hours_count"}
            }
        },
        {
            "$project": {
                "_id": 0,
                "department": "$_id",
                "headcount": 1,
                "present_days": 1,
                "late_count": 1,
                "total_late_minutes": 1,
                "leave_count": 1,
                "on_duty_count": 1,
                "avg_work_hours": {
                    "$cond": [
                        {"$gt": ["$work_hours_count", 0]},
                        round_half_up_expression(
                            {"$divide": ["$work_hours_sum", "$work_hours_count"]},
                            2
                        ),
                        None
                    ]
                }
            }
        },
        {"$sort": {"department": 1}}
    ]

    items = list(db.employees.aggregate(pipeline))
    return {"month": month, "items": items}

@app.get("/analytics/leaderboard/late")
def late_leaderboard(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    limit: int = Query(10, ge=1, le=50),
    department: Optional[str] = None
):
    month_start, next_month = get_month_dates(month)

    pipeline = [
        {
            "$match": {
                "date": {"$gte": month_start, "$lt": next_month}
            }
        },
        {
            "$group": {
                "_id": "$emp_code",
                "total_late_minutes": {
                    "$sum": {"$ifNull": ["$late_minutes", 0]}
                },
                "late_count": {
                    "$sum": {
                        "$cond": [
                            {"$gt": [{"$ifNull": ["$late_minutes", 0]}, 0]},
                            1,
                            0
                        ]
                    }
                }
            }
        },
        {"$match": {"total_late_minutes": {"$gt": 0}}},
        {
            "$lookup": {
                "from": "employees",
                "localField": "_id",
                "foreignField": "emp_code",
                "as": "employee"
            }
        },
        {"$unwind": "$employee"}
    ]

    if department is not None:
        pipeline.append({"$match": {"employee.department": department}})

    pipeline.extend([
        {
            "$setWindowFields": {
                "sortBy": {"total_late_minutes": -1},
                "output": {"rank": {"$rank": {}}}
            }
        },
        {"$match": {"rank": {"$lte": limit}}},
        {"$sort": {"total_late_minutes": -1, "_id": 1}},
        {
            "$project": {
                "_id": 0,
                "rank": 1,
                "emp_code": "$_id",
                "name": "$employee.name",
                "department": "$employee.department",
                "total_late_minutes": 1,
                "late_count": 1
            }
        }
    ])

    items = list(db.attendance_logs.aggregate(pipeline))
    return {"month": month, "items": items}


    


    
# --------------------------------------------------------------------------- #
# TODO - Done! (Completed)
#   POST  /attendance/punch-out
#   PATCH /attendance/{emp_code}/{date}
#   GET   /analytics/employees/{emp_code}/monthly
#   GET   /analytics/departments/summary
#   GET   /analytics/leaderboard/late
#   GET   /analytics/departments/{department}/trend                    
