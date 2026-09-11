# HeatGuard

### SIH 2026 — Problem Statement 26083

**Extreme Heatwave Early Warning & Human Thermal Stress Index**

**Theme:** Disaster Management
**Organization:** Ministry of Earth Sciences (MoES) / NCMRWF
**Pilot City:** Bengaluru

---

## Overview

HeatGuard is an **impact-based heatwave early warning system** designed to assess the potential health impact of extreme heat conditions.

Instead of relying solely on temperature, the system combines weather variables, thermal stress indices, population vulnerability, and available health data to generate localized heat-risk predictions and actionable recommendations.

### System Flow

```text
Weather Forecast
       ↓
Temperature + Humidity + Wind + Radiation
       ↓
Thermal Stress
(WBGT / UTCI / Heat Index)
       ↓
Population Vulnerability
       ↓
Health Risk
       ↓
Ward-Level Alerts & Recommendations
```

---

## Key Features

* Thermal stress calculation using WBGT, UTCI, and Heat Index
* Ward-level heat-risk mapping for Bengaluru
* 3–5 day heat-risk forecasting
* Population vulnerability analysis
* Consideration of elderly populations, outdoor workers, and population density
* Health-risk estimation where relevant data is available
* Action recommendations such as cooling centers and outdoor work-hour adjustments
* API support for future SMS, WhatsApp, and administrative integrations

---

## Tech Stack

**Backend:** Python, FastAPI
**Machine Learning:** Pandas, NumPy, Scikit-learn
**Frontend:** React / Next.js
**Maps:** Leaflet / Mapbox, GeoJSON
**Database:** PostgreSQL / Supabase
**Weather Data:** Open-Meteo

---

## Project Structure

```text
heatguard/
├── thermal/       # Thermal stress calculations
├── data/          # Weather, demographic, and health data
├── backend/       # API services
├── ml/            # Prediction models
├── frontend/      # Dashboard
└── README.md
```

---

## Setup

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

---

## MVP

The hackathon MVP will focus on:

1. Integrating real Bengaluru weather data
2. Calculating WBGT / Heat Index
3. Generating a heat-risk score
4. Displaying ward-level risk using GIS data
5. Providing a 3–5 day risk forecast
6. Generating recommended actions based on risk levels

---

## Current Progress

* Bengaluru selected as the pilot city
* Initial project structure created
* Python virtual environment configured
* Open-Meteo API connected
* Temperature, humidity, wind, and radiation data retrieved
* Thermal Stress Engine currently under development

---

## Development Approach

The project will be developed incrementally:

```text
Build → Test → Integrate → Validate → Demo
```

The primary focus is on developing a working and scientifically defensible MVP before adding additional features.
