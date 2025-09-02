# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Utility Benchmark — дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Константы
# ------------------------
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

# Корректировки для "Среднего соседа"
HOUSE_COEFS = {
    "Новый": {"heating": 1.0, "electricity": 1.0},
    "Средний": {"heating": 1.05, "electricity": 1.05},
    "Старый": {"heating": 1.1, "electricity": 1.05},
}
REALISM_UPLIFT = 1.07

# Порядок категорий — использую везде, чтобы не было рассинхрона
CATEGORIES = ["Электроэнергия", "Вода", "Канализация", "Отопление", "Фикс. платежи"]

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
        "Электроэнергия": round(elec,1),          # в кВт·ч (объём)
        "Вода": round(water,2),                   # в м³
        "Горячая вода": round(hot_water,2),
        "Канализация": round(sewage,2),           # в м³
        "Отопление": round(heat_monthly,3)        # в Гкал
    }

def calculate_costs_from_volumes(volumes, tariffs, subsidy=False, subsidy_rate=0.2):
    """
    Принимает volumes (как из calculate_volumes) и возвращает dict с ключами:
    'Электроэнергия','Вода','Канализация','Отопление','Фикс. платежи','Итого'
    (в BYN)
    """
    t = tariffs.copy()
    if subsidy:
        t["heating_BYN_per_Gcal"] *= subsidy_rate

    # electricity volume is in kWh
    elec_cost = volumes["Электроэнергия"] * t["electricity_BYN_per_kWh"]
    water_cost = volumes["Вода"] * t["water_BYN_per_m3"]
    sewage_cost = volumes["Канализация"] * t["sewage_BYN_per_m3"]
    heat_cost = volumes["Отопление"] * t["heating_BYN_per_Gcal"]
    fixed = t.get("fixed_fees_BYN", 0.0)

    costs = {
        "Электроэнергия": round(elec_cost,2),
        "Вода": round(water_cost,2),
        "Канализация": round(sewage_cost,2),
        "Отопление": round(heat_cost,2),
        "Фикс. платежи": round(fixed,2)
    }
    costs["Итого"] = round(sum(costs.values()),2)
    return costs

def apply_neighbor_adjustment(volumes, tariffs, house_category):
    """Коррекция расходов для Среднего соседа
       volumes — словарь объёмов (из calculate_volumes),
       tariffs — словарь тарифов,
       house_category — ключ из HOUSE_COEFS.
    """
    coefs = HOUSE_COEFS.get(house_category, {"heating":1.0,"electricity":1.0})
    # создаём копию volumes и корректируем объёмы (электричество и отопление)
    vol_adj = volumes.copy()
    # электроэнергия в кВт·ч масштабируем
    vol_adj["Электроэнергия"] = vol_adj["Электроэнергия"] * coefs["electricity"]
    # отопление в Гкал масштабируем
    vol_adj["Отопление"] = vol_adj["Отопление"] * coefs["heating"]

    # пересчитаем стоимость по скорректированным объёмам
    neighbor_costs = calculate_costs_from_volumes(vol_adj, tariffs, subsidy=False)
    # добавим реалистичный uplift (5-10% -> мы используем 7%)
    neighbor_costs = {k: round(v * REALISM_UPLIFT, 2) for k, v in neighbor_costs.items()}
    return neighbor_costs

# ------------------------
# Sidebar: параметры семьи
# ------------------------
st.sidebar.header("Параметры семьи")
month = st.sidebar.selectbox("Месяц", list(range(1,13)),
                             format_func=lambda x: ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", 10.0, 500.0, 90.0)
adults = st.sidebar.number_input("Взрослые", 0,10,2)
children = st.sidebar.number_input("Дети", 0,10,1)
occupants = adults + children
scenario = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[scenario]

# Категория дома
house_category = st.sidebar.selectbox("Категория дома", list(HOUSE_COEFS.keys()), index=1)

# Галочка льготного тарифа
st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Использовать льготный тариф")
if use_subsidy:
    subsidy_rate = st.sidebar.slider("Доля от полного тарифа", 0.0, 1.0, 0.2, 0.05)
else:
    subsidy_rate = 1.0

# Расширенные настройки тарифа (оставляем возможность менять)
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
# Ввод реальных расходов (явно BYN)
# ------------------------
st.header("📊 Введите ваши реальные расходы за месяц (BYN)")
with st.expander("Показать поля для ручного ввода"):
    # порядок строго соответствует CATEGORIES
    user_real = {
        "Электроэнергия": st.number_input("Электроэнергия BYN", min_value=0.0, value=0.0, step=1.0),
        "Вода": st.number_input("Вода BYN", min_value=0.0, value=0.0, step=0.1),
        "Канализация": st.number_input("Канализация BYN", min_value=0.0, value=0.0, step=0.1),
        "Отопление": st.number_input("Отопление BYN", min_value=0.0, value=0.0, step=0.1),
        "Фикс. платежи": st.number_input("Фикс. платежи BYN", min_value=0.0, value=0.0, step=0.1)
    }
user_real["Итого"] = round(sum(user_real[k] for k in CATEGORIES), 2)

# ------------------------
# Расчёт идеального (модель) и среднего соседа
# ------------------------
ideal_vol = calculate_volumes(area_m2, occupants, behavior_factor, coeffs=DEFAULT_COEFFS, month=month)
# идеальные расходы по тарифам (учитываем льготу на отопление, если отмечено)
ideal_costs = calculate_costs_from_volumes(ideal_vol, tariffs, subsidy=use_subsidy, subsidy_rate=subsidy_rate)

# средний сосед: берём factor=1.0 (усреднённый по поведению), затем корректируем по дому и uplift
neighbor_vol = calculate_volumes(area_m2, occupants, 1.0, coeffs=DEFAULT_COEFFS, month=month)
neighbor_costs = apply_neighbor_adjustment(neighbor_vol, tariffs, house_category)

# ------------------------
# Визуализация и таблицы
# ------------------------
st.header("🏠 Сравнение расходов")
col1, col2 = st.columns([2, 1])

with col1:
    st.metric("Идеальный расчёт по нормативам, BYN", f"{ideal_costs['Итого']:.2f}")
    st.metric("Ваши реальные расходы, BYN", f"{user_real['Итого']:.2f}")
    st.metric("Средний сосед, BYN", f"{neighbor_costs['Итого']:.2f}")

    # Процент отклонения (защита от деления на 0)
    ideal_total = ideal_costs.get("Итого", 0.0) or 0.0
    neighbor_total = neighbor_costs.get("Итого", 0.0) or 0.0
    real_total = user_real["Итого"]

    diff_real = round((real_total/ideal_total-1)*100,1) if ideal_total>0 else 0.0
    diff_neighbor = round((real_total/neighbor_total-1)*100,1) if neighbor_total>0 else 0.0

    st.info(f"Ваши реальные расходы на {diff_real}% {'выше' if diff_real>0 else 'ниже'} нормативного расчёта.")
    st.info(f"Ваши реальные расходы на {diff_neighbor}% {'выше' if diff_neighbor>0 else 'ниже'} среднего соседа.")

with col2:
    # Таблица детализации (стоимости)
    detail_df = pd.DataFrame({
        "Категория": CATEGORIES,
        "Идеальный расчёт (BYN)": [ideal_costs[c] for c in CATEGORIES],
        "Ваши реальные данные (BYN)": [user_real[c] for c in CATEGORIES],
        "Средний сосед (BYN)": [neighbor_costs[c] for c in CATEGORIES],
    })
    st.dataframe(detail_df.style.format({
        "Идеальный расчёт (BYN)": "{:.2f}",
        "Ваши реальные данные (BYN)": "{:.2f}",
        "Средний сосед (BYN)": "{:.2f}"
    }), height=260)

st.markdown("---")
# График: группированная столбчатая диаграмма — все три показателя
plot_df = pd.DataFrame({
    "Категория": CATEGORIES * 3,
    "Тип": (["Идеальный расчёт"] * len(CATEGORIES)) + (["Ваши реальные данные"] * len(CATEGORIES)) + (["Средний сосед"] * len(CATEGORIES)),
    "BYN": [ideal_costs[c] for c in CATEGORIES] + [user_real[c] for c in CATEGORIES] + [neighbor_costs[c] for c in CATEGORIES]
})

fig = px.bar(plot_df, x="Категория", y="BYN", color="Тип", barmode="group",
             color_discrete_map={"Идеальный расчёт":"#636EFA","Ваши реальные данные":"#00CC96","Средний сосед":"#EF553B"},
             text="BYN")
fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
fig.update_layout(yaxis_title="BYN / месяц", legend_title_text="Показатель", uniformtext_minsize=8)
st.plotly_chart(fig, use_container_width=True)

# ------------------------
# Рекомендации
# ------------------------
st.header("💡 Рекомендации")
for cat in ["Электроэнергия","Вода","Отопление","Канализация"]:
    if user_real[cat] > ideal_costs[cat]:
        st.write(f"- Перерасход по {cat}: проверьте приборы и привычки, возможна экономия.")
    else:
        st.write(f"- {cat}: расход в пределах или ниже нормативного уровня.")

# Финальное замечание
st.caption("Исправлено: электроэнергия теперь явно учитывается во всех расчётах (идеал, сосед, реальные данные).")
