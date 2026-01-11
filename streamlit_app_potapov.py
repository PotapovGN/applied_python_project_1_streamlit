import pandas as pd
import numpy as np
import streamlit as st
import warnings
import time
import requests
import datetime
import plotly.express as px
import plotly.graph_objects as go

warnings.filterwarnings('ignore')


# Функции для получения данных. Нет смысла асинхронности, так как будем выбирать конкретный один город
def get_response_season(response_dt):

    response_month = datetime.datetime.fromtimestamp(response_dt, tz=datetime.timezone.utc).month

    dict_month_x_season = {1: 'winter', 2: 'winter', 12: 'winter',
                           3: 'spring', 4: 'spring', 5: 'spring',
                           6: 'summer', 7: 'summer', 8: 'summer',
                           9: 'autumn', 10: 'autumn', 11: 'autumn'}

    return dict_month_x_season[response_month]


def get_current_weather(api_key, city):

    url = (f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric")
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        curent_temperature = data['main']['temp']
        curent_season = get_response_season(data['dt'])
        return curent_temperature, curent_season
    else:
        raise Exception(response.text)


def check_normality_of_temperature(api_key, city, df):

    # Плучаем температуру и сезон
    curent_temperature, curent_season = get_current_weather(api_key=api_key, city=city)

    # Фильтруем и считаем границы
    df_filtered = df.query("city == @city and season == @curent_season")
    lower_border = (df_filtered['temperature'].mean() - 2 * df_filtered['temperature'].std())
    upper_border = (df_filtered['temperature'].mean() + 2 * df_filtered['temperature'].std())

    if lower_border <= curent_temperature <= upper_border:
        result_txt = f"Текущая температура в городе {city} составляет {curent_temperature} и является нормальной для сезона {curent_season}. Границы нормальности: {round(lower_border, 2)} и {round(upper_border, 2)}"
    else:
        result_txt = f"Текущая температура в городе {city} составляет {curent_temperature} и НЕ ЯВЛЯЕТСЯ НОРМАЛЬНОЙ для сезона {curent_season}. Границы нормальности: {round(lower_border, 2)} и {round(upper_border, 2)}"

    return result_txt


# Функции для визуализации
def plot_temperature_dynamic(df_selected_city, window_size, show_raw, show_rolling, show_anomalies):

    # Копируем датафрейм на всякий случай
    df_filtered = df_selected_city.copy()

    # Скользящее среднее для сглаживания
    df_filtered['mean_temperature_rolling'] = df_filtered['temperature'].rolling(window=window_size, center=True).mean()

    # Рассчитываем среднее и std для сезона
    season_stats = df_filtered.groupby('season')['temperature'].agg(['mean', 'std']).reset_index()
    df_merged = df_filtered.merge(season_stats, on='season')
    df_merged['lower_border'] = df_merged['mean'] - 2 * df_merged['std']
    df_merged['upper_border'] = df_merged['mean'] + 2 * df_merged['std']

    # Выделяем аномалии
    df_merged['anomaly_flg'] = ((df_merged['temperature'] < df_merged['lower_border']) | (df_merged['temperature'] > df_merged['upper_border']))

    # Визуализируем
    fig = go.Figure()

    if show_raw:
        fig.add_trace(go.Scatter(x=df_merged['calendar_dt'],
                                 y=df_merged['temperature'],
                                 mode='lines',
                                 name='Температура'))
    if show_rolling:
        fig.add_trace(go.Scatter(x=df_merged['calendar_dt'],
                                 y=df_merged['mean_temperature_rolling'],
                                 mode='lines',
                                 name=f'Скользящее среднее ({window_size} дней)'))
    if show_anomalies:
        anomalies = df_merged[df_merged['anomaly_flg']]
        fig.add_trace(go.Scatter(x=anomalies['calendar_dt'],
                                 y=anomalies['temperature'],
                                 mode='markers',
                                 name='Аномалии'))

    fig.update_layout(title=f"Временной ряд температуры — {df_selected_city['city'].iloc[0]}",
                      xaxis_title="Дата",
                      yaxis_title="Температура",
                      hovermode="x unified")

    st.plotly_chart(fig, use_container_width=True)


def plot_bar_mean_temp_with_ci_each_season(df_season_stats, selected_city):

    df_filtered = df_season_stats.copy()

    df_filtered['ci95'] = 1.96 * df_filtered['std'] / np.sqrt(df_filtered['count'])

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_filtered['season'],
                         y=df_filtered['mean'],
                         error_y=dict(type='data', array=df_filtered['ci95'], visible=True),
                         name='Средняя температура'))
    
    fig.update_layout(title=f"Средняя температура по сезонам с 95% ДИ в {selected_city}",
                      xaxis_title="Сезон",
                      yaxis_title="Средняя температура")

    st.plotly_chart(fig, use_container_width=True)


# Главная функция
def main():

    # Название дашборда
    st.title("Анализ температурных данных и мониторинг текущей температуры через OpenWeatherMap API")

    # Получение файла (Добавить интерфейс для загрузки файла с историческими данными)
    uploaded_file = st.file_uploader("Загрузите файл с данными", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        df['calendar_dt'] = pd.to_datetime(df['timestamp'])
    else:
        st.stop()

    # Выбор города (Добавить интерфейс для выбора города из выпадающего списка)
    list_cities = list(df['city'].unique())
    selected_city = st.selectbox(label="Выберите город:",
                                 options=list_cities,
                                 index=None,
                                 placeholder="Выберите город")
    if selected_city is None:
        st.stop()
    df_selected_city = df.query("city == @selected_city")

    # Отобразить:
    # 1. Описательную статистику по историческим данным для города
    st.write(f"Описательная статистика для города {selected_city}")
    st.write(df_selected_city['temperature'].describe())

    # 2. Временной ряд температур с выделением аномалий
    st.write(f"Временной ряд температур с выделением аномалий для города {selected_city}")
    # Интерактивные параметры визуализации
    window_size = st.slider("Размер окна скользящего среднего (дней)", min_value=7, max_value=90, value=30)
    show_raw = st.checkbox("Показать температуру", True)
    show_rolling = st.checkbox("Показать скользящее среднее", True)
    show_anomalies = st.checkbox("Показать аномалии", True)
    plot_temperature_dynamic(df_selected_city, window_size, show_raw, show_rolling, show_anomalies)

    # 3. Сезонные профили с указанием среднего и стандартного отклонения
    df_season_stats = df_selected_city.groupby("season")['temperature'].agg(['mean', 'std', 'count']).reset_index()
    st.write(df_season_stats)
    # Дополнительно: визуализируем столбчатую диаграмму температуры по сезонам с дов интервалами
    plot_bar_mean_temp_with_ci_each_season(df_season_stats=df_season_stats, selected_city=selected_city)

    # Получение API-ключа (Добавить форму для ввода API-ключа OpenWeatherMap)
    api_key = st.text_input("Введите ваш API-ключ для OpenWeatherMap", type="password")
    valid_api_key_flg = False

    # Если API-ключ введен, то выводим результаты по текущей погоде
    if api_key:
        try:
            curent_temperature, curent_season = get_current_weather(api_key=api_key, city=selected_city)
            st.write(f"Текущая температура в городе {selected_city} равна {curent_temperature}, сезон — {curent_season}")
            valid_api_key_flg = True
        except Exception as e:
            st.error(f"Ошибка: {e}")

    # Вывести текущую температуру через API и указать, нормальна ли она для сезона
    if valid_api_key_flg:
        result_txt = check_normality_of_temperature(api_key=api_key, city=selected_city, df=df)
        st.write(result_txt)


if __name__ == "__main__":
    main()