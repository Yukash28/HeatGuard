import requests

latitude = 12.9716
longitude = 77.5946

url = "https://api.open-meteo.com/v1/forecast"

params = {
    "latitude": latitude,
    "longitude": longitude,
    "hourly": [
        "temperature_2m",
        "relative_humidity_2m",
        "wind_speed_10m",
        "shortwave_radiation"
    ],
    "forecast_days": 5,
    "timezone": "Asia/Kolkata"
}

response = requests.get(url, params=params)

data = response.json()

hourly = data["hourly"]

for i in range(10):
    print(
        hourly["time"][i],
        "| Temp:", hourly["temperature_2m"][i],
        "| Humidity:", hourly["relative_humidity_2m"][i],
        "| Wind:", hourly["wind_speed_10m"][i],
        "| Radiation:", hourly["shortwave_radiation"][i]
    )