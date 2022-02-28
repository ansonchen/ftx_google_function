import config
import client
import time
import json
from google.cloud import storage

sub = client.FtxClient(config.SPOT['KEY'],config.SPOT['SECRET'],config.SPOT['SUBACCOUNT'])

storage_client = storage.Client.from_service_account_json('key.json')
bucket_name = config.G_bucket_name
BUCKET = storage_client.get_bucket(bucket_name)

buyList ={}

def create_json(json_object, filename):
    # create a blob
    blob = BUCKET.blob(filename)
    # upload the blob 
    blob.upload_from_string(
        data=json.dumps(json_object),
        content_type='application/json'
        )
    result = filename + ' upload complete'
    return {'response' : result}

def get_json(filename):

    # get the blob
    blob = BUCKET.get_blob(filename)
    # load blob using json
    file_data = json.loads(blob.download_as_string())
    return file_data


# def get_before_order(code):

#     size = 0
#     quote = sub.get_order_history(f'{code}-PERP')
#     size = quote[0]['size'] if len(quote) > 0 else 0
#     buyList[code] = size
#     print(buyList)
#     return size
def file_read():
    return get_json('ftx.json')
    # result = {}
    # try:
    #     fo = open("text.txt","r+")
    #     str = fo.read()
    #     result = json.loads(str)
    #     fo.close()
    # except Exception as e:
    #     result = {
    #         "error":str(e)
    #     }
    # return result

def file_write(obj):
    return create_json(obj,'ftx.json')
    # result = {}
    # try:
    #     str = json.dumps(obj)
    #     fo = open("text.txt","w")
    #     fo.write(str)
    #     fo.close()
    #     result = {
    #         "msg":"write suss"}
    # except Exception as e:
    #     result = {
    #         "error":str(e)
    #     }
    # return result

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
    # print(type(result))
    # return json.dumps(result, separators=(',', ':'))

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

def clear_order_perp(data):
    global buyList
    clear_order = {}

    buyIndex = 1 if data['side']=='buy' else 0
    price = int(data['price']*100 + 2)/100 if data['side']=='buy' else int(data['price']*100 - 2)/100

    if data['xf'] in buyList and buyList[data['xf']][buyIndex] > 0 :
        clear_order = limit_order(f'{data["xf"]}-PERP',data['side'],price, buyList[data['xf']][buyIndex],'limit',True,False,False)
        if 'error' not in clear_order:
            print(f'==>clear order {data["side"]}:{price},size:{buyList[data["xf"]][buyIndex]}')
            buyList[data['xf']][buyIndex] = 0
            buyList[data['xf']][2] = ''
            file_write(buyList)
    else:
        print('No PERP positons')
        clear_order = {'msg':'No PERP positons'}
    if data['xf'] not in buyList:
        buyList[data['xf']]= [0,0,'']
        file_write(buyList)
    return clear_order
    
def xf_get_coin(price):
    USD = get_coin('USD')
    # 2X杠杆　0.8仓入
    return int(USD['total'] * 2 * 0.8 / price * 1000)/1000  

def xf(data):
    order = {}
    clear_order = {}
    global buyList
    buyList = file_read()
    print(buyList)
    # 先清空单（合约），再买入现货,市价单出，限价单入
    if(data['xf'] in buyList and buyList[data['xf']][2] == data['side']):
        return {
            "error":f'double {data["side"]}'
        }
    clear_order = clear_order_perp(data)
    print(clear_order)
    if 'error' in clear_order:
        return xf(data)

    price = int(data['price']*100 + 2)/100 if data['side']=='buy' else int(data['price']*100 - 2)/100
    size = 0.1
    if('size' not in data or data['size'] == 0):
        size = xf_get_coin(data['price'])
    else:
        size =  data['size']     
    print(f'==>Order:{data["side"]}:{data["price"]},Size:{size}')
    order = limit_order(f'{data["xf"]}-PERP',data['side'],price, size,'limit',False)
    if 'error' not in order:
        buyIndex = 0 if data['side']=='buy' else 1
        #将合约数据写入缓存
        buyList[data['xf']][buyIndex] = size
        buyList[data['xf']][2] = data['side']
        file_write(buyList)
        print(f'==>Order:Suss')
    print(order) 
    print(buyList)   
   
    return {
        "clear_order":clear_order,
        "order":order
    }

def clearList():
    global buyList
    list = {"SRM": [0, 0, ""], "SOL": [0, 0, ""], "BTC": [0, 0, ""], "ETH": [0, 0, ""], "FTT": [0, 0, ""]}
    file_write(list)
    buyList = file_read()
    print(buyList)
    return {
        "msg":"clear OK",
        "buylist":buyList
    }
def order(request):
    
    
    data = request.get_json()
    print(data)
    if 'passphrase' not in data or data['passphrase'] != config.PASSPHRASE_TV:
        return {
            "code":"error",
            "msg":"invalid passphrase,forbidden"
        }

    if 'clear' in data :
        return clearList()
        
    return xf(data) 