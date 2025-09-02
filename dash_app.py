import streamlit as st
import pandas as pd
import plotly.express as px
from dataclasses import dataclass

# --- Входные данные пользователя ---
@dataclass
class UserInput:
    month: str  # "01".."12"
    area: float  # площадь квартиры (м²)
    adults: int
    children: int
    is_privileged: bool  # льгота (да/нет)
    house_age_category: str  # "new" | "medium" | "old"
    has_elevator: bool


# --- Тарифы для Минска (2025) ---
TARIFFS = {
    # источник: https://economy.gov.by/ru/inform_vop-ru/
    "heating_Gcal": 24.72,       # BYN/Гкал (субсидированный)
    "heating_Gcal_full": 134.94, # экономически обоснованный

    # источник: https://www.energosbyt.by/ru/info-potrebitelyam/fiz-l/tarify
    "electricity_kWh": 0.2412,   # BYN/кВт·ч (одноставочный)

    # источник: https://minskvodokanal.by/person/tariffs/
    "water_m3": 1.5216,          # BYN/м³
    "sewage_m3": 1.6267,         # BYN/м³

    # ЖКХ фиксированные
    "waste_per_person": 3.35,    # BYN/чел (по нормативу ТКО)
    "maintenance_m2": 0.1932,    # BYN/м²
    "capital_repair_m2": 0.2536, # BYN/м²
    "lift_m2": 0.0902,           # BYN/м²
    "lighting_m2": 0.0366,       # BYN/м²
}

HEATING_MONTHS = ["11", "12", "01", "02", "03"]

HOUSE_COEFS = {
    "new": {"heating": 1.0, "electricity": 1.0},
    "medium": {"heating": 1.05, "electricity": 1.05},
    "old": {"heating": 1.1, "electricity": 1.05},
}

REALISM_UPLIFT = 1.07  # +7% для "среднего соседа"


# --- Расчёт ---
def calculate_costs(user: UserInput):
    people = user.adults + user.children
    area = user.area

    # отопление (очень упрощённо: считаем 0.018 Гкал на 1 м² в месяц отопления)
    heating = 0
    if user.month in HEATING_MONTHS:
        gcal = area * 0.018
        tariff = TARIFFS["heating_Gcal_full"]
        if user.is_privileged:
            tariff = TARIFFS["heating_Gcal"]
        heating = gcal * tariff

    # электроэнергия (норматив: 150 кВт·ч на семью + 50 на каждого доп.чел)
    base_kWh = 150 + (people - 1) * 50
    electricity = base_kWh * TARIFFS["electricity_kWh"]

    # вода и канализация (по 3 м³ на чел)
    water = people * 3 * TARIFFS["water_m3"]
    sewage = people * 3 * TARIFFS["sewage_m3"]

    # ТКО
    waste = people * TARIFFS["waste_per_person"]

    # обслуживание
    maintenance = area * TARIFFS["maintenance_m2"]
    cap_repair = area * TARIFFS["capital_repair_m2"]
    lift = area * TARIFFS["lift_m2"] if user.has_elevator else 0
    lighting = area * TARIFFS["lighting_m2"]

    normative = heating + electricity + water + sewage + waste + maintenance + cap_repair + lift + lighting

    # --- Средний сосед ---
    coefs = HOUSE_COEFS[user.house_age_category]
    heating_corr = heating * coefs["heating"]
    electricity_corr = electricity * coefs["electricity"]

    neighbor = (
        heating_corr + electricity_corr + water + sewage + waste + maintenance + cap_repair + lift + lighting
    ) * REALISM_UPLIFT

    return {"normative": round(normative, 2), "neighbor": round(neighbor, 2)}


# --- Streamlit интерфейс ---
st.title("🏠 Сравнение коммунальных платежей — Минск")

col1, col2 = st.columns(2)
with col1:
    month = st.selectbox("Месяц", [f"{i:02}" for i in range(1, 13)])
    area = st.number_input("Площадь квартиры (м²)", 20, 200, 60)
    adults = st.number_input("Взрослые", 1, 6, 2)
    children = st.number_input("Дети", 0, 5, 1)
with col2:
    is_privileged = st.checkbox("Льготный тариф")
    house_age_category = st.selectbox("Возраст дома", ["new", "medium", "old"])
    has_elevator = st.checkbox("Лифт в доме", value=True)

user = UserInput(
    month=month,
    area=area,
    adults=adults,
    children=children,
    is_privileged=is_privileged,
    house_age_category=house_age_category,
    has_elevator=has_elevator,
)

calc = calculate_costs(user)

# --- Реальные данные пользователя ---
st.subheader("📊 Введите свои реальные расходы")
real_electricity = st.number_input("Электроэнергия (BYN)", 0.0, 500.0, 50.0)
real_water = st.number_input("Вода (BYN)", 0.0, 300.0, 20.0)
real_heating = st.number_input("Отопление (BYN)", 0.0, 500.0, 80.0)
real_sewage = st.number_input("Канализация (BYN)", 0.0, 300.0, 15.0)
real_fixed = st.number_input("Фиксированные платежи (BYN)", 0.0, 200.0, 30.0)

real_total = real_electricity + real_water + real_heating + real_sewage + real_fixed

# --- Визуализация ---
df = pd.DataFrame(
    {
        "Категория": ["Идеальный расчёт", "Ваши расходы", "Средний сосед"],
        "Сумма (BYN)": [calc["normative"], real_total, calc["neighbor"]],
    }
)

fig = px.bar(df, x="Категория", y="Сумма (BYN)", color="Категория", text="Сумма (BYN)")
fig.update_traces(textposition="outside")

st.plotly_chart(fig, use_container_width=True)
