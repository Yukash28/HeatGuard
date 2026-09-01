#  HeatGuard

### SIH 2026 — Problem Statement 26083

**Extreme Heatwave Early Warning & Human Thermal Stress Index**

> **Theme:** Disaster Management
> **Organization:** Ministry of Earth Sciences (MoES) / NCMRWF
> **Pilot City:** Bengaluru

---

##  What are we building?

HeatGuard is an **impact-based heatwave early warning system** that predicts **how dangerous heat will be for people**, rather than relying only on temperature.

It combines weather, thermal stress, population vulnerability, and health data to produce **localized heat-risk predictions** and recommend actions.

### Core idea

```text
Weather Forecast
       ↓
Temperature + Humidity + Wind + Radiation
       ↓
   Thermal Stress
  (WBGT / UTCI / HI)
       ↓
Population Vulnerability
       ↓
   Health Risk
       ↓
Ward-Level Alerts & Actions
```

---

##  Key Features

* 🌡️ **Thermal Stress:** WBGT, UTCI, Heat Index
* 🗺️ **Ward-Level Risk Map:** Bengaluru
* 📅 **3–5 Day Forecast:** Predict upcoming risk
* 👥 **Vulnerability Analysis:** Elderly, outdoor workers, population density
* 🏥 **Health Risk:** Hospitalization / mortality risk where data permits
* 🚨 **Action Recommendations:** Cooling centers, work-hour changes, alerts
* 📡 **API:** Future SMS/WhatsApp/admin integrations

---

## 🛠️ Tech Stack

**Backend:** Python / FastAPI
**ML:** Pandas, NumPy, Scikit-learn
**Frontend:** React / Next.js
**Maps:** Leaflet / Mapbox + GeoJSON
**Database:** PostgreSQL / Supabase
**Weather:** Open-Meteo

---

## 📁 Project Structure

```text
heatguard/
├── thermal/       # Thermal stress calculations
├── data/          # Weather, demographic & health data
├── backend/       # APIs
├── ml/            # Prediction models
├── frontend/      # Dashboard
└── README.md
```

---

## 🚀 MVP

Our hackathon MVP should demonstrate:

1. Real Bengaluru weather data
2. WBGT / Heat Index calculation
3. Heat-risk scoring
4. Bengaluru ward-level GIS map
5. 3–5 day risk forecast
6. Recommended actions

---

## 💡 What makes it different?

We're **not building another weather app.**

> **Weather App:**
> *"Tomorrow will be 35°C."*

> **HeatGuard:**
> *"Ward 42 has HIGH heat-health risk tomorrow. Outdoor exposure should be reduced between 12–4 PM."*

### Our goal:

**Move from *“What will the weather be?”* → *“What will the weather do?”***

---

## 📌 Current Progress

* ✅ Bengaluru selected as pilot city
* ✅ Project structure created
* ✅ Python environment configured
* ✅ Open-Meteo API connected
* ✅ Temperature, humidity, wind & radiation retrieved
* 🔄 **Next: Build the Thermal Stress Engine**

---

## 👥 Team Focus

**Build → Test → Integrate → Demo**

Don't overcomplicate the MVP.
**A working, scientifically defensible prototype > a huge unfinished system.**
