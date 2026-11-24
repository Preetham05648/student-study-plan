import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Sample student study data
data = {
    "difficulty": [2, 5, 8, 3, 9, 6, 7, 4],
    "preparation": [8, 5, 2, 7, 1, 4, 3, 6],
    "days_left": [10, 5, 2, 8, 1, 4, 3, 7],
    "study_hours": [2, 3, 5, 2, 6, 4, 5, 3],
    "priority": [
        "Low", "Medium", "High", "Low",
        "High", "Medium", "High", "Medium"
    ]
}

df = pd.DataFrame(data)

# Input features
X = df[[
    "difficulty",
    "preparation",
    "days_left",
    "study_hours"
]]

# Target
y = df["priority"]

# Train Random Forest model
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

model.fit(X, y)


def recommend_priority(difficulty, preparation, days_left, study_hours):

    student_data = pd.DataFrame([{
        "difficulty": difficulty,
        "preparation": preparation,
        "days_left": days_left,
        "study_hours": study_hours
    }])

    prediction = model.predict(student_data)

    return prediction[0]


# Test the model
result = recommend_priority(9, 2, 2, 5)

print("Recommended Study Priority:", result)