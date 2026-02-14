from flask import Flask, render_template, request
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
STATIC_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

NORMAL_NIGHT_POWER = 200
COST_PER_KWH = 8


def calculate_ghost_load(df):
    ghost_energy = 0.0

    for _, row in df.iterrows():
        hour = row["hour"]
        power = row["power"]

        if hour >= 22 or hour <= 6:
            if power > NORMAL_NIGHT_POWER:
                ghost_energy += (power - NORMAL_NIGHT_POWER) / 1000

    annual_energy = ghost_energy * 365
    annual_cost = annual_energy * COST_PER_KWH

    return ghost_energy, annual_energy, annual_cost


@app.route("/")
def upload_page():
    return render_template("upload_files.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    file = request.files["file"]

    if not file or file.filename == "":
        return "No file uploaded"

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)

    # Read CSV
    df = pd.read_csv(filepath)
    df.columns = df.columns.str.lower().str.strip()

    # Detect timestamp column
    time_col = None
    for col in df.columns:
        if "time" in col or "date" in col:
            time_col = col
            break

    # Detect power/value column
    power_col = None
    for col in df.columns:
        if "power" in col or "value" in col or "energy" in col:
            power_col = col
            break

    if time_col is None or power_col is None:
        return "CSV must contain a timestamp/date column and a power/value column"

    # Convert timestamp
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col, power_col])

    # Standardize column names
    df.rename(columns={time_col: "timestamp", power_col: "power"}, inplace=True)

    # Time features
    df["hour"] = df["timestamp"].dt.hour
    df["day"] = df["timestamp"].dt.date

    # Daily stats
    daily_stats = df.groupby("day")["power"].sum().reset_index()

    # Heatmap data
    heatmap_data = df.pivot_table(
        index="day",
        columns="hour",
        values="power",
        aggfunc="mean"
    )

    plt.figure(figsize=(12, 6))
    sns.heatmap(heatmap_data, cmap="inferno")
    plt.title("Energy Consumption Heatmap")
    plt.xlabel("Hour")
    plt.ylabel("Day")

    heatmap_path = os.path.join(STATIC_FOLDER, "heatmap.png")
    plt.tight_layout()
    plt.savefig(heatmap_path)
    plt.close()

    # Ghost load calculation
    daily, annual, cost = calculate_ghost_load(df)

    return render_template(
        "result.html",
        daily=daily,
        annual=annual,
        cost=cost,
        stats=daily_stats.to_dict(orient="records"),
        heatmap="heatmap.png"
    )


if __name__ == "__main__":
    app.run(debug=True)
