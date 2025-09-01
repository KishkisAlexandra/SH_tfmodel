import streamlit as st
import pandas as pd
pip install plotly
import plotly.graph_objects as go

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

# ---- Функции ----
def calculate_volumes(area_m2, occupants, profile, coeffs=DEFAULT_COEFFS, month=1):
    pf = profiles.get(profile, 1.0)
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2)*pf
    water = coeffs["water_per_person_m3"]*occupants*pf
    hot_water = water*coeffs["hot_water_fraction"]
    sewage = water
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
        "heating_Gcal_month_mid": round(heat_monthly_mid,3)
    }

def calculate_costs(volumes, tariffs, heating_scenario="mid"):
    elec_cost = volumes["electricity_kWh"]*tariffs["electricity_BYN_per_kWh"]
    water_cost = volumes["water_m3"]*tariffs["water_BYN_per_m3"]
    sewage_cost = volumes["sewage_m3"]*tariffs["sewage_BYN_per_m3"]
    heat_cost = volumes["heating_Gcal_month_mid"]*tariffs["heating_BYN_per_Gcal"]
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
    st.header("Ваши параметры")
    month = st.selectbox("Месяц", list(range(1,13)), format_func=lambda x:
                         ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
    area_m2 = st.number_input("Площадь, м²", min_value=10.0, max_value=500.0, value=80.0)
    adults = st.number_input("Взрослые", min_value=0, max_value=10, value=2)
    children = st.number_input("Дети", min_value=0, max_value=10, value=1)
    profile = st.selectbox("Профиль", ["eco","average","intensive"], index=1)

# ---- Расчёты ----
occupants = adults + children
user_volumes = calculate_volumes(area_m2, occupants, profile, month=month)
user_costs = calculate_costs(user_volumes, DEFAULT_TARIFFS)

typical_volumes = calculate_volumes(area_m2, occupants, "average", month=month)
typical_costs = calculate_costs(typical_volumes, DEFAULT_TARIFFS)

# ---- Дашборд ----
st.title("🏠 Сравнение коммунальных расходов")

# 1. Спидометр
st.subheader("📊 Ваши расходы относительно типового")
fig_gauge = go.Figure(go.Indicator(
    mode = "gauge+number+delta",
    value = user_costs["total_monthly"],
    delta = {"reference": typical_costs["total_monthly"]},
    gauge = {
        "axis": {"range": [0, typical_costs["total_monthly"]*1.5]},
        "bar": {"color": "darkblue"},
        "steps": [
            {"range": [0, typical_costs["total_monthly"]*0.8], "color": "lightgreen"},
            {"range": [typical_costs["total_monthly"]*0.8, typical_costs["total_monthly"]*1.2], "color": "khaki"},
            {"range": [typical_costs["total_monthly"]*1.2, typical_costs["total_monthly"]*1.5], "color": "salmon"}
        ],
    },
    title = {"text": "BYN/мес"}
))
st.plotly_chart(fig_gauge, use_container_width=True)

# 2. Пузырьковая диаграмма
st.subheader("🔵 Распределение расходов по категориям")
categories = ["Электроэнергия","Вода","Канализация","Отопление","Фикс. платежи"]

bubble_df = pd.DataFrame({
    "Категория": categories*2,
    "Стоимость": [user_costs["electricity_cost"], user_costs["water_cost"], user_costs["sewage_cost"], user_costs["heating_cost"], user_costs["fixed_fees"]] +
                 [typical_costs["electricity_cost"], typical_costs["water_cost"], typical_costs["sewage_cost"], typical_costs["heating_cost"], typical_costs["fixed_fees"]],
    "Тип": ["Ваши"]*5 + ["Типовые"]*5
})

fig_bubble = go.Figure()

for t in bubble_df["Тип"].unique():
    df = bubble_df[bubble_df["Тип"]==t]
    fig_bubble.add_trace(go.Scatter(
        x=df["Категория"],
        y=df["Стоимость"],
        mode="markers+text",
        text=df["Стоимость"],
        textposition="top center",
        marker=dict(size=df["Стоимость"]*3, sizemode="area", opacity=0.6),
        name=t
    ))

fig_bubble.update_layout(height=500)
st.plotly_chart(fig_bubble, use_container_width=True)
