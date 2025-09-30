# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Константы
# ------------------------
SCENARIOS = {"Экономный": 0.85, "Средний": 1.0, "Расточительный": 1.25}

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
HEATING_MONTHS = [1,2,3,4,10,11,12]

# Минск тарифы
ELECTRICITY_FULL = 0.2969
ELECTRICITY_SUBSIDY = 0.2412
HEATING_FULL = 134.94
HEATING_SUBSIDY = 24.7187
WATER_TARIFF = 1.7858
SEWAGE_TARIFF = 0.9586
FIXED_FEES = 5.0
CATEGORIES_MINSK = ["Электроэнергия", "Вода", "Канализация", "Отопление", "Фикс. платежи"]

# Лимассол тарифы и НДС
ELECTRICITY_HISTORY = {1:0.242,2:0.242,3:0.242,4:0.242,5:0.242,6:0.242,
                       7:0.242,8:0.242,9:0.242,10:0.2661,11:0.2661,12:0.2661}
WATER_VOLUME = 25.2
WATER_BASE = 22
WATER_TARIFF = 0.9
WATER_VAT = 1.05
VAT_ELECTRICITY = 1.19
VAT_OTHER = 1.19
SERVICE_MIN = 45
SERVICE_MAX = 125
CATEGORIES_LIMASSOL = ["Электроэнергия","Вода","Интернет","Телефон","IPTV","Сервисный сбор","Итого"]

# ------------------------
# Функции расчёта
# ------------------------
def calculate_volumes(area_m2, occupants, behavior_factor, coeffs=DEFAULT_COEFFS, month=1):
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2) * behavior_factor
    water = coeffs["water_per_person_m3"]*occupants*behavior_factor
    hot_water = water * coeffs["hot_water_fraction"]
    sewage = water
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

def calculate_costs_from_volumes(volumes, tariffs, area_m2=50, occupants=1, floor=1, has_elevator=True):
    elec_cost = volumes["Электроэнергия"] * tariffs["electricity_BYN_per_kWh"]
    water_cost = volumes["Вода"] * tariffs["water_BYN_per_m3"]
    sewage_cost = volumes["Канализация"] * tariffs["sewage_BYN_per_m3"]
    heat_cost = volumes["Отопление"] * tariffs["heating_BYN_per_Gcal"]

    maintenance_max = 0.0388
    lighting_max = 0.0249
    waste_norm = 0.2092
    capital_repair_rate = 0.05
    elevator_max = 0.88

    maintenance_cost = area_m2 * maintenance_max
    lighting_cost = area_m2 * lighting_max
    waste_cost = waste_norm * occupants
    capital_repair_cost = area_m2 * capital_repair_rate
    elevator_cost = elevator_max * occupants if has_elevator and floor >= 2 else 0.0

    fixed = maintenance_cost + lighting_cost + waste_cost + capital_repair_cost + elevator_cost

    costs = {
        "Электроэнергия": round(elec_cost,2),
        "Вода": round(water_cost,2),
        "Канализация": round(sewage_cost,2),
        "Отопление": round(heat_cost,2),
        "Фикс. платежи": round(fixed,2)
    }
    costs["Итого"] = round(sum(costs.values()),2)
    return costs

def apply_neighbor_adjustment(volumes, tariffs, house_category, area_m2, occupants, floor=1, has_elevator=True):
    coefs = HOUSE_COEFS.get(house_category, {"heating":1.0,"electricity":1.0})
    vol_adj = volumes.copy()
    vol_adj["Электроэнергия"] = vol_adj["Электроэнергия"] * coefs["electricity"]
    vol_adj["Отопление"] = vol_adj["Отопление"] * coefs["heating"]
    neighbor_costs = calculate_costs_from_volumes(vol_adj, tariffs, area_m2, occupants, floor, has_elevator)
    neighbor_costs = {k: round(v * REALISM_UPLIFT, 2) for k, v in neighbor_costs.items()}
    return neighbor_costs

def calculate_limassol_costs(electricity_kWh, month, use_max_other=False):
    elec_rate = ELECTRICITY_HISTORY.get(month,0.2661)
    electricity_cost = electricity_kWh * elec_rate * VAT_ELECTRICITY
    water_cost = (WATER_BASE + WATER_VOLUME*WATER_TARIFF) * WATER_VAT

    # Прочие расходы
    internet = 20 * VAT_OTHER
    phone = 20 * VAT_OTHER
    iptv = 10 * VAT_OTHER
    service = SERVICE_MAX if use_max_other else SERVICE_MIN

    total = electricity_cost + water_cost + internet + phone + iptv + service
    return {
        "Электроэнергия": round(electricity_cost,2),
        "Вода": round(water_cost,2),
        "Интернет": round(internet,2),
        "Телефон": round(phone,2),
        "IPTV": round(iptv,2),
        "Сервисный сбор": round(service,2),
        "Итого": round(total,2)
    }

# ------------------------
# Sidebar: Параметры семьи и города
# ------------------------
st.sidebar.header("Параметры")
city = st.sidebar.selectbox("Город", ["Минск","Лимассол"])
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,2)
occupants = adults + children

if city=="Минск":
    scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
    behavior_factor = SCENARIOS[scenario]
    house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1)
    use_subsidy = st.sidebar.checkbox("Использовать льготный тариф (дополнительно к субсидированному)")
    subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05) if use_subsidy else 1.0
else:
    electricity_kWh = st.sidebar.number_input("Электроэнергия, кВт·ч", 0, 5000, 1048)
    use_max_other = st.sidebar.checkbox("Использовать максимальные прочие расходы")

# ------------------------
# Ввод реальных расходов
# ------------------------
st.header("📊 Ваши реальные расходы за месяц")
if city=="Минск":
    user_real = {
        "Электроэнергия": st.number_input("Электроэнергия BYN", 0.0, 10000.0, 0.0),
        "Вода": st.number_input("Вода BYN", 0.0, 1000.0, 0.0),
        "Канализация": st.number_input("Канализация BYN",0.0,1000.0,0.0),
        "Отопление": st.number_input("Отопление BYN",0.0,1000.0,0.0),
        "Фикс. платежи": st.number_input("Фикс. платежи BYN",0.0,1000.0,0.0)
    }
    user_real["Итого"] = round(sum(user_real[k] for k in CATEGORIES_MINSK),2)
else:
    user_real = {
        "Электроэнергия": st.number_input("Электроэнергия €",0.0,5000.0,0.0),
        "Вода": st.number_input("Вода €",0.0,500.0,0.0),
        "Интернет": st.number_input("Интернет €",0.0,100.0,0.0),
        "Телефон": st.number_input("Телефон €",0.0,100.0,0.0),
        "IPTV": st.number_input("IPTV €",0.0,100.0,0.0),
        "Сервисный сбор": st.number_input("Сервисный сбор €",0.0,500.0,0.0)
    }
    user_real["Итого"] = round(sum(user_real[k] for k in CATEGORIES_LIMASSOL[:-1]),2)

# ------------------------
# Расчёт идеального и среднего соседа
# ------------------------
if city=="Минск":
    ideal_vol = calculate_volumes(area_m2, occupants, 1.0, month=month)
    ideal_costs = calculate_costs_from_volumes(ideal_vol,{
        "electricity_BYN_per_kWh": ELECTRICITY_SUBSIDY,
        "water_BYN_per_m3": WATER_TARIFF,
        "sewage_BYN_per_m3": SEWAGE_TARIFF,
        "heating_BYN_per_Gcal": HEATING_SUBSIDY,
        "fixed_fees_BYN": FIXED_FEES
    }, area_m2, occupants)
    
    neighbor_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)
    neighbor_tariffs = {
        "electricity_BYN_per_kWh": ELECTRICITY_SUBSIDY * subsidy_rate,
        "water_BYN_per_m3": WATER_TARIFF,
        "sewage_BYN_per_m3
