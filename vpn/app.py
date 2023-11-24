from flask import Flask, render_template, request
from vpn import *
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
@app.route('/')
def index():
    
    return render_template('index.html', data="ip")

@app.route('/encender_todas', methods=['POST'])
def entoda():
    if request.method == 'POST':
        if request.json:
            b = request.json
            print("datos_json")
            print(b)
        a = ontode()
        return a
    
@app.route('/apagar_todas', methods=['POST'])
def offtoda():
    if request.method == 'POST':
        if request.json:
            b = request.json
            print("datos_json")
            print(b)
        a = offtode()
        return a
    
@app.route('/encender_una', methods=['POST'])
def enuna():
    if request.method == 'POST':
        if request.json:
            b = request.json
            print("datos_json")
            print(b)
            a = onuna(b["input"])
            return a
    
@app.route('/actualizar', methods=['POST'])
def consult():
    if request.method == 'POST':
        if request.json:
            b = request.json
            print("datos_json")
            print(b)
        a = ontode()
        return a


if __name__ == '__main__':
    app.run(debug=True, port=5000) 