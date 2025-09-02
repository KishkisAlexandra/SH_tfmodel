# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — Минск с нормативами", page_icon="🏠", layout="wide")

# ------------------------
# Новые нормативы Минска
# ------------------------
SCENARIOS = {"Экономный": 0.85, "Средний": 1.0, "Расточительный": 1.25}

DEFAULT_TARIFFS = {
    "electricity_BYN_per_kWh": 0.2412,  # актуально
    "water_BYN_per_m3": 1.7858,
    "sewage_BYN_per_m3": 0.9586,
    "heating_BYN_per_Gcal": 135.0,
    "fixed_fees_BYN": 5.0
}

DEFAULT_COEFFS = {
    "elec_base_kWh": 0.0,
    "elec_per_person_kWh": 75.0,          # среднее по нормативам
    "elec_per_m2_kWh": 0.0,
    "water_per_person_m3": 4.2,           # норматив
    "hot_water_fraction": 0.45,
    "heating_Gcal_per_m2_season_mid": 0.10,
    "heating_season_months": 7.0
}

HOUSE_COEFS = {
    "Новый": {"heating": 1.0, "electricity": 1.0},
    "Средний": {"heating": 1.05, "electricity": 1.05},
    "Старый": {"heating": 1.10, "electricity": 1.05},
}
REALISM_UPLIFT = 1.07

# ------------------------
# Функции расчёта (без изменений)
# ------------------------
def calculate_volumes(area, occupants, factor, coeffs=DEFAULT_COEFFS, month=1):
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"] * occupants
            + coeffs["elec_per_m2_kWh"] * area) * factor
    water = coeffs["water_per_person_m3"] * occupants * factor
    hot_water = water * coeffs["hot_water_fraction"]
    sewage = water
    if 4 <= month <= 10:
        heat = 0.0
    else:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"] * area
        heat = G_mid / coeffs["heating_season_months"]
    return {
        "Электроэнергия (кВт·ч)": round(elec, 1),
        "Вода (м³)": round(water, 2),
        "Горячая вода (м³)": round(hot_water, 2),
        "Канализация (м³)": round(sewage, 2),
        "Отопление (Gcal)": round(heat, 3),
    }

def calculate_costs(volumes, tariffs, subsidy=False, subsidy_rate=1.0):
    t = tariffs.copy()
    if subsidy:
        t["heating_BYN_per_Gcal"] *= subsidy_rate
    e = volumes["Электроэнергия (кВт·ч)"] * t["electricity_BYN_per_kWh"]
    w = volumes["Вода (м³)"] * t["water_BYN_per_m3"]
    s = volumes["Канализация (м³)"] * t["sewage_BYN_per_m3"]
    h = volumes["Отопление (Gcal)"] * t["heating_BYN_per_Gcal"]
    f = t.get("fixed_fees_BYN", 0.0)
    costs = {"Электроэнергия": round(e,2), "Вода": round(w,2),
             "Канализация": round(s,2), "Отопление": round(h,2),
             "Фикс. платежи": round(f,2)}
    costs["Итого"] = round(sum(costs.values()),2)
    return costs

def apply_neighbor_adjustment(volumes, tariffs, house_cat):
    coefs = HOUSE_COEFS[house_cat]
    vol2 = volumes.copy()
    vol2["Электроэнергия (кВт·ч)"] *= coefs["electricity"]
    vol2["Отопление (Gcal)"] *= coefs["heating"]
    nb = calculate_costs(vol2, tariffs, subsidy=False)
    return {k: round(v * REALISM_UPLIFT,2) for k,v in nb.items()}

# ------------------------
# Sidebar: ввод
# ------------------------
st.sidebar.header("Параметры семьи")
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda m: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][m-1])
area = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,1)
occupants = adults + children
scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
factor = SCENARIOS[scenario]
house_cat = st.sidebar.selectbox("Возраст дома", list(HOUSE_COEFS.keys()), index=1)
use_subsidy = st.sidebar.checkbox("Льготный тариф")
subsidy_rate = st.sidebar.slider("Доля тарифа",0.0,1.0,0.2,0.05) if use_subsidy else 1.0

with st.sidebar.expander("Расширенные тарифы"):
    t_e = st.number_input("Электро BYN/kWh", value=DEFAULT_TARIFFS["electricity_BYN_per_kWh"], format="%.4f")
    t_w = st.number_input("Вода BYN/m³", value=DEFAULT_TARIFFS["water_BYN_per_m3"], format="%.4f")
    t_s = st.number_input("Канал-плата BYN/m³", value=DEFAULT_TARIFFS["sewage_BYN_per_m3"], format="%.4f")
    t_h = st.number_input("Отопление BYN/Gcal", value=DEFAULT_TARIFFS["heating_BYN_per_Gcal"], format="%.2f")
    t_f = st.number_input("Фикс. BYN", value=DEFAULT_TARIFFS["fixed_fees_BYN"], format="%.2f")
tariffs = {#"electricity_BYN_per_kWh": t_e, ...
    "electricity_BYN_per_kWh": t_e,
    "water_BYN_per_m3": t_w,
    "sewage_BYN_per_m3": t_s,
    "heating_BYN_per_Gcal": t_h,
    "fixed_fees_BYN": t_f
}

# ------------------------
# Реальные расходы
# ------------------------
st.header("Ваши реальные расходы")
real = {k: st.number_input(f"{k} BYN", min_value=0.0, value=0.0) for k in ["Электроэнергия","Вода","Канализация","Отопление","Фикс. платежи"]}
real["Итого"] = sum(real.values())

# ------------------------
# Расчёт норматива и соседа
# ------------------------
ideal_vol = calculate_volumes(area, occupants, factor, month=month)
ideal_costs = calculate_costs(ideal_vol, tariffs, subsidy=use_subsidy, subsidy_rate=subsidy_rate)
nbr_vol = calculate_volumes(area, occupants, 1.0, month=month)
nbr_costs = apply_neighbor_adjustment(nbr_vol, tariffs, house_cat)

# ------------------------
# График и сравнение
# ------------------------
st.header("Сравнение: норматив — вы — средний сосед")
df = pd.DataFrame({
    "Показатель":["Идеал","Вы","Сосед"],
    "Итого":[ideal_costs["Итого"], real["Итого"], nbr_costs["Итого"]]
})
fig = px.bar(df, x="Показатель", y="Итого", color="Показатель", text="Итого")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Процент отклонения")
st.write(f"От нормы: {((real['Итого']/ideal_costs['Итого']-1)*100):.1f}%")
st.write(f"От соседа: {((real['Итого']/nbr_costs['Итого']-1)*100):.1f}%")
