import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import pickle

# ---------------- DISASTER ENCODING ----------------
disaster_map = {
    "Earthquake": 1,
    "Flood": 2,
    "Cyclone": 3,
    "Fire": 4,
    "Tsunami": 5,
    "Landslide": 6,
    "Drought": 7,
    "Avalanche": 8,
    "Heatwave": 9,
    "Tornado": 10,
    "Wildfire": 11,
    "Blizzard": 12,
    "Volcanic Eruption": 13,
    "Pandemic": 14
}

reverse_map = {v: k for k, v in disaster_map.items()}


# ---------------- TRAIN MODEL ----------------
def train_model():

    df = pd.read_csv("training_dataset.csv")

    # Convert disaster names to numbers
    df["disaster_type"] = df["disaster_type"].map(disaster_map)
    df["next_recommended"] = df["next_recommended"].map(disaster_map)

    # Input Features
    X = df[["disaster_type", "exercise_number", "percentage"]]

    # Output
    y = df["next_recommended"]

    model = DecisionTreeClassifier()
    model.fit(X, y)

    pickle.dump(model, open("model.pkl", "wb"))

    print("✅ AI Model trained successfully")


# ---------------- PREDICT ----------------
def predict_next(disaster, exercise, score_percent):

    model = pickle.load(open("model.pkl", "rb"))

    disaster_num = disaster_map.get(disaster)

    prediction = model.predict([[disaster_num, exercise, score_percent]])

    return reverse_map[prediction[0]]


# ---------------- RUN TRAINING ----------------
if __name__ == "__main__":
    train_model()