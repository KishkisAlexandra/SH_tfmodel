# app.py
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Utility Benchmark Dashboard",
    page_icon="🏠",
    layout="wide"
)

# ---- Типовые профили ----
profiles = {"eco": 0.85, "average": 1.0, "intensive": 1.15}

DEFAULT_TARIFFS = {
    "electricity_BYN_per_kWh": 0.254,
    "water_BYN_per_m3": 1.7858,
    "sewage_BYN_per_m3": 0.9586,
    "heating_BYN_per_Gcal": 135.0,
    "fixed_fees_BYN": 5.0
}

DEFAULT_COEFFS = {
    "elec_base_kWh": 40.0,
    "elec_per_person_kWh": 35.0,
    "elec_per_m2_kWh": 0.25,
    "water_per_person_m3": 3.5,
    "hot_water_fraction": 0.45,
    "heating_Gcal_per_m2_season_low": 0.08,
    "heating_Gcal_per_m2_season_mid": 0.10,
    "heating_Gcal_per_m2_season_high": 0.12,
    "heating_season_months": 7.0
}

# ---- Функции расчёта ----
def calculate_volumes(area_m2, occupants, profile, coeffs=DEFAULT_COEFFS, month=1):
    pf = profiles.get(profile, 1.0)
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2)*pf
    water = coeffs["water_per_person_m3"]*occupants*pf
    hot_water = water*coeffs["hot_water_fraction"]
    sewage = water
    # Отопление отключаем с апреля (4) по октябрь (10)
    if 4 <= month <= 10:
        heat_monthly_low = 0
        heat_monthly_mid = 0
        heat_monthly_high = 0
    else:
        G_low = coeffs["heating_Gcal_per_m2_season_low"]*area_m2
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"]*area_m2
        G_high = coeffs["heating_Gcal_per_m2_season_high"]*area_m2
        heat_monthly_low = G_low / coeffs["heating_season_months"]
        heat_monthly_mid = G_mid / coeffs["heating_season_months"]
        heat_monthly_high = G_high / coeffs["heating_season_months"]
    return {
        "electricity_kWh": round(elec,1),
        "water_m3": round(water,2),
        "hot_water_m3": round(hot_water,2),
        "sewage_m3": round(sewage,2),
        "heating_Gcal_month_low": round(heat_monthly_low,3),
        "heating_Gcal_month_mid": round(heat_monthly_mid,3),
        "heating_Gcal_month_high": round(heat_monthly_high,3)
    }

def calculate_costs(volumes, tariffs, heating_scenario="mid"):
    elec_cost = volumes["electricity_kWh"]*tariffs["electricity_BYN_per_kWh"]
    water_cost = volumes["water_m3"]*tariffs["water_BYN_per_m3"]
    sewage_cost = volumes["sewage_m3"]*tariffs["sewage_BYN_per_m3"]
    heat_cost = volumes[f"heating_Gcal_month_{heating_scenario}"]*tariffs["heating_BYN_per_Gcal"]
    fixed = tariffs.get("fixed_fees_BYN",0)
    costs = {
        "electricity_cost": round(elec_cost,2),
        "water_cost": round(water_cost,2),
        "sewage_cost": round(sewage_cost,2),
        "heating_cost": round(heat_cost,2),
        "fixed_fees": round(fixed,2)
    }
    costs["total_monthly"] = round(sum(costs.values()),2)
    return costs

# ---- Sidebar ----
with st.sidebar:
    st.header("Параметры вашего жилья")
    month = st.selectbox("Месяц", list(range(1,13)), format_func=lambda x:
                         ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
    area_m2 = st.number_input("Площадь, м²", min_value=10.0, max_value=500.0, value=80.0)
    adults = st.number_input("Взрослые", min_value=0, max_value=10, value=2)
    children = st.number_input("Дети", min_value=0, max_value=10, value=1)
    profile = st.selectbox("Профиль поведения", ["eco","average","intensive"], index=1)
    heating_type = st.selectbox("Тип отопления", ["central","gas","electric"], index=0)
    housing_type = st.selectbox("Тип жилья", ["квартира","дом"], index=0)

# ---- Расчёты ----
occupants = adults + children
user_volumes = calculate_volumes(area_m2, occupants, profile, month=month)
user_costs = calculate_costs(user_volumes, DEFAULT_TARIFFS)

typical_volumes = calculate_volumes(area_m2, occupants, "average", month=month)
typical_costs = calculate_costs(typical_volumes, DEFAULT_TARIFFS)

# ---- Дашборд ----
st.title("🏠 Моделирование типового домохозяйства")
st.subheader(f"Месяц: {month}")

col1, col2 = st.columns(2)
with col1:
    st.metric("Ваши расходы (BYN/мес)", f"{user_costs['total_monthly']}")
    st.metric("Электроэнергия", f"{user_costs['electricity_cost']}")
    st.metric("Отопление", f"{user_costs['heating_cost']}")
with col2:
    st.metric("Типовые расходы (BYN/мес)", f"{typical_costs['total_monthly']}")
    st.metric("Электроэнергия", f"{typical_costs['electricity_cost']}")
    st.metric("Отопление", f"{typical_costs['heating_cost']}")

# ---- Бар-чарт для сравнения расходов ----
st.subheader("Сравнение расходов по услугам")
compare_chart_df = pd.DataFrame({
    "Ваши показатели": [user_costs["electricity_cost"], user_costs["water_cost"], user_costs["heating_cost"]],
    "Типовые показатели": [typical_costs["electricity_cost"], typical_costs["water_cost"], typical_costs["heating_cost"]]
}, index=["Электроэнергия","Вода","Отопление"])

st.bar_chart(compare_chart_df)

# ---- Бар-чарт для сравнения объёмов ----
st.subheader("Сравнение объёмов потребления")
compare_volumes_df = pd.DataFrame({
    "Ваши показатели": [user_volumes["electricity_kWh"], user_volumes["water_m3"], user_volumes["hot_water_m3"],
                        user_volumes["sewage_m3"], user_volumes["heating_Gcal_month_mid"]],
    "Типовые показатели": [typical_volumes["electricity_kWh"], typical_volumes["water_m3"], typical_volumes["hot_water_m3"],
                           typical_volumes["sewage_m3"], typical_volumes["heating_Gcal_month_mid"]]
}, index=["Электроэнергия (kWh)","Вода (m³)","Горячая вода (m³)","Канализация (m³)","Отопление (Gcal)"])

st.bar_chart(compare_volumes_df)
