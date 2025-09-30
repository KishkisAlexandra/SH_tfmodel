# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# ОБЩИЕ НАСТРОЙКИ
# ------------------------
SCENARIOS = {"Экономный": 0.85, "Средний": 1.0, "Расточительный": 1.25}
HOUSE_COEFS = {
    "Новый": {"heating": 1.0, "electricity": 1.0},
    "Средний": {"heating": 1.05, "electricity": 1.05},
    "Старый": {"heating": 1.1, "electricity": 1.05},
}
REALISM_UPLIFT = 1.07
MONTH_NAMES = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]

# ----------------------------------------------------
# --- ДАННЫЕ И ЛОГИКА ДЛЯ МИНСКА (БЕЛАРУСЬ) ---
# ----------------------------------------------------
MINSK_CATEGORIES = ["Электроэнергия", "Вода", "Канализация", "Отопление", "Фикс. платежи"]
MINSK_HEATING_MONTHS = [1, 2, 3, 4, 10, 11, 12]

MINSK_DEFAULT_COEFFS = {
    "elec_base_kWh": 60.0, "elec_per_person_kWh": 75.0, "elec_per_m2_kWh": 0.5,
    "water_per_person_m3": 4.5, "hot_water_fraction": 0.6,
    "heating_Gcal_per_m2_season_mid": 0.15, "heating_season_months": 7.0
}

MINSK_TARIFFS = {
    "electricity_BYN_per_kWh_full": 0.2969, "electricity_BYN_per_kWh_subsidy": 0.2412,
    "heating_BYN_per_Gcal_full": 134.94, "heating_BYN_per_Gcal_subsidy": 24.7187,
    "water_BYN_per_m3": 1.7858, "sewage_BYN_per_m3": 0.9586, "fixed_fees_BYN": 5.0
}

def calculate_volumes_minsk(area_m2, occupants, behavior_factor, month=1):
    coeffs = MINSK_DEFAULT_COEFFS
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"] * occupants +
            coeffs["elec_per_m2_kWh"] * area_m2) * behavior_factor
    water = coeffs["water_per_person_m3"] * occupants * behavior_factor
    sewage = water
    heat_monthly = 0.0
    if month in MINSK_HEATING_MONTHS:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"] * area_m2
        heat_monthly = G_mid / coeffs["heating_season_months"]
    return {
        "Электроэнергия": round(elec, 1), "Вода": round(water, 2),
        "Канализация": round(sewage, 2), "Отопление": round(heat_monthly, 3)
    }

def calculate_costs_minsk(volumes, tariffs, area_m2, occupants, floor=1, has_elevator=True):
    elec_cost = volumes["Электроэнергия"] * tariffs["electricity_BYN_per_kWh_subsidy"]
    water_cost = volumes["Вода"] * tariffs["water_BYN_per_m3"]
    sewage_cost = volumes["Канализация"] * tariffs["sewage_BYN_per_m3"]
    heat_cost = volumes["Отопление"] * tariffs["heating_BYN_per_Gcal_subsidy"]

    fixed = (area_m2 * 0.0388) + (area_m2 * 0.0249) + (0.2092 * occupants) + (area_m2 * 0.05)
    if has_elevator and floor >= 2:
        fixed += 0.88 * occupants

    costs = {
        "Электроэнергия": round(elec_cost, 2), "Вода": round(water_cost, 2),
        "Канализация": round(sewage_cost, 2), "Отопление": round(heat_cost, 2),
        "Фикс. платежи": round(fixed, 2)
    }
    costs["Итого"] = round(sum(costs.values()), 2)
    return costs

# ----------------------------------------------------
# --- ДАННЫЕ И ЛОГИКА ДЛЯ ЛИМАСОЛА (КИПР) ---
# ----------------------------------------------------
LIMASSOL_CATEGORIES = ["Аренда", "Электроэнергия", "Вода", "Интернет", "Телефон", "IPTV", "Обслуживание"]

LIMASSOL_TARIFFS = {
    "rent": 4600,
    "electricity_history": {
        1: 0.242, 2: 0.242, 3: 0.242, 4: 0.242, 5: 0.2705, 6: 0.2705,
        7: 0.2661, 8: 0.2661, 9: 0.2661, 10: 0.2661, 11: 0.2661, 12: 0.2661
    },
    "vat_electricity": 0.19, "water_base": 22,
    "water_tiers": {40: 0.9, 80: 1.43, 120: 2.45, float('inf'): 5.0},
    "vat_water": 0.05, "internet": 20, "phone": 20, "iptv": 10,
    "vat_services": 0.19, "service_min": 45, "service_max": 125,
}

def calculate_water_cost_limassol(volume_m3):
    tariffs = LIMASSOL_TARIFFS
    cost = tariffs["water_base"]
    remaining_volume = volume_m3
    tier_limits = sorted(tariffs["water_tiers"].keys())
    last_limit = 0
    for limit in tier_limits:
        if remaining_volume <= 0: break
        vol_in_tier = min(remaining_volume, limit - last_limit)
        cost += vol_in_tier * tariffs["water_tiers"][limit]
        remaining_volume -= vol_in_tier
        last_limit = limit
    return cost * (1 + tariffs["vat_water"])

def calculate_costs_limassol(volumes, month):
    tariffs = LIMASSOL_TARIFFS
    elec_tariff = tariffs["electricity_history"].get(month, 0.2661)
    costs = {
        "Аренда": tariffs["rent"],
        "Электроэнергия": round(volumes["Электроэнергия"] * elec_tariff * (1 + tariffs["vat_electricity"]), 2),
        "Вода": round(calculate_water_cost_limassol(volumes["Вода"]), 2),
        "Интернет": round(tariffs["internet"] * (1 + tariffs["vat_services"]), 2),
        "Телефон": round(tariffs["phone"] * (1 + tariffs["vat_services"]), 2),
        "IPTV": round(tariffs["iptv"] * (1 + tariffs["vat_services"]), 2),
        "Обслуживание": round(((tariffs["service_min"] + tariffs["service_max"]) / 2) * (1 + tariffs["vat_services"]), 2)
    }
    costs["Итого"] = round(sum(costs.values()), 2)
    return costs

# ------------------------
# Sidebar: общие параметры
# ------------------------
st.sidebar.header("📍 Выбор города и параметры")
selected_city = st.sidebar.selectbox("Город", ["Минск", "Лимасол"], key='city_select')
month = st.sidebar.selectbox("Месяц", list(range(1, 13)), format_func=lambda x: MONTH_NAMES[x - 1], key='month_select')

# ------------------------
# ГЛАВНОЕ ОКНО
# ------------------------
if selected_city == "Минск":
    st.title("🏠 Коммунальные платежи: Минск")
    
    st.sidebar.header("Параметры семьи (Минск)")
    area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0, key='minsk_area')
    adults = st.sidebar.number_input("Взрослые", 0, 10, 2, key='minsk_adults')
    children = st.sidebar.number_input("Дети", 0, 10, 2, key='minsk_children')
    occupants = adults + children
    
    scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1, key='minsk_scenario')
    behavior_factor = SCENARIOS[scenario]
    house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1, key='minsk_house_type')
    st.sidebar.markdown("---")
    use_subsidy = st.sidebar.checkbox("Использовать льготный тариф", key='minsk_subsidy_check')
    subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05, key='minsk_subsidy_slider') if use_subsidy else 1.0

    st.header("📊 Введите ваши реальные расходы за месяц (BYN)")
    with st.expander("Показать поля для ручного ввода"):
        user_real = {cat: st.number_input(f"{cat} BYN", min_value=0.0, value=0.0, step=1.0, format="%.2f", key=f'minsk_input_{cat}') for cat in MINSK_CATEGORIES}
    user_real["Итого"] = sum(user_real.values())

    ideal_vol = calculate_volumes_minsk(area_m2, occupants, 1.0, month=month)
    ideal_costs = calculate_costs_minsk(ideal_vol, MINSK_TARIFFS, area_m2, occupants)
    neighbor_vol = calculate_volumes_minsk(area_m2, occupants, behavior_factor, month=month)
    neighbor_costs_minsk = calculate_costs_minsk(neighbor_vol, MINSK_TARIFFS, area_m2, occupants)
    neighbor_costs = {k: v * REALISM_UPLIFT for k, v in neighbor_costs_minsk.items()}
    neighbor_costs["Итого"] = sum(neighbor_costs.values())

    st.header("🏠 Сравнение расходов (Минск)")
    # ... остальная часть кода для Минска не меняется ...

elif selected_city == "Лимасол":
    st.title("🏠 Коммунальные платежи: Лимасол")
    
    st.header("📊 Введите ваше фактическое потребление и расходы за месяц")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Потребление ресурсов")
        user_consumption = {
            "Электроэнергия": st.number_input("Электроэнергия, кВт·ч", min_value=0.0, value=1048.0, step=10.0, key='limassol_consum_elec'),
            "Вода": st.number_input("Вода, м³", min_value=0.0, value=25.2, step=1.0, key='limassol_consum_water'),
        }
    with col2:
        st.subheader("Фактические расходы (€)")
        user_real_costs = {
            cat: st.number_input(f"{cat} €", min_value=0.0, value=0.0, step=5.0, key=f'limassol_costs_{cat}') for cat in LIMASSOL_CATEGORIES
        }
    user_real_costs["Итого"] = sum(user_real_costs.values())

    calculated_costs = calculate_costs_limassol(user_consumption, month)

    st.header("🏠 Сравнение расчетных и реальных расходов (€)")
    # ... остальная часть кода для Лимасола не меняется ...

# (Весь остальной код для отображения таблиц и графиков остается без изменений)
# Я не стал его сюда копировать, чтобы не загромождать ответ, 
# но он должен остаться в вашем файле.
# Просто вставьте этот исправленный код до начала секции
# с st.header("🏠 Сравнение расходов (Минск)") 
# и до st.header("🏠 Сравнение расчетных и реальных расходов (€)")
