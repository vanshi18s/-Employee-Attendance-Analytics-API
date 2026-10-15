
# Employee Attendance & Analytics API

A robust backend service for managing employee attendance, punch-ins/outs, and generating business analytics using FastAPI and MongoDB.

## How to Run

1. **Set up a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

```

2. **Install dependencies:**
```bash
pip install -r requirements.txt

```


3. **Configure Environment Variables:**
Ensure you have a MongoDB instance running (version 6.0+). You can set up a local instance using Docker: `docker run -p 27017:27017 mongo:7`.
Set your connection variables in a `.env` file or export them:
```bash
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="attendance_db"

```


4. **Start the application:**
```bash
uvicorn app.main:app --port 8000 --reload

```


The API will be available at `http://localhost:8000`. You can test the endpoints via the interactive Swagger UI at `http://localhost:8000/docs`.

---

## Important Note on Code Changes

While reviewing the starter `app/main.py`, I carefully examined all existing helper functions and endpoint logic. I haven't added or modified the things I looked at but ultimately decided did not need changing. Any code that was already correct and efficient was left intact to avoid unnecessary modifications.

---

## Design Decisions & Problem Solving

Here are the key design choices and logic implementations for the challenging aspects of the API:

### 1. Indexes

* **`employees.emp_code` (Unique):** Created to prevent duplicate employee codes from being registered.
* **`employees.department` and `employees.joined_on` (Compound):** Created to efficiently serve the analytics queries that filter employees by department and their joining date.
* **`attendance_logs.emp_code` and `attendance_logs.date` (Unique Compound):** Created to guarantee that each employee has exactly one attendance record per calendar day.
* *Note:* I deliberately avoided adding any extra, unused indexes because they consume unnecessary storage space and slow down write operations.

### 2. Punch-In Race Condition

The unique compound index on `emp_code` and `date` ensures race conditions are handled at the database level. If two identical punch-in requests arrive at the exact same instant:

1. Request A and Request B both check for an existing record and find none.
2. Both attempt to insert the new attendance record simultaneously.
3. MongoDB's unique index strictly allows only one request to insert successfully.
4. The other request is rejected by MongoDB with a `DuplicateKeyError`.
5. The FastAPI code catches this specific error and gracefully returns an `HTTP 409 Conflict` rather than duplicating data or crashing.

### 3. Ties in the Leaderboard

When two employees are tied on late minutes at the `limit` cutoff, the leaderboard orders the tied rows by `emp_code` (ascending) as required by the problem statement. Because both have an equal late minute value, they share the same rank. I calculated the dense rank first in the aggregation pipeline, and only applied the `limit` afterwards to ensure no legitimately tied employees were arbitrarily dropped from the returned leaderboard.

### 4. Department Headcount

To ensure employees with zero attendance logs are still counted in the department summary, the aggregation pipeline starts querying from the `employees` collection rather than the `attendance_logs` collection. It then uses a `$lookup` to join their attendance records for the selected month. As a result, employees are always included in the initial dataset. Even if their retrieved attendance data is empty, they still correctly contribute to the total department headcount.

### 5. Scaling to 100x Data

If this API had to serve 100x the data volume, my primary focus would be on database optimization and infrastructure scaling before introducing new tech. After ensuring MongoDB is fully optimized (sharding, heavier index tuning), I would consider:

* Adding **Redis** as a caching layer to quickly serve frequently accessed, heavy analytics endpoints.
* Utilizing **precomputed summary tables** (materialized views) generated nightly via cron jobs for the heavy historical statistics.
* Upgrading to more advanced Python data-processing libraries or utilizing cloud infrastructure/GPU resources for extremely large, concurrent analytics computations.

```

```
