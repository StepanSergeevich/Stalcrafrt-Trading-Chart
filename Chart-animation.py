import os
import json
import datetime
import requests
import datetime
import threading
import pandas as pd
import sqlite3 as sq  
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.animation as anim
import pytz
import time
from threading import *
from datetime import date
from statistics import mean
from matplotlib.animation import FuncAnimation


token = "" #Bearer FKKT3JF..... сгенерированный токен
amount = 10 #Количество предметов для формирования средней цены.
item_name = "" #Русское название предмета, например "Стандартные инструменты"
path_data_base = "" #Путь к файлу listing.json, например c:/projects/stalcraft-database-main/ru/listing.json

headers = {
    'Content-Type': "application/json",
    'Authorization': f"{token}"
}

    
def auction_history_lots(): # Get history prices of item
    id_item = get_id()
    token_link = requests.get(f"https://eapi.stalcraft.net/ru/auction/{id_item}/history?limit=200", headers = headers).json()
    return token_link['prices']

def auction_active_lots(): # Get active lots of item
    id_item = get_id()
    token_link = requests.get(f"https://eapi.stalcraft.net/ru/auction/{id_item}/lots?limit=200&sort=buyout_price&order=asc", headers = headers).json()
    return token_link['lots']


def get_id(): # Find id item

    with open(path_data_base, "rb") as data_file: data = json.load(data_file) #Open stalcraft-data-base 
    for element in data: 
        if element['name']['lines']['ru'] == item_name: 
                return element['data'].split('/')[-1].replace('.json', '')# Get rid of unnecessary things, take only id-name   


                
def get_prices(): # Get price of item

    lots = auction_active_lots()
    price_list = []
    
    for i in range(len(lots)): # Sort prices and append this in price_list
        if lots [i]['buyoutPrice'] > 1:
            price_list.append(lots [i]['buyoutPrice'])

    price_list.sort()
    return int(mean(price_list[:amount])) # Del point and averages the price



def get_values(): # Gets volume of item

    history_lots = auction_history_lots()
    lot_counts = 0

    if not history_lots: # If empty
        return 1
    
    #get UTC+0 date
    pytz_time_zone = pytz.timezone("Europe/London")
    time_today = datetime.datetime.now(pytz_time_zone)

    #count values
    for i in range(len(history_lots)):
        time_lots = datetime.datetime.strptime(history_lots[i]['time'],"%Y-%m-%dT%H:%M:%SZ")

        if time_lots.hour != time_today.hour or time_lots.hour != time_today.hour:
            continue
        elif time_lots.minute == time_today.minute: 
            lot_counts += 1

    return lot_counts


# Update High Low and Open for price on chart(sqlite3)
def record_value(): 

    price = get_prices()

    with sq.connect("data-candle.db") as con:
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS integers (open INTEGER, high INTEGER, low INTEGER)") 
        empty_values = cur.execute("SELECT COUNT(*) FROM integers").fetchall()
        if empty_values[0][0] == 0: 
            cur.execute("INSERT INTO integers (open, high, low) VALUES (?, ?, ?)", (price, price, price))
        else:
            cur.execute("UPDATE integers SET high = ? WHERE high < ?", (price, price)) 
            cur.execute("UPDATE integers SET low = ? WHERE low > ?", (price, price))
        cur.row_factory = sq.Row #Create the dict 
        return_values = cur.execute("SELECT * FROM integers").fetchall()
    return [dict(row) for row in return_values] #Return the dict
        


# Creates data format for chart(sqlite3)
def get_chart_data():

        price = get_prices()
        value = get_values()
        result_value_file = record_value()

        high_now = int(result_value_file[-1]["high"])
        low_now = int(result_value_file[-1]["low"])
        open_now = int(result_value_file[-1]["open"])

        pytz_time_zone = pytz.timezone("Europe/London")
        time_today = datetime.datetime.now(pytz_time_zone)
        time_today = time_today.replace(tzinfo=None)

        upd_dict = {"High": [], "Low": [], "Open": [], "Close": [], "Volume": [], "Date": []}


        with sq.connect("data-chart.db") as con:

            data = con.cursor()
            data.execute("""CREATE TABLE IF NOT EXISTS data (High INTEGER, Low INTEGER, Open INTEGER, Close INTEGER, Volume INTEGER, Date INTEGER)""")

            all_values = data.execute("""SELECT * FROM data""").fetchall()
            
            if all_values == []:
                data.execute("""INSERT INTO data (High, Low, Open, Close, Volume, Date) VALUES(?,?,?,?,?,?)""", (high_now, low_now, open_now, price, value, time_today))

            if data.execute("SELECT COUNT(*) FROM data").fetchall()[0][0] > 0:
                last_date = data.execute("SELECT Date From data").fetchall()[-1]
                bool_date = datetime.datetime.strptime(last_date[0], '%Y-%m-%d %H:%M:%S.%f')

                if bool_date.minute != time_today.minute:
                    val = 0
                    history_lots = auction_history_lots()

                    for i in range(len(history_lots)):
                        time_lots = datetime.datetime.strptime(history_lots[i]['time'],"%Y-%m-%dT%H:%M:%SZ") 

                        if time_lots.hour != time_today.hour or time_lots.hour != time_today.hour: 
                            continue
                        elif time_lots.minute == time_today.minute-1: 
                            val += 1

                    data.execute("""INSERT INTO data (High, Low, Open, Close, Volume, Date) VALUES(?,?,?,?,?,?)""", (high_now, low_now, open_now, price, val, time_today))


                    with sq.connect("data-candle.db") as con:
                        cur = con.cursor()
                        cur.execute("""DELETE FROM integers""")


            for row in all_values:
                upd_dict["High"].append(list(row)[0])
                upd_dict["Low"].append(list(row)[1])
                upd_dict["Open"].append(list(row)[2])
                upd_dict["Close"].append(list(row)[3])
                upd_dict["Volume"].append(list(row)[4])
                upd_dict["Date"].append(datetime.datetime.strptime(list(row)[5], '%Y-%m-%d %H:%M:%S.%f'))



        for variables, value in zip(upd_dict.keys(), [high_now, low_now, open_now, price, value, time_today]): upd_dict[variables].append(value)
        upd_dict = pd.DataFrame.from_dict(upd_dict) 
        upd_dict.set_index('Date', inplace=True) 
        return upd_dict




#Animation
def update_chart_data(): 
    global data_chart
    data_chart = get_chart_data() # Update chart_data


data_chart = get_chart_data() 


def animation(): 

    def repeat_animation(frame):
        t = threading.Thread(target=update_chart_data)
        t.start()
        ax1.clear()
        ax2.clear() 
        mpf.plot(data_chart, type='candle', ax=ax1, style='binance', xrotation=0)
        mpf.plot(data_chart, ax=ax2, xrotation=0, style='binance', volume=ax2)

    figure = plt.figure()
    ax1 = figure.add_subplot(2,1,1)
    ax2 = figure.add_subplot(2,1,2)
    mpf.plot(data_chart, type='candle', ax=ax1, style='binance', xrotation=0)
    mpf.plot(data_chart, ax=ax2, xrotation=0, style='binance', volume=ax2)

    animation = FuncAnimation(figure, repeat_animation, interval=5000)

    plt.show()




animation() 



