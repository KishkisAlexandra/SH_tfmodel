# app.py
import streamlit as st
import pandas as pd
from dataclasses import dataclass

# ------------------------
# Новые тарифы и настройки
# ------------------------
@dataclass
class UserInput:
    month: str
    area: float
    adults: int
    children: int
    is_privileged: bool
    house_age_category: str  # "new" | "medium" | "old"
    has_elevator: bool

TARIFFS = {
    "water_m3": 1.55,
    "water_norm_m3": 4.2,
    "electricity_kwh": 0.2412,
    "electricity_norm_kwh": 75,
    "heating": 1.0,
    "maintenance": 0.5,
    "waste": 2.0,
    "elevator": 1.0,
}

HEATING_MONTHS = ["11", "12", "01", "02", "03"]

HOUSE_COEFS = {
    "new": {"heating": 1.0, "electricity": 1.0},
    "medium": {"heating": 1.05, "electricity": 1.05},
    "old": {"heating": 1.1, "electricity": 1.05},
}

REALISM_UPLIFT = 1.07

def calculate_costs(user: UserInput):
    people = user.adults + user.children
    heating = user.area * TARIFFS["heating"] if user.month in HEATING_MONTHS else 0
    water = people * TARIFFS["water_norm_m3"] * TARIFFS["water_m3"]
    electricity = people * TARIFFS["electricity_norm_kwh"] * TARIFFS["electricity_kwh"]
    maintenance = user.area * TARIFFS["maintenance"]
    waste = people * TARIFFS["waste"]
    elevator = people * TARIFFS["elevator"] if user.has_elevator else 0

    normative = heating + water + electricity + maintenance + waste + elevator
    if user.is_privileged:
        normative *= 0.5

    coefs = HOUSE_COEFS[user.house_age_category]
    heating_corr = heating * coefs["heating"]
    electricity_corr = electricity * coefs["electricity"]
    neighbor = (heating_corr + electricity_corr + water + maintenance + waste + elevator) * REALISM_UPLIFT

    return {
        "normative_total": round(normative, 2),
        "neighbor_total": round(neighbor, 2),
        "details": {
            "heating": round(heating, 2),
            "water": round(water, 2),
            "electricity": round(electricity, 2),
            "maintenance": round(maintenance, 2),
            "waste": round(waste, 2),
            "elevator": round(elevator, 2),
        }
    }

# ------------------------
# Streamlit интерфейс
# ------------------------
st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")
st.title("🏠 Utility Benchmark")

# Sidebar: ввод параметров
st.sidebar.header("Параметры семьи")
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0, 10, 2)
children = st.sidebar.number_input("Дети", 0, 10, 1)
privileged = st.sidebar.checkbox("Использовать льготный тариф")
house_category = st.sidebar.selectbox("Категория дома", ["new", "medium", "old"], index=1)
has_elevator = st.sidebar.checkbox("Есть ли лифт в доме?")

user_input = UserInput(
    month=f"{month:02d}",
    area=area,
    adults=adults,
    children=children,
    is_privileged=privileged,
    house_age_category=house_category,
    has_elevator=has_elevator
)

# ------------------------
# Расчёты
# ------------------------
result = calculate_costs(user_input)

# ------------------------
# Визуализация
# ------------------------
st.header("📊 Расчётные расходы")
st.metric("Нормативные расходы (BYN)", f"{result['normative_total']:.2f}")
st.metric("Средний сосед (BYN)", f"{result['neighbor_total']:.2f}")

# Таблица детализации
details_df = pd.DataFrame.from_dict(result['details'], orient='index', columns=["BYN"])
st.dataframe(details_df.style.format("{:.2f}"))

# Пример сравнения с ручным вводом
st.header("Введите реальные расходы, BYN")
user_real = {
    "heating": st.number_input("Отопление", 0.0),
    "water": st.number_input("Вода", 0.0),
    "electricity": st.number_input("Электроэнергия", 0.0),
    "maintenance": st.number_input("Содержание", 0.0),
    "waste": st.number_input("Вывоз мусора", 0.0),
    "elevator": st.number_input("Лифт", 0.0),
}
user_real_total = round(sum(user_real.values()), 2)
st.metric("Ваши реальные расходы (BYN)", f"{user_real_total:.2f}")
