# Data Sources & APIs Research Matrix for Indian Heat-Wave Modeling

## 1. Evaluation of Candidate Sources

| Source | Provider / Dataset | Free / Open? | Historical Temporal Range | Spatial Resolution | Variables Covered | Legal / Academic Use | Assessment & Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Open-Meteo Historical Archive** | ECMWF ERA5 & ERA5-Land Reanalysis | **Yes (Free, No API key required)** | 1940 – Present (1940–2025) | 0.1° (~9 km over India) | Tmax, Tmin, Tmean, RH, Dew Point, Precipitation, Surface Pressure, Wind Speed, Solar Radiation, Cloud Cover, Soil Moisture | CC-BY 4.0 (Open academic/commercial use) | **Selected Primary Source**: Complete multi-year continuous daily and hourly records across all Indian coordinates without temporal gaps. |
| **NASA POWER API** | NASA Langley Research Center | Yes (Free, Public REST API) | 1981 – Present | 0.5° × 0.5° (~50 km) | Tmax, Tmin, RH, Solar Irradiance, Wind Speed | Public Domain (NASA Open Data) | **Secondary / Cross-check Source**: Excellent solar data, but slower API latency and coarser spatial grid (50 km vs. 9 km). |
| **IMD Official Station Normal Climatology** | India Meteorological Department (IMD) / Opendata | Yes (Public Climatological Normals: 1981–2010 / 1991–2020) | Multi-decadal baseline averages | Station-level (All major Indian cities/airports) | Monthly & daily normal maximum temperatures, historical station extremes | Open Government Data (OGD) Platform India | **Authoritative Climatology Source**: Used to compute official IMD departure from normal for heat-wave classification. |
| **NOAA NCEI GSOD (Global Surface Summary of the Day)** | NOAA / WMO Stations | Yes (Free, FTP / REST API) | 1901 – Present | Station-specific (e.g., Delhi Safdarjung, Bengaluru HAL, Ahmedabad) | Daily Tmax, Tmin, Dew Point, Precipitation | Public Domain | Good for single-station historical cross-verification, but suffers from occasional missing days and station metadata changes. |
| **Copernicus CDS (Climate Data Store - ERA5)** | ECMWF | Yes (Free registration & API key) | 1950 – Present | 0.25° (~28 km) | Full atmospheric levels | Open Data | Excellent, but downloads are large NetCDF/GRIB files requiring queued asynchronous job processing. Open-Meteo provides pre-extracted tabular endpoints for the same underlying ERA5 data directly. |

---

## 2. Selection & Architecture Decision
* **Primary Time-Series Dataset**: Open-Meteo Historical Archive API (ERA5-Land reanalysis).
* **Target Cities / Geographic Climate Representation**:
  1. **New Delhi** (Northern Plains, Continental, severe heat-wave zone): Lat 28.6139, Lon 77.2090
  2. **Ahmedabad** (Western Arid / Semi-arid, frequent extreme heat): Lat 23.0225, Lon 72.5714
  3. **Bengaluru** (Deccan Plateau, High-altitude urban, moderate baseline): Lat 12.9716, Lon 77.5946
  4. **Kolkata** (Eastern Coastal / High-humidity delta, humid heat-wave zone): Lat 22.5726, Lon 88.3639
  5. **Nagpur** (Central India, Vidarbha heat corridor): Lat 21.1458, Lon 79.0882
* **Time Span**: **2018-01-01 to 2025-12-31** (8 full consecutive years, capturing major Indian heat waves of 2019, 2022, 2024).
