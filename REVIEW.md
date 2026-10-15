# REVIEW.md

List every defect you found in the starter `app/main.py` (helpers and endpoints). For each one:

| # | Where (function / line) | What is wrong | How you'd notice it (test, input, or symptom) | How you fixed it |
|---|---|---|---|---|
| 1 | def compute_late_minutes (line 36-37)| The final late minutes calculation is done based on minutes and seconds are not considered, which gives wrong answer. | Found the bug by testing cases in Swagger UI|Converted 10 mins to 600 sec and checked if elapsed_seconds>600, this way I added 10 mins late to the employees who took 10min +some extra seconds but less than 11 mins. |
| 2 | def compute_work_hours (line 46-57) | Truncation of microseconds was not done, there was no value error for punch out before punch in and simple round() was used instead of half round up as mentioned in PS. | Found the value error bug by test case and rest all I matched with the rules mentioned in PS and corrected. | Removed microseconds as mentioned in R1, proper error rasing was added and corrected the rounded half up calculations |
| 3 | def compute_overtime (line 64-65) | Function was not following Rule R3 | I noticed it by checking edge cases by testing in UI | I added the if-else statement for minutes>=30 only then add the overtime otherwise 0. | 

Also note anything you looked at and decided was **not** a defect, and why.
