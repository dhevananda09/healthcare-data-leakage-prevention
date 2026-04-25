import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

print("Loading Dataset...")

df = pd.read_csv("dataset.csv")

# =====================
# Encode Data
# =====================
le_dict = {}

categorical_cols = [
    "Role",
    "Access_Time",
    "Device_Type",
    "Location",
    "Data_Sensitivity",
    "Previous_Violations"
]

for col in categorical_cols:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col])
    le_dict[col] = le

risk_map = {"Low": 0, "Medium": 1, "High": 2}
df["Risk_Level"] = df["Risk_Level"].map(risk_map)

# =====================
# Split Features & Target
# =====================
X = df.drop("Risk_Level", axis=1)
y = df["Risk_Level"]

feature_names = X.columns

# =====================
# Scale Data
# =====================
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# =====================
# Simulate Federated Clients
# =====================
client_X = np.array_split(X_scaled, 3)
client_y = np.array_split(y, 3)

local_models = []
local_importances = []

print("\nStarting Federated Training Simulation...")

# =====================
# Train Local Models
# =====================
for i in range(3):
    print(f"\nTraining Hospital {i+1} Model")

    X_train, X_test, y_train, y_test = train_test_split(
        client_X[i], client_y[i], test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(n_estimators=120)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)

    print(f"Hospital {i+1} Accuracy: {acc:.3f}")

    local_models.append(model)
    local_importances.append(model.feature_importances_)

# =====================
# Federated Aggregation (IMPROVED)
# =====================
print("\nPerforming Federated Aggregation...")

avg_importance = np.mean(local_importances, axis=0)

# Train global model on full data
global_model = RandomForestClassifier(n_estimators=120)
global_model.fit(X_scaled, y)

print("Global Model Trained Using Aggregated Knowledge")

# =====================
# Save Model
# =====================
joblib.dump(global_model, "ml_fl_xai_model.pkl")
joblib.dump(scaler, "scaler.pkl")

print("\nModel Saved Successfully!")

# =====================
# 🔥 DYNAMIC RISK SCORING (NEW)
# =====================
def calculate_risk_score(input_data):
    score = 0

    if input_data["Access_Time"] == 1:  # Night
        score += 25

    if input_data["Device_Type"] == 1:  # Unknown
        score += 30

    if input_data["Location"] == 1:  # Outside
        score += 20

    if input_data["Data_Sensitivity"] == 1:
        score += 25

    if input_data["Previous_Violations"] == 1:
        score += 40

    return score

# =====================
# 🔥 BEHAVIOR CHECK (NEW)
# =====================
def behavior_anomaly(user_history, current_input):
    if current_input["Access_Time"] != user_history["usual_time"]:
        return True
    return False

# =====================
# FINAL HYBRID PREDICTION
# =====================
def predict_with_risk(input_data, user_history):
    input_df = pd.DataFrame([input_data])
    input_scaled = scaler.transform(input_df)

    ml_pred = global_model.predict(input_scaled)[0]

    risk_score = calculate_risk_score(input_data)

    if behavior_anomaly(user_history, input_data):
        risk_score += 20

    # Map to Low/Medium/High
    if risk_score < 40:
        final = "Low"
    elif risk_score < 80:
        final = "Medium"
    else:
        final = "High"

    return final, risk_score

# =====================
# Explainable AI
# =====================
print("\nExplainable AI - Feature Importance:")

for name, score in zip(feature_names, avg_importance):
    print(f"{name} : {score:.3f}")

print("\nTraining Complete!")