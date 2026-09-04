import requests
from heat_index import calculate_heat_index

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
    temp = hourly["temperature_2m"][i]
    humidity = hourly["relative_humidity_2m"][i]

    heat_index = calculate_heat_index(temp, humidity)

    print(
        hourly["time"][i],
        "| Temp:", temp,
        "| Humidity:", humidity,
        "| Wind:", hourly["wind_speed_10m"][i],
        "| Radiation:", hourly["shortwave_radiation"][i],
        "| Heat Index:", heat_index
    )