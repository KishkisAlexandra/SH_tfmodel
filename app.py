# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import yaml
import os

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Список городов
# ------------------------
CONFIG_DIR = "configs"
cities = [f.replace(".yaml", "") for f in os.listdir(CONFIG_DIR) if f.endswith(".yaml")]

st.sidebar.header("Выберите город")
city = st.sidebar.selectbox("Город", cities)

# ------------------------
# Загрузка конфигурации для выбранного города
# ------------------------
with open(f"{CONFIG_DIR}/{city}.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Извлекаем тарифы, нормативы и коэффициенты дома
tariffs = config["tariffs"]
coeffs = config["norms"]
house_coefs = config["house_coeffs"]

# ------------------------
# Параметры семьи
# ------------------------
st.sidebar.header("Параметры семьи")
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн",
                                                    "Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,1)
occupants = adults + children

scenario_options = {"Экономный": 0.85, "Средний": 1.0, "Расточительный": 1.25}
scenario = st.sidebar.selectbox("Сценарий поведения", list(scenario_options.keys()), index=1)
behavior_factor = scenario_options[scenario]

house_category = st.sidebar.selectbox("Категория дома", list(house_coefs.keys()), index=1)

# ------------------------
# Льгота
# ------------------------
st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Использовать субсидированный тариф")
if use_subsidy:
    subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.85, 0.05)  # пример 0.85
else:
    subsidy_rate = 1.0

# ------------------------
# Расчётные функции (пример)
# ------------------------
def calculate_volumes(area_m2, occupants, behavior_factor, coeffs=coeffs, month=1):
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2) * behavior_factor
    water = coeffs["water_per_person_m3"]*occupants*behavior_factor
    hot_water = water * coeffs["hot_water_fraction"]
    sewage = water
    HEATING_MONTHS = [1,2,3,4,10,11,12]
    if month in HEATING_MONTHS:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"] * area_m2
        heat_monthly = G_mid / coeffs["heating_season_months"]
    else:
        heat_monthly = 0.0
    return {
        "Электроэнергия": round(elec,1),
        "Вода": round(water,2),
        "Горячая вода": round(hot_water,2),
        "Канализация": round(sewage,2),
        "Отопление": round(heat_monthly,3)
    }

def calculate_costs_from_volumes(volumes, tariffs, area_m2=50, occupants=1):
    elec_cost = volumes["Электроэнергия"] * tariffs["electricity_BYN_per_kWh"] * subsidy_rate
    water_cost = volumes["Вода"] * tariffs["water_BYN_per_m3"]
    sewage_cost = volumes["Канализация"] * tariffs["sewage_BYN_per_m3"]
    heat_cost = volumes["Отопление"] * tariffs["heating_BYN_per_Gcal"] * subsidy_rate
    fixed = tariffs["fixed_fees_BYN"]
    costs = {
        "Электроэнергия": round(elec_cost,2),
        "Вода": round(water_cost,2),
        "Канализация": round(sewage_cost,2),
        "Отопление": round(heat_cost,2),
        "Фикс. платежи": round(fixed,2)
    }
    costs["Итого"] = round(sum(costs.values()),2)
    return costs

# ------------------------
# Пример расчёта для пользователя
# ------------------------
ideal_vol = calculate_volumes(area_m2, occupants, 1.0, month=month)
ideal_costs = calculate_costs_from_volumes(ideal_vol, tariffs)

st.header(f"🏠 Расчёт коммунальных услуг для города {city}")
st.write("Идеальный расчёт по нормативам:", ideal_costs)

