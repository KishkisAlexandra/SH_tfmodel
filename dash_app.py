# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from PIL import Image
import pytesseract

st.set_page_config(page_title="Utility Benchmark — расширенный дашборд", page_icon="🏠", layout="wide")

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
    if 4 <= month <= 10:
        heat_monthly = 0.0
    else:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"] * area_m2
        heat_monthly = G_mid / coeffs["heating_season_months"]
    return {
        "electricity_kWh": round(elec,1),
        "water_m3": round(water,2),
        "hot_water_m3": round(hot_water,2),
        "sewage_m3": round(sewage,2),
        "heating_Gcal_month_mid": round(heat_monthly,3)
    }

def calculate_costs(volumes, tariffs, subsidy=False, subsidy_rate=0.2):
    t = tariffs.copy()
    if subsidy:
        t["heating_BYN_per_Gcal"] *= subsidy_rate
    elec_cost = volumes["electricity_kWh"] * t["electricity_BYN_per_kWh"]
    water_cost = volumes["water_m3"] * t["water_BYN_per_m3"]
    sewage_cost = volumes["sewage_m3"] * t["sewage_BYN_per_m3"]
    heat_cost = volumes["heating_Gcal_month_mid"] * t["heating_BYN_per_Gcal"]
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
# Sidebar: настройки
# ------------------------
st.sidebar.header("Параметры расчёта")
month = st.sidebar.selectbox("Месяц", list(range(1,13)), format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,1)
occupants = adults + children
behavior = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[behavior]
archetype_name = st.sidebar.selectbox("Сравнить с профилем (архетип)", list(ARCHETYPES.keys()), index=3)
archetype_factor = ARCHETYPES[archetype_name]

# Чекбокс льготного тарифа
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
# Два режима: параметры семьи / платежка
# ------------------------
st.header("Выберите режим расчёта")
mode = st.radio("Режим расчёта", ["Смоделировать по параметрам семьи", "По реальной платежке"])

if mode=="По реальной платежке":
    st.subheader("Загрузите фото вашей квитанции")
    uploaded_file = st.file_uploader("Выберите изображение", type=["png","jpg","jpeg"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Загруженная квитанция", use_column_width=True)
        # OCR распознавание текста
        text = pytesseract.image_to_string(image, lang="rus+eng")
        st.text_area("Распознанный текст платежки", text, height=200)
        st.info("Фактические цифры из платежки нужно извлечь вручную или через дополнительные парсеры.")

# ------------------------
# Расчёт по параметрам семьи
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
st.markdown(f"**Ваш счёт:** {user_costs['Итого']} BYN")
st
