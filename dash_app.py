import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Utility Benchmark Dashboard",
    page_icon="🏠",
    layout="wide"
)

# ---- Типовые профили ----
profiles = {
    "Одинокий житель": {"factor": 0.8},
    "Пара": {"factor": 0.95},
    "Семья с детьми": {"factor": 1.1},
    "Большая семья": {"factor": 1.2}
}

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

# ---- Функции ----
def calculate_volumes(area_m2, occupants, factor, coeffs=DEFAULT_COEFFS, month=1):
    elec = (coeffs["elec_base_kWh"] +
            coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2) * factor
    water = coeffs["water_per_person_m3"]*occupants*factor
    sewage = water
    # отопление отключено с апреля по октябрь
    if 4 <= month <= 10:
        heat_monthly = 0
    else:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"]*area_m2
        heat_monthly = G_mid / coeffs["heating_season_months"]
    return {
        "electricity_kWh": round(elec,1),
        "water_m3": round(water,2),
        "sewage_m3": round(sewage,2),
        "heating_Gcal_month_mid": round(heat_monthly,3)
    }

def calculate_costs(volumes, tariffs):
    elec_cost = volumes["electricity_kWh"]*tariffs["electricity_BYN_per_kWh"]
    water_cost = volumes["water_m3"]*tariffs["water_BYN_per_m3"]
    sewage_cost = volumes["sewage_m3"]*tariffs["sewage_BYN_per_m3"]
    heat_cost = volumes["heating_Gcal_month_mid"]*tariffs["heating_BYN_per_Gcal"]
    fixed = tariffs.get("fixed_fees_BYN",0)
    costs = {
        "Электроэнергия": round(elec_cost,2),
        "Вода": round(water_cost,2),
        "Канализация": round(sewage_cost,2),
        "Отопление": round(heat_cost,2),
        "Фикс. платежи": round(fixed,2)
    }
    costs["Итого"] = round(sum(costs.values()),2)
    return costs

# ---- Sidebar ----
with st.sidebar:
    st.header("Ваши параметры")
    month = st.selectbox("Месяц", list(range(1,13)), format_func=lambda x:
                         ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
    area_m2 = st.number_input("Площадь, м²", min_value=10.0, max_value=500.0, value=80.0)
    occupants = st.number_input("Число жильцов", min_value=1, max_value=10, value=4)
    profile_name = st.selectbox("Сравнить с профилем", list(profiles.keys()), index=3)

# ---- Расчёты ----
user_volumes = calculate_volumes(area_m2, occupants, 1.0, month=month)
user_costs = calculate_costs(user_volumes, DEFAULT_TARIFFS)

typical_volumes = calculate_volumes(area_m2, occupants, profiles[profile_name]["factor"], month=month)
typical_costs = calculate_costs(typical_volumes, DEFAULT_TARIFFS)

# ---- Аналитика ----
st.title("📊 Результаты сравнения")

diff = user_costs["Итого"] - typical_costs["Итого"]
percent = (diff / typical_costs["Итого"]) * 100

if diff > 0:
    verdict = f"Ваши расходы на **{percent:.1f}% выше**, чем у типового домохозяйства."
    advice = "💡 Есть потенциал для экономии."
else:
    verdict = f"Ваши расходы на **{-percent:.1f}% ниже**, чем у типового домохозяйства."
    advice = "✅ Вы тратите меньше, чем большинство."

st.markdown(f"""
### Мы сравнили вас с профилем: **{profile_name}**

- Ваш счёт: **{user_costs['Итого']} BYN**
- Типовой счёт: **{typical_costs['Итого']} BYN**

**Аналитика:**  
{verdict}  
{advice}
""")

# ---- Визуализация ----
st.subheader("Сравнение расходов по категориям")

df_compare = pd.DataFrame({
    "Категория": list(user_costs.keys())[:-1],
    "Ваши расходы": list(user_costs.values())[:-1],
    "Типовые расходы": list(typical_costs.values())[:-1]
})

df_melted = df_compare.melt(id_vars="Категория", var_name="Тип", value_name="BYN")

fig = px.bar(
    df_melted,
    x="Категория", y="BYN",
    color="Тип",
    barmode="group",
    text="BYN",
    color_discrete_map={"Ваши расходы": "royalblue", "Типовые расходы": "orange"}
)

fig.update_layout(height=500)
st.plotly_chart(fig, use_container_width=True)
