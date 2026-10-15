```markdown
# Employee Attendance & Analytics API

This repository contains the backend for the HROne Employee Attendance & Analytics system, built with FastAPI and MongoDB. It handles employee attendance tracking, manual regularization (corrections), and complex aggregations for HR analytics.

## Included Documentation
* `app/main.py`: Contains the complete application code, including all endpoints, helpers, and MongoDB aggregation pipelines.
* `REVIEW.md`: Details the defects found in the starter code and the specific fixes applied.
* `DECISIONS.md`: Explains the architectural decisions, index choices, concurrency handling, and scaling considerations.
* `requirements.txt`: Lists all required Python dependencies.

## How to Run

1. **Set up the virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   pip install -r requirements.txt

```

2. **Configure Environment Variables:**
Create a `.env` file in the root directory and set your MongoDB connection details. (Alternatively, you can copy from a `.env.example` if you have one):
```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=attendance_db

```


*Note: If testing locally, you can spin up a MongoDB container using:* `docker run -p 27017:27017 mongo:7`
3. **(Optional) Seed the Database:**
If you have the sample data script provided in the candidate kit, run it to populate initial data:
```bash
python sample_seed.py

```


4. **Start the FastAPI Server:**
```bash
uvicorn app.main:app --port 8000 --reload

```


The API will be available at `http://localhost:8000`. You can explore the interactive API documentation (Swagger UI) at `http://localhost:8000/docs`.

## Developer Notes

* **Starter Code Review:** I thoroughly reviewed the provided starter template. While I fixed the bugs explicitly documented in `REVIEW.md` (such as concurrency issues and improper pagination), I also examined several other helper functions and existing structures but ultimately decided not to change them. They successfully met the strict problem statement constraints without the need for unnecessary over-engineering.
* **Indexes & Concurrency:** Required indexes (like the unique compound index on `emp_code` and `date`) are created idempotently at application startup to ensure race-safe punch-ins and fast analytical queries.

```

```
