import asyncio
import concurrent.futures
import requests
import pandas as pd
import datetime
import backtrader as bt
from datetime import datetime, timedelta
from flask import Flask, render_template, request
import random
import distutils

app = Flask(__name__)


@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        req = {'pair': request.form['pair'].upper(),
               'time_frame': request.form['time_frame'],
               'short_term': (int(request.form['short_min']), int(request.form['short_max'])),
               'med_term': (int(request.form['med_min']), int(request.form['med_max'])),
               'is_not_long': bool(distutils.util.strtobool(
                   request.form.get('is_not_long'))) if 'is_not_long' in request.form else False
               }
        global start
        if req['is_not_long']:
            # print('without long')

            if req['short_term'][0] > req['short_term'][1]:
                return render_template('400.html',
                                       message='Short term max value is less than min value. it is not acceptable.'), 400
            if req['med_term'][0] > req['med_term'][1]:
                return render_template('400.html',
                                       message='Medium term max value is less than min value. it is not acceptable.'), 400
            if req['short_term'][1] >= req['med_term'][0]:
                return render_template('400.html',
                                       message='short range and medium range have conflict. correct it!'), 400
            start = datetime.now()
            print('start with out Long term', datetime.now().strftime("%H:%M:%S"))
            res = asyncio.run(solver(data_loader(req), req, st1=False))

        else:
            req['long_term'] = (int(request.form['long_min']), int(request.form['long_max']))

            # print('with long')
            if req['short_term'][0] > req['short_term'][1]:
                return render_template('400.html',
                                       message='Short term max value is less than min value. it is not acceptable.'), 400
            if req['med_term'][0] > req['med_term'][1]:
                return render_template('400.html',
                                       message='Medium term max value is less than min value. it is not acceptable.'), 400
            if req['long_term'][0] > req['long_term'][1]:
                return render_template('400.html',
                                       message='Long term max value is less than min value. it is not acceptable.'), 400
            if req['short_term'][1] >= req['med_term'][0]:
                return render_template('400.html',
                                       message='short range and medium range have conflict. correct it!'), 400
            if req['med_term'][1] >= req['long_term'][0]:
                return render_template('400.html',
                                       message='long range have conflict with short or medium range. correct it!'), 400

            start = datetime.now()
            print('start with Long term', datetime.now().strftime("%H:%M:%S"))
            res = asyncio.run(solver(data_loader(req), req, st1=True))
        return render_template('response.html', response=res[0], request=req, data=res[1])

        # return {'ranked_list': res, 'request': req}

    else:
        return render_template('index.html')


def data_loader(req):
    pair = req['pair']
    time_frame = req['time_frame']

    base_url = 'https://api.binance.com'
    query = f'/api/v3/klines?symbol={pair}&interval={time_frame}&limit=1000'
    url = f'{base_url}{query}'
    response = requests.get(url).json()
    starter = response[0][0]

    n = 10
    for _ in range(n - 1):
        given_time = datetime.fromtimestamp(starter / 1000)
        if time_frame == '5m':
            final_time = given_time - timedelta(minutes=5000)
        elif time_frame == '15m':
            final_time = given_time - timedelta(minutes=15000)
        elif time_frame == '30m':
            final_time = given_time - timedelta(minutes=30000)
        elif time_frame == '1h':
            final_time = given_time - timedelta(hours=1000)
        elif time_frame == '4h':
            final_time = given_time - timedelta(hours=4000)
        elif time_frame == '8h':
            final_time = given_time - timedelta(hours=8000)
        elif time_frame == '1d':
            final_time = given_time - timedelta(days=1000)
        starter = int(datetime.timestamp(final_time)) * 1000
        query = f'/api/v3/klines?symbol={pair}&interval={time_frame}&startTime={starter}&limit=1000'
        url = f'{base_url}{query}'
        temp_res = requests.get(url).json()
        response = temp_res + response
    # response
    df = pd.DataFrame(response,
                      columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', '1', '2', '3', '4',
                               '5'])
    df = df.drop(columns=['1', '2', '3', '4', '5'])

    df.iloc[:, 1:] = df.iloc[:, 1:].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    df = df.drop_duplicates()
    print('data from ', df.index[0], ' to ', df.index[-1])
    return df


async def solver(df, req, st1):
    if st1:
        fast_range = req['short_term']
        normal_range = req['med_term']
        slow_range = req['long_term']
        rank_list = list()
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for f in range(fast_range[0], fast_range[1]):
                s = random.randrange(slow_range[0], slow_range[1] + 1, 15)
                results = [executor.submit(calculator, f, n, s, df, st1) for n in
                           range(normal_range[0], normal_range[1], 2)]
            for f in concurrent.futures.as_completed(results):
                rank_list.append(f.result())

        top_ranked = sorted(rank_list, key=lambda tup: tup[0], reverse=True)[:3]
        top_ranked = [(item[0], item[1], round(((item[0] - 10000) / 100), 2)) for item in top_ranked]
        data = {'start_date': df.index[0],
                'end_date': df.index[-1],
                'row_length': df.shape[0]}
        return top_ranked, data

    else:

        fast_range = req['short_term']
        normal_range = req['med_term']
        rank_list = list()
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for f in range(fast_range[0], fast_range[1]):
                results = [executor.submit(calculator, f, n, -1, df, st1) for n in
                           range(normal_range[0], normal_range[1], 2)]
            for f in concurrent.futures.as_completed(results):
                rank_list.append(f.result())

        top_ranked = sorted(rank_list, key=lambda tup: tup[0], reverse=True)[:3]
        top_ranked = [(item[0], item[1], round(((item[0] - 10000) / 100), 2)) for item in top_ranked]
        data = {'start_date': df.index[0],
                'end_date': df.index[-1],
                'row_length': df.shape[0]}
        end = datetime.now()
        print('done', end - start)
        return top_ranked, data


def calculator(fast=9, normal=15, slow=100, df=None, st1=True):
    # print('hi',fast,normal,slow,st1)
    class St1(bt.Strategy):
        def __init__(self):
            self.dataclose = self.datas[0].close
            self.ma_fast = bt.ind.EMA(period=fast)
            self.ma_normal = bt.ind.EMA(period=normal)
            self.ma_slow = bt.ind.EMA(period=slow)
            self.crossover = bt.ind.CrossOver(self.ma_fast, self.ma_normal)

        def next(self):

            if self.dataclose[0] > self.ma_slow[0]:
                # long
                if self.crossover > 0:
                    self.buy()
                elif self.crossover < 0:
                    self.close()

            elif self.dataclose[0] < self.ma_slow[0]:
                # short
                if self.crossover < 0:
                    self.sell()
                elif self.crossover > 0:
                    self.close()

    class St2(bt.Strategy):
        def __init__(self):
            self.dataclose = self.datas[0].close
            self.ma_fast = bt.ind.EMA(period=fast)
            self.ma_normal = bt.ind.EMA(period=normal)
            self.crossover = bt.ind.CrossOver(self.ma_fast, self.ma_normal)

        def next(self):

            # long
            if self.crossover > 0:
                if self.position:
                    self.close()
                self.buy()
            elif self.crossover < 0:
                if self.position:
                    self.close()
                self.sell()

    data = bt.feeds.PandasData(dataname=df)
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    if st1:
        cerebro.addstrategy(St1)
    else:
        cerebro.addstrategy(St2)
    cerebro.broker.setcash(10000.0)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=10)

    cerebro.run()
    # cerebro.plot()
    return cerebro.broker.getvalue(), [fast, normal, slow]


# @app.route('/api')
# def solver():
#     res = asyncio.run(solver(data_loader()))
#     return {'ranked_list': res}


if __name__ == '__main__':
    app.run()
