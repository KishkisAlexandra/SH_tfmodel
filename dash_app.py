# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Utility Benchmark — расширенный дашборд", page_icon="🏠", layout="wide")

# ------------------------
# Настройки / константы
# ------------------------
# Архетипы (придуманные названия и "факторы" потребления)
ARCHETYPES = {
    "Одинокий житель": 0.8,
    "Пара": 0.95,
    "Семья с детьми": 1.1,
    "Большая семья": 1.25
}

# eco/avg/int
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
    """Возвращает объёмы: электр-во, вода, канализация, отопление (Gcal/мес mid)"""
    elec = (coeffs["elec_base_kWh"] + coeffs["elec_per_person_kWh"]*occupants +
            coeffs["elec_per_m2_kWh"]*area_m2) * behavior_factor
    water = coeffs["water_per_person_m3"]*occupants*behavior_factor
    hot_water = water * coeffs["hot_water_fraction"]
    sewage = water
    # Отопление отключаем с апреля по октябрь
    if 4 <= month <= 10:
        heat_monthly = 0.0
    else:
        G_mid = coeffs["heating_Gcal_per_m2_season_mid"] * area_m2
        heat_monthly = G_mid / coeffs["heating_season_months"]
    return {
        "electricity_kWh": round(elec, 1),
        "water_m3": round(water, 2),
        "hot_water_m3": round(hot_water, 2),
        "sewage_m3": round(sewage, 2),
        "heating_Gcal_month_mid": round(heat_monthly, 3)
    }

def calculate_costs(volumes, tariffs, subsidy=False, subsidy_rate=0.2):
    """
    Вычисляет расходы по статьям. 
    subsidy=True применяет льготный тариф к отоплению и подогреву воды (иллюстративно).
    subsidy_rate — доля от полного тарифа (например 0.2 — 20% от полного).
    """
    # тарифы (копируем)
    t = tariffs.copy()
    # если субсидия — уменьшаем тариф на отопление и (логично) на расчёт Гкал для подогрева воды
    if subsidy:
        # Здесь мы применяем subsidy_rate к тарифу на отопление.
        # Это упрощение: реальные правила могут быть сложнее (доли по людям, преференции и т.п.)
        t["heating_BYN_per_Gcal"] = t["heating_BYN_per_Gcal"] * subsidy_rate

    elec_cost = volumes["electricity_kWh"] * t["electricity_BYN_per_kWh"]
    water_cost = volumes["water_m3"] * t["water_BYN_per_m3"]
    sewage_cost = volumes["sewage_m3"] * t["sewage_BYN_per_m3"]
    heat_cost = volumes["heating_Gcal_month_mid"] * t["heating_BYN_per_Gcal"]
    fixed = t.get("fixed_fees_BYN", 0.0)

    costs = {
        "Электроэнергия": round(elec_cost, 2),
        "Вода": round(water_cost, 2),
        "Канализация": round(sewage_cost, 2),
        "Отопление": round(heat_cost, 2),
        "Фикс. платежи": round(fixed, 2)
    }
    costs["Итого"] = round(sum(costs.values()), 2)
    return costs

# ------------------------
# UI: Sidebar (ввод)
# ------------------------
st.sidebar.header("Параметры жилья и расчёта")
month = st.sidebar.selectbox("Месяц", list(range(1,13)), format_func=lambda x:
                             ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"][x-1])
area_m2 = st.sidebar.number_input("Площадь, м²", min_value=10.0, max_value=500.0, value=90.0)
adults = st.sidebar.number_input("Взрослые", min_value=0, max_value=10, value=2)
children = st.sidebar.number_input("Дети", min_value=0, max_value=10, value=1)
occupants = int(adults + children)

behavior = st.sidebar.selectbox("Сценарий поведения", list(SCENARIOS.keys()), index=1)
behavior_factor = SCENARIOS[behavior]

archetype_name = st.sidebar.selectbox("Сравнить с профилем (архетип)", list(ARCHETYPES.keys()), index=3)
archetype_factor = ARCHETYPES[archetype_name]

# льготный тариф
st.sidebar.markdown("---")
use_subsidy = st.sidebar.checkbox("Рассчитывать по льготному тарифу (социальные/адресные льготы)")
if use_subsidy:
    st.sidebar.caption("Применяется снижающий коэффициент к тарифу на отопление (иллюстративно).")
    subsidy_rate = st.sidebar.slider("Доля от полного тарифа (чего списывается) — subsidy_rate", 0.0, 1.0, 0.2, 0.05)
else:
    subsidy_rate = 1.0

st.sidebar.markdown("---")
st.sidebar.write("Тарифы (BYN) — можно менять")
t_elec = st.sidebar.number_input("Электроэнергия BYN/kWh", value=DEFAULT_TARIFFS["electricity_BYN_per_kWh"], format="%.6f")
t_water = st.sidebar.number_input("Вода BYN/m³", value=DEFAULT_TARIFFS["water_BYN_per_m3"], format="%.6f")
t_sewage = st.sidebar.number_input("Канализация BYN/m³", value=DEFAULT_TARIFFS["sewage_BYN_per_m3"], format="%.6f")
t_heating = st.sidebar.number_input("Отопление BYN/Gcal", value=DEFAULT_TARIFFS["heating_BYN_per_Gcal"], format="%.2f")
t_fixed = st.sidebar.number_input("Фикс. платежи BYN/мес", value=DEFAULT_TARIFFS["fixed_fees_BYN"], format="%.2f")

tariffs = {
    "electricity_BYN_per_kWh": float(t_elec),
    "water_BYN_per_m3": float(t_water),
    "sewage_BYN_per_m3": float(t_sewage),
    "heating_BYN_per_Gcal": float(t_heating),
    "fixed_fees_BYN": float(t_fixed)
}

st.sidebar.markdown("---")
st.sidebar.caption("История расчетов можно сохранять и анализировать динамику (график без учёта отопления).")

# ------------------------
# Основные расчёты
# ------------------------
# пользователь
user_vol = calculate_volumes(area_m2, occupants, behavior_factor, month=month)
user_costs = calculate_costs(user_vol, tariffs, subsidy=use_subsidy, subsidy_rate=subsidy_rate)

# типовой (архетип) — берём поведение 'Средний' + архетип factor
typical_vol = calculate_volumes(area_m2, occupants, archetype_factor, month=month)
typical_costs = calculate_costs(typical_vol, tariffs, subsidy=False)

# диапазон eco/avg/int для визуализации (на той же площади/кол-ве людей)
eco_vol = calculate_volumes(area_m2, occupants, SCENARIOS["Экономный"], month=month)
eco_costs = calculate_costs(eco_vol, tariffs, subsidy=False)
int_vol = calculate_volumes(area_m2, occupants, SCENARIOS["Расточительный"], month=month)
int_costs = calculate_costs(int_vol, tariffs, subsidy=False)

# ------------------------
# Сохранение истории (session_state)
# ------------------------
if 'history' not in st.session_state:
    st.session_state.history = []  # каждый элемент: dict с keys: ts, month, total_with_heat, total_no_heat

def save_current():
    # собираем запись: month, totals (with heating), total without heating (для тренда)
    # Для total_without_heating пересчитаем без отопления:
    vol_no_heat = user_vol.copy()
    vol_no_heat["heating_Gcal_month_mid"] = 0.0
    costs_no_heat = calculate_costs(vol_no_heat, tariffs, subsidy=use_subsidy, subsidy_rate=subsidy_rate)
    rec = {
        "timestamp": datetime.utcnow().isoformat(),
        "month": month,
        "total_with_heat": user_costs["Итого"],
        "total_no_heat": costs_no_heat["Итого"],
        "area_m2": area_m2,
        "occupants": occupants,
        "profile": behavior,
        "archetype": archetype_name
    }
    st.session_state.history.append(rec)
    st.success("Результат сохранён в историю.")

st.header("🏠 Результаты расчёта (быстрый обзор)")
st.subheader(f"Сравнение с профилем: «{archetype_name}»")

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown(f"**Ваш счёт:** {user_costs['Итого']} BYN")
    st.markdown(f"**Типовой счёт (архетип «{archetype_name}»):** {typical_costs['Итого']} BYN")
    diff = user_costs["Итого"] - typical_costs["Итого"]
    pct = (diff / typical_costs["Итого"]) * 100 if typical_costs["Итого"] != 0 else 0.0
    if diff > 0:
        st.markdown(f"**Аналитика:** Ваши расходы на **{pct:.1f}% выше**, чем у типового домохозяйства. 💡 Есть потенциал для экономии.")
    else:
        st.markdown(f"**Аналитика:** Ваши расходы на **{abs(pct):.1f}% ниже** типового домохозяйства. ✅ Отлично!")
    st.markdown("---")
    st.markdown("**Разбивка по категориям (BYN):**")
    cat_df = pd.DataFrame({
        "Категория": list(user_costs.keys())[:-1],
        "Ваши расходы": [user_costs[k] for k in list(user_costs.keys())[:-1]],
        "Типовые расходы": [typical_costs[k] for k in list(user_costs.keys())[:-1]],
    })
    # покажем таблицу компактно
    st.dataframe(cat_df.style.format({"Ваши расходы": "{:.2f}", "Типовые расходы": "{:.2f}"}), height=220)

    # Кнопка сохранения в историю
    if st.button("Сохранить результат в историю"):
        save_current()

with col2:
    st.metric("Итого (BYN/мес) — Вы", f"{user_costs['Итого']}")
    st.metric("Итого (BYN/мес) — Типовое", f"{typical_costs['Итого']}")
    st.metric("Сценарий поведения", f"{behavior}")
    st.metric("Архетип сравнения", f"{archetype_name}")

st.markdown("---")

# ------------------------
# Визуализация: цветной групповой бар (Plotly)
# ------------------------
st.subheader("Графическое сравнение расходов (цвета: ваши / типовые / диапазон eco..int)")

# Построим df для bar chart: для каждой категории — eco/you/typical/int
categories = list(user_costs.keys())[:-1]  # исключаем 'Итого'
rows = []
for cat in categories:
    rows.append({"Категория": cat, "Тип": "Экономный (eco)", "BYN": eco_costs[cat]})
    rows.append({"Категория": cat, "Тип": "Ваши", "BYN": user_costs[cat]})
    rows.append({"Категория": cat, "Тип": "Типовое (архетип)", "BYN": typical_costs[cat]})
    rows.append({"Категория": cat, "Тип": "Расточительный (int)", "BYN": int_costs[cat]})

plot_df = pd.DataFrame(rows)

fig = px.bar(plot_df, x="Категория", y="BYN", color="Тип", barmode="group",
             color_discrete_map={
                 "Экономный (eco)": "lightgreen",
                 "Ваши": "royalblue",
                 "Типовое (архетип)": "orange",
                 "Расточительный (int)": "salmon"
             })
fig.update_layout(height=520, legend_title_text="Сравнение")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ------------------------
# Динамика: история и график по месяцам (без отопления)
# ------------------------
st.subheader("Динамика сохранённых расчётов (тренд расходов без отопления)")

if st.session_state.history:
    hist_df = pd.DataFrame(st.session_state.history)
    # Преобразуем месяц в порядковый для сортировки, добавим метку времени
    hist_df['ts'] = pd.to_datetime(hist_df['timestamp'])
    hist_df = hist_df.sort_values('ts')
    # линия по total_no_heat
    fig_trend = px.line(hist_df, x='ts', y='total_no_heat', markers=True,
                        title="Тренд: расходы без учёта отопления (BYN)")
    fig_trend.update_xaxes(title_text="Дата сохранения")
    fig_trend.update_yaxes(title_text="BYN (без отопления)")
    st.plotly_chart(fig_trend, use_container_width=True)

    # Таблица и экспорт CSV
    st.dataframe(hist_df[['ts','month','total_with_heat','total_no_heat','area_m2','occupants','profile','archetype']].rename(columns={
        'ts':'Дата сохранения','month':'Месяц','total_with_heat':'Итого (с отопл.)',
        'total_no_heat':'Итого (без отопл.)','area_m2':'Площадь','occupants':'Проживают','profile':'Сценарий','archetype':'Архетип'
    }), height=240)

    csv = hist_df.to_csv(index=False).encode('utf-8')
    st.download_button("Скачать историю (CSV)", data=csv, file_name=f"utility_history_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv", mime="text/csv")
else:
    st.info("История пуста — сохраните расчёт кнопкой 'Сохранить результат в историю'.")

st.markdown("---")

# ------------------------
# Блок рекомендаций (анализ по статьям)
# ------------------------
st.subheader("Рекомендации и возможные причины перерасхода")

recs = []
threshold_pct = 15.0  # порог эффективности (в процентах)

for cat in categories:
    user_v = user_costs[cat]
    typ_v = typical_costs[cat] if typical_costs[cat] != 0 else 1e-6
    diff_pct = (user_v - typ_v) / typ_v * 100
    if diff_pct >= threshold_pct:
        # составим рекомендацию
        if cat == "Электроэнергия":
            recs.append(f"🔌 Электроэнергия: ваши расходы на {diff_pct:.0f}% выше. Проверьте: наличие энергозатратных приборов (обогреватели, старые холодильники), режимы работы, лампы — замените на LED.")
        elif cat == "Вода":
            recs.append(f"🚿 Вода: ваши расходы на {diff_pct:.0f}% выше. Проверьте протечки, длительность душа, старые смесители и экономьте горячую воду.")
        elif cat == "Канализация":
            recs.append(f"🛁 Канализация: повышенные объёмы обычно следуют за большим расходом воды — проверьте семейные привычки и утечки.")
        elif cat == "Отопление":
            recs.append(f"🔥 Отопление: расходы выше на {diff_pct:.0f}%. Возможные причины: большие площади, слабое утепление, длительный прогрев. Рассмотрите утепление, регуляторы температуры, программируемые термостаты.")
        else:
            recs.append(f"ℹ️ {cat}: расходы выше на {diff_pct:.0f}%. Посмотрите детально счета и нормативы.")
# Если нет значимых рекомендаций:
if not recs:
    st.success("По ключевым категориям значимого перерасхода не обнаружено. Отличная работа!")

# Отобразим рекомендации (если есть)
for r in recs:
    st.markdown(r)

st.markdown("---")
st.caption("Примечание: функции льгот (субсидий) реализованы упрощённо — реальные правила зависят от законов/постановлений и адресной поддержки. Для точного расчёта льгот требуется интеграция с локальными нормативами и документами (например, Минэкономики). :contentReference[oaicite:1]{index=1}")
