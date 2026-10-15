# DECISIONS.md 

1. **Indexes.** Which indexes did you create, and which query or guarantee does each one serve? Which one did you consider and reject?
2. **Punch-in race.** Two identical punch-in requests arrive at the same instant. Walk through exactly what happens in your code.
3. **Ties.** Two employees are tied on late minutes at the cutoff of `limit`. What does your leaderboard return, and why?
4. **Headcount.** How does your department summary make sure employees with zero logs are counted?
5. **One thing you would change** if this had to serve 100x the data.

#Answers:
1. **Answer 1:** I created a unique index on employees.emp_code to prevent duplicate employee codes, a compound index on employees.department and employees.joined_on to help filter employees by department and joining date and a unique compound index on attendance_logs.emp_code and attendance_logs.date to ensure that each employee has only one attendance record per day, did not add any extra indexes because they consume storage and slow down writes.
2. **Answer 2:** The unique compound index on emp_code and date allows only one insert to succeed; the other raises a duplicate-key error. The code should handle that error and return an appropriate conflict response rather than create a duplicate record.
   Imagine two identical punch-in requests arrive at exactly the same time:
  i) Request A checks for an existing record and finds none.
  ii) Request B also checks and finds none.
  iii) Both try to insert the attendance record.
  iv) MongoDB's unique index allows only one request to insert successfully.
  v) The other request is rejected with a duplicate-key error, which your code catches and returns as HTTP 409 Conflict.
4. **Answer 3:** Tied rows are ordered by emp_code as mentioned in the requirements of this project's problem statement as both have equal value, that is why we ranked first and then applied limit to prevent dropping of employee.
5. **Answer 4:** The department summary starts with employees and then uses $lookup to find their attendance records for the selected month. This means employees are included even if they have no attendance logs. Their attendance data is empty, but they still contribute to the department headcount.
6. **Answer 5:** For handling 100x more data, I would consider adding Redis for faster retrieval of frequently accessed results, along with suitable mappings and precomputed tables for commonly requested statistics. I could also use advanced Python libraries for better data processing and optimization. For extremely large workloads, cloud infrastructure and GPU resources could be used wherever required. MongoDB itself is capable of handling large datasets, so I would first optimize the existing database and scale the infrastructure before introducing additional technologies.
