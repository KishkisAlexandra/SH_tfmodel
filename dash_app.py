# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Настройки / константы
# ------------------------
ARCHETYPES = {
    "Одинокий житель": 0.8,
    "Пара": 0.95,
    "Семья с детьми": 1.1,
    "Большая семья": 1.25
}

SCENARIOS = {"Экономный": 0.85, "Средний": 1.0, "Расточительный": 1.25}

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
    "heating_Gcal_per_m2_season_mid": 0.10,
    "heating_season_months": 7.0
}

# ------------------------
# Функции расчёта
# ------------------------
def calculate_volumes(area_m2, occupants, behavior_factor, coeffs=DEFAULT_COEFFS, month=1):
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2) * behavior_factor
    water = coeffs["water_per_person_m3"]*occupants*behavior_factor
    hot_water = water * coeffs["hot_water_fraction"]
    sewage = water
    if 4 <= month <= 10:  # Апрель–Октябрь: отопление не учитываем
        heat_monthly = 0.0
    else:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"] * area_m2
        heat_monthly = G_mid / coeffs["heating_season_months"]
    return {
        "Электроэнергия": round(elec,1),
        "Вода": round(water,2),
        "Горячая вода": round(hot_water,2),
        "Канализация": round(sewage,2),
        "Отопление": round(heat_monthly,3)
    }

def calculate_costs(volumes, tariffs, subsidy=False, subsidy_rate=0.2):
    t = tariffs.copy()
    if subsidy:
        t["heating_BYN_per_Gcal"] *= subsidy_rate
    elec_cost = volumes["Электроэнергия"] * t["electricity_BYN_per_kWh"]
    water_cost = volumes["Вода"] * t["water_BYN_per_m3"]
    sewage_cost = volumes["Канализация"] * t["sewage_BYN_per_m3"]
    heat_cost = volumes["Отопление"] * t["heating_BYN_per_Gcal"]
    fixed = t.get("fixed_fees_BYN",0.0)
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
# Sidebar: ввод параметров
# ------------------------
st.sidebar.header("Параметры расчёта")
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,1)
occupants = adults + children
behavior = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[behavior]
archetype_name = st.sidebar.selectbox("Сравнить с профилем (архетип)", list(ARCHETYPES.keys()), index=3)
archetype_factor = ARCHETYPES[archetype_name]

# Галочка льготного тарифа
st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Использовать льготный тариф")
if use_subsidy:
    subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05)
else:
    subsidy_rate = 1.0

# Расширенные настройки тарифа (только при включении льгот)
with st.sidebar.expander("Расширенные настройки тарифа"):
    t_elec = st.number_input("Электроэнергия BYN/kWh", value=DEFAULT_TARIFFS["electricity_BYN_per_kWh"], format="%.6f")
    t_water = st.number_input("Вода BYN/m³", value=DEFAULT_TARIFFS["water_BYN_per_m3"], format="%.6f")
    t_sewage = st.number_input("Канализация BYN/m³", value=DEFAULT_TARIFFS["sewage_BYN_per_m3"], format="%.6f")
    t_heating = st.number_input("Отопление BYN/Gcal", value=DEFAULT_TARIFFS["heating_BYN_per_Gcal"], format="%.2f")
    t_fixed = st.number_input("Фикс. платежи BYN/мес", value=DEFAULT_TARIFFS["fixed_fees_BYN"], format="%.2f")

tariffs = {
    "electricity_BYN_per_kWh": t_elec,
    "water_BYN_per_m3": t_water,
    "sewage_BYN_per_m3": t_sewage,
    "heating_BYN_per_Gcal": t_heating,
    "fixed_fees_BYN": t_fixed
}

# ------------------------
# Расчёт
# ------------------------
user_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)
user_costs = calculate_costs(user_vol, tariffs, subsidy=use_subsidy, subsidy_rate=subsidy_rate)
typical_vol = calculate_volumes(area_m2, occupants, archetype_factor, month=month)
typical_costs = calculate_costs(typical_vol, tariffs, subsidy=False)

# ------------------------
# Коммунальные платежи
# ------------------------
st.header("🏠 Коммунальные платежи")
st.subheader(f"Сравнение с профилем: «{archetype_name}»")

col1, col2 = st.columns(2)
with col1:
    st.metric("Ваш счёт, BYN", f"{user_costs['Итого']}")
    st.metric("Типовой счёт, BYN", f"{typical_costs['Итого']}")
    diff_percent = round((user_costs['Итого']/typical_costs['Итого']-1)*100,1)
    st.info(f"Ваши расходы на {diff_percent}% {'выше' if diff_percent>0 else 'ниже'} среднего профиля.")

with col2:
    # Столбцовая диаграмма
    cost_df = pd.DataFrame({
        "Категория": list(user_costs.keys())[:-1],
        "Ваши расходы": list(user_costs.values())[:-1],
        "Типовые расходы": list(typical_costs.values())[:-1]
    })
    fig = px.bar(cost_df, x="Категория", y=["Ваши расходы","Типовые расходы"],
                 barmode="group", color_discrete_sequence=["#636EFA","#EF553B"])
    fig.update_layout(yaxis_title="BYN / месяц")
    st.plotly_chart(fig, use_container_width=True)
