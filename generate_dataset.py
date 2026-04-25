import pandas as pd
import random

roles = ["Doctor", "Nurse", "Admin"]
times = ["Working", "Night"]
devices = ["Trusted", "Unknown"]
locations = ["Hospital", "Outside"]
sensitivity = ["Low", "High"]
violations = ["Yes", "No"]

data = []
rows = 1000

for _ in range(rows):
    role = random.choice(roles)
    time = random.choice(times)
    device = random.choice(devices)
    location = random.choice(locations)
    sens = random.choice(sensitivity)
    freq = random.randint(1, 15)
    viol = random.choice(violations)

    if (time == "Night" and device == "Unknown" and sens == "High") or viol == "Yes":
        risk = "High"
    elif (time == "Night" and location == "Outside") or device == "Unknown":
        risk = "Medium"
    else:
        risk = "Low"

    data.append([role, time, device, location, sens, freq, viol, risk])

df = pd.DataFrame(data, columns=[
    "Role",
    "Access_Time",
    "Device_Type",
    "Location",
    "Data_Sensitivity",
    "Access_Frequency",
    "Previous_Violations",
    "Risk_Level"
])

df.to_csv("dataset.csv", index=False)

print("Dataset Created Successfully!")
