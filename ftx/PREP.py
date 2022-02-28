import config
import client
import time
import json

sub = client.FtxClient(config.PERP['KEY'],config.PERP['SECRET'],config.PERP['SUBACCOUNT'])


def get_coin(coin):
    
    total = 0
    try:
        result = sub.get_sub_balances()
        for item in result:
            if(item['coin'] ==coin):
                # 不借货时的可用余额
                total = item['availableWithoutBorrow']
    except Exception as e:
        return {
            "total":0,
            "msg":str(e)
        }
    print(f'==>Total:{int(total*100)/100}')
    return {
        "total":total
        }
# 取未成交条件委托合约
def del_old_order(symbol):
    orders = sub.get_conditional_orders(symbol)
    num = "No"
    if(len(orders) == 1 ):
        sub.cancel_orders(symbol,True,False)
        print('Delete conditial order')
        num = "Yes"
    return num

def set_size(price):
    usd = get_coin('USD')
    # 不设置size，默认下单75％，即15倍杠杆
    return int(usd['total'] * 19.65 * 0.75 / price * 10) / 10

def con_order(symbol,side,size,limitPrice,triggerPrice,type:str='stop'):
    cond_stop ={}
    try:
        cond_stop = sub.place_conditional_order(symbol,side, size,type,limitPrice,True,True,triggerPrice)
    except Exception as e:
        cond_stop = { "error":str(e)}
    return cond_stop

def limit_order(symbol,side,price,size, type:str = 'limit',reduceonly:bool = False,ioc:bool = False,postonly:bool = False):
    order ={}
    # 限价委托单
    try:
        order = sub.place_order(symbol,side,price,size,type,reduceonly,ioc,postonly,None)
    except Exception as e:
        order = { "error":str(e)}
    return order

def del_con_order(symbol):
    del_msg = 'None'
    try:
        del_msg = del_old_order(symbol)
    except Exception as e:
        del_msg = str(e)
    return del_msg

def perp(data):

    useSize = 0
    if('size' not in data or data['size'] == 0):
    # 不设置size，默认下单75％，即15倍杠杆
        useSize = set_size(data['price'])
    else:
        useSize =  data['size']

    if(useSize == 0):
        return {
            "total":0,
            "msg":"No Money"
        }
    
    condSide = 'sell' if data['side']=='buy' else 'buy'
    # 最多盈亏10％，15倍杠杆
    priceLess = int(data['price']*(1 - 0.1/15)*100)/100
    priceMore = int(data['price']*(1 + 0.1/15)*100)/100
    stopPrice = priceLess if condSide =='sell' else priceMore
    profitPrice = priceLess if condSide !='sell' else priceMore

    print(f'==>{data["side"]}:{data["price"]},Stop:{stopPrice},Profit:{profitPrice},Size:{useSize}')
   
    # 限价委托单
    order = limit_order(data['symbol'],data['side'],data['price'], useSize,'limit',False)
    orderSuss = True if 'error' not in order else False
    # 删除前一条委托单
    del_msg = del_con_order(data['symbol'])
    # 上损单
    cond_stop = con_order(data['symbol'],condSide, useSize,stopPrice,stopPrice,'stop') if orderSuss else {"error":"limit order error"}
    # 上盈单 
    cond_profit = con_order(data['symbol'],condSide, useSize,profitPrice,profitPrice,'takeProfit') if orderSuss else {"error":"limit order error"}

    return {
        "order":order,
        "cond_stop":cond_stop,
        "cond_profit":cond_profit,
        "del_old_order": del_msg
    }

def order(request):
    data = request.get_json()
    if 'passphrase' not in data or data['passphrase'] != config.PASSPHRASE_TV:
        return {
            "code":"error",
            "msg":"invalid passphrase,forbidden"
        }
    return perp(data)