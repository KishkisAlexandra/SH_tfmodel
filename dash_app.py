# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Константы
# ------------------------
DEFAULT_TARIFFS = {
    "electricity_BYN_per_kWh": 0.254,
    "water_BYN_per_m3": 1.7858,
    "sewage_BYN_per_m3": 0.9586,
    "heating_BYN_per_Gcal": 135.0,
    "maintenance_BYN_per_m2": 0.5,
    "waste_BYN_per_person": 2.0,
    "elevator_BYN_per_person": 1.0
}

DEFAULT_COEFFS = {
    "elec_base_kWh": 60.0,
    "elec_per_person_kWh": 75.0,
    "elec_per_m2_kWh": 0.5,
    "water_per_person_m3": 4.5,
    "hot_water_fraction": 0.6,
    "heating_Gcal_per_m2_season_mid": 0.15,
    "heating_season_months": 7.0
}

HOUSE_COEFS = {
    "Новый": {"heating": 1.0, "electricity": 1.0},
    "Средний": {"heating": 1.05, "electricity": 1.05},
    "Старый": {"heating": 1.1, "electricity": 1.05},
}

REALISM_UPLIFT = 1.07
CATEGORIES = ["Электроэнергия", "Вода", "Канализация", "Отопление", "Фикс. платежи"]
HEATING_MONTHS = [1,2,3,4,10,11,12]

# ------------------------
# Функции расчёта
# ------------------------
def calculate_volumes(area_m2, occupants, behavior_factor=1.0, coeffs=DEFAULT_COEFFS, month=1):
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2) * behavior_factor
    water = coeffs["water_per_person_m3"]*occupants*behavior_factor
    hot_water = water * coeffs["hot_water_fraction"]
    sewage = water
    heat_monthly = 0.0
    if month in HEATING_MONTHS:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"] * area_m2
        heat_monthly = G_mid / coeffs["heating_season_months"]
    return {
        "Электроэнергия": round(elec,1),
        "Вода": round(water,2),
        "Горячая вода": round(hot_water,2),
        "Канализация": round(sewage,2),
        "Отопление": round(heat_monthly,3)
    }

def calculate_costs_from_volumes(volumes, tariffs, area_m2, occupants, has_elevator=False, subsidy=False, subsidy_rate=0.2):
    t = tariffs.copy()
    if subsidy:
        t["heating_BYN_per_Gcal"] *= subsidy_rate
    elec_cost = volumes["Электроэнергия"] * t["electricity_BYN_per_kWh"]
    water_cost = volumes["Вода"] * t["water_BYN_per_m3"]
    sewage_cost = volumes["Канализация"] * t["sewage_BYN_per_m3"]
    heat_cost = volumes["Отопление"] * t["heating_BYN_per_Gcal"]

    # Фиксированные платежи
    maintenance_cost = area_m2 * t["maintenance_BYN_per_m2"]
    waste_cost = occupants * t["waste_BYN_per_person"]
    elevator_cost = occupants * t["elevator_BYN_per_person"] if has_elevator else 0.0
    fixed_total = maintenance_cost + waste_cost + elevator_cost

    costs = {
        "Электроэнергия": round(elec_cost,2),
        "Вода": round(water_cost,2),
        "Канализация": round(sewage_cost,2),
        "Отопление": round(heat_cost,2),
        "Фикс. платежи": round(fixed_total,2)
    }
    costs["Итого"] = round(sum(costs.values()),2)
    return costs

def apply_neighbor_adjustment(volumes, tariffs, house_category, behavior_factor, area_m2, occupants, has_elevator):
    vol_adj = volumes.copy()
    coefs = HOUSE_COEFS.get(house_category, {"heating":1.0,"electricity":1.0})
    vol_adj["Электроэнергия"] = vol_adj["Электроэнергия"] * behavior_factor * coefs["electricity"]
    vol_adj["Отопление"] = vol_adj["Отопление"] * coefs["heating"]
    neighbor_costs = calculate_costs_from_volumes(vol_adj, tariffs, area_m2, occupants, has_elevator, subsidy=False)
    neighbor_costs = {k: round(v * REALISM_UPLIFT, 2) for k, v in neighbor_costs.items()}
    return neighbor_costs

# ------------------------
# Sidebar
# ------------------------
st.sidebar.header("Параметры семьи")
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 65.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,1)
occupants = adults + children

st.sidebar.markdown("---")
scenario = st.sidebar.selectbox("Сценарий поведения", ["Экономный","Средний","Расточительный"], index=1)
behavior_factor_neighbor = {"Экономный":0.85,"Средний":1.0,"Расточительный":1.25}[scenario]
house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1)

st.sidebar.markdown("---")
has_elevator = st.sidebar.checkbox("Есть лифт в доме?", value=True)
use_subsidy = st.sidebar.checkbox("Использовать льготный тариф")
subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05) if use_subsidy else 1.0

with st.sidebar.expander("Расширенные настройки тарифа"):
    t_elec = st.number_input("Электроэнергия BYN/kWh", value=DEFAULT_TARIFFS["electricity_BYN_per_kWh"], format="%.6f")
    t_water = st.number_input("Вода BYN/m³", value=DEFAULT_TARIFFS["water_BYN_per_m3"], format="%.6f")
    t_sewage = st.number_input("Канализация BYN/m³", value=DEFAULT_TARIFFS["sewage_BYN_per_m3"], format="%.6f")
    t_heating = st.number_input("Отопление BYN/Gcal", value=DEFAULT_TARIFFS["heating_BYN_per_Gcal"], format="%.2f")
    t_maintenance = st.number_input("Обслуживание BYN/м²", value=DEFAULT_TARIFFS["maintenance_BYN_per_m2"], format="%.2f")
    t_waste = st.number_input("Вывоз мусора BYN/чел", value=DEFAULT_TARIFFS["waste_BYN_per_person"], format="%.2f")
    t_elevator = st.number_input("Лифт BYN/чел", value=DEFAULT_TARIFFS["elevator_BYN_per_person"], format="%.2f")

tariffs = {
    "electricity_BYN_per_kWh": t_elec,
    "water_BYN_per_m3": t_water,
    "sewage_BYN_per_m3": t_sewage,
    "heating_BYN_per_Gcal": t_heating,
    "maintenance_BYN_per_m2": t_maintenance,
    "waste_BYN_per_person": t_waste,
    "elevator_BYN_per_person": t_elevator
}

# ------------------------
# Расчёты
ideal_vol = calculate_volumes(area_m2, occupants, behavior_factor=1.0, coeffs=DEFAULT_COEFFS, month=month)
ideal_costs = calculate_costs_from_volumes(ideal_vol, tariffs, area_m2, occupants, has_elevator, subsidy=use_subsidy, subsidy_rate=subsidy_rate)

neighbor_vol = calculate_volumes(area_m2, occupants, behavior_factor=1.0, coeffs=DEFAULT_COEFFS, month=month)
neighbor_costs = apply_neighbor_adjustment(neighbor_vol, tariffs, house_category, behavior_factor_neighbor, area_m2, occupants, has_elevator)

# ------------------------
# Визуализация
st.header("🏠 Сравнение расходов")
col1, col2 = st.columns([2,1])
with col1:
    st.metric("Идеальный расчёт по нормативам, BYN", f"{ideal_costs['Итого']:.2f}")
    st.metric("Средний сосед, BYN", f"{neighbor_cost
