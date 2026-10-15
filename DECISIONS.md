# DECISIONS.md  (about 150-200 words in total - plain language, your own words)

1. **Indexes.** Which indexes did you create, and which query or guarantee does each one serve? Which one did you consider and reject?
2. **Punch-in race.** Two identical punch-in requests arrive at the same instant. Walk through exactly what happens in your code.
3. **Ties.** Two employees are tied on late minutes at the cutoff of `limit`. What does your leaderboard return, and why?
4. **Headcount.** How does your department summary make sure employees with zero logs are counted?
5. **One thing you would change** if this had to serve 100x the data.

1. **Answer 1:**
2. **Answer 2:**
3. **Answer 3:** Tied rows are ordered by emp_code as mentioned in the requirements of this project's problem statement as both have equal value, that is why we ranked first and then applied limit to prevent dropping of employee.
4. **Answer 4:**
5. **Answer 5:**
