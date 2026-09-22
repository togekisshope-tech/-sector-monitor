from flask import Flask, jsonify
import akshare as ak

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response

@app.route("/api/sector/<type_str>")
def get_sector(type_str):
    try:
        if type_str == "industry":
            df = ak.stock_sector_spot(indicator="行业")
        else:
            df = ak.stock_sector_spot(indicator="概念")
        df = df[["板块名称", "涨跌幅", "成交额"]].copy()
        df["成交额"] = df["成交额"] / 1e8
        data = df.to_dict("records")
        return jsonify({"code":0, "data":data})
    except Exception as e:
        return jsonify({"code":-1, "msg":str(e)})

@app.route("/api/market_total")
def get_market_total():
    try:
        df = ak.stock_zh_a_spot_em()
        total = df["成交额"].sum() / 1e8
        return jsonify({"code":0, "data": round(total,2)})
    except Exception as e:
        return jsonify({"code":-1, "msg":str(e)})

@app.route("/api/limit_up")
def get_limit_up():
    try:
        df = ak.stock_zt_pool_em(date="")
        names = df["名称"].tolist()
        return jsonify({"code":0, "data":names})
    except Exception as e:
        return jsonify({"code":-1, "msg":str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
