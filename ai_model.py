import pandas as pd
from sklearn.tree import DecisionTreeClassifier
import pickle

# ---------------- DISASTER ENCODING ----------------
disaster_map = {
    "Earthquake": 1,
    "Flood": 2,
    "Cyclone": 3,
    "Fire": 4
}

reverse_map = {v: k for k, v in disaster_map.items()}


# ---------------- TRAIN MODEL ----------------
def train_model():

    # Load dataset
    df = pd.read_csv("training_dataset.csv")

    # Convert disaster names to numbers
    df["disaster_type"] = df["disaster_type"].map(disaster_map)
    df["next_recommended"] = df["next_recommended"].map(disaster_map)

    # Features (Input)
    X = df[["disaster_type", "exercise_number", "percentage"]]

    # Target (Output)
    y = df["next_recommended"]

    # Train model
    model = DecisionTreeClassifier()
    model.fit(X, y)

    # Save model
    pickle.dump(model, open("model.pkl", "wb"))

    print("✅ AI Model trained successfully")


# ---------------- PREDICT ----------------
def predict_next(disaster, exercise, score_percent):

    model = pickle.load(open("model.pkl", "rb"))

    disaster_num = disaster_map[disaster]

    prediction = model.predict([[disaster_num, exercise, score_percent]])

    return reverse_map[prediction[0]]


# ✅ IMPORTANT — RUN TRAINING
if __name__ == "__main__":
    train_model()
