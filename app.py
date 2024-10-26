import os
import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import json
import sqlite3
import logging

app = Flask(__name__)
CORS(app)

# Configuração do logger
handler = logging.FileHandler('logs/flask_app.log')  # Log para um arquivo
app.logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
app.logger.addHandler(handler)

# Crie uma métrica de exemplo (contador de requisições)
REQUEST_COUNT = Counter('http_requests_total', 'Total de requisições HTTP', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('http_request_latency_seconds', 'Latência das requisições HTTP em segundos', ['method', 'endpoint'])
HTTP_ERRORS = Counter('http_errors_total', 'Total de respostas HTTP com erro', ['method', 'endpoint', 'status_code'])

def log_message(level, message):
    """Loga uma mensagem com o nível especificado."""
    log_methods = {
        'debug': app.logger.debug,
        'info': app.logger.info,
        'warning': app.logger.warning,
        'error': app.logger.error,
        'critical': app.logger.critical
    }
    if level in log_methods:
        log_methods[level](f"{message}")
    else:
        app.logger.error(f"Unrecognized logging level: {level}")

# Middleware para contar requisições
@app.before_request
def before_request():
    REQUEST_COUNT.labels(method=request.method, endpoint=request.path).inc()

# Rota para o Prometheus coletar as métricas
@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# Endpoint para devolver todos as pessoas cadastradas
@app.route('/')
def home():
    log_message('info', 'Accessed home endpoint')
    return "API de pessoas"

@app.route('/pessoas', methods=['GET'])
def pessoas():
    try:
        with sqlite3.connect('crud.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''SELECT nome, sobrenome, cpf, data_nascimento FROM pessoa''')
            result = cursor.fetchall()
            log_message('info', 'Fetched all people from the database')
            return json.dumps([dict(ix) for ix in result]), 200
    except Exception as e:
        log_message('error', f'Error fetching people: {e}')
        return jsonify(error=str(e)), 500

@app.route('/pessoa/<cpf>', methods=['GET', 'DELETE'])
def pessoa_por_cpf(cpf):
    try:
        with sqlite3.connect('crud.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if request.method == 'GET':
                cursor.execute('''SELECT nome, sobrenome, cpf, data_nascimento FROM pessoa WHERE cpf=?''', [cpf])
                result = cursor.fetchall()
                if result:
                    log_message('info', f'Fetched person with CPF: {cpf}')
                    return json.dumps([dict(ix) for ix in result]), 200
                log_message('warning', f'Person not found with CPF: {cpf}')
                return jsonify(error="Pessoa não encontrada"), 404
            elif request.method == 'DELETE':
                cursor.execute('DELETE FROM pessoa WHERE cpf = ?', (cpf,))
                if cursor.rowcount == 0:
                    log_message('warning', f'Attempted to delete non-existing person with CPF: {cpf}')
                    return jsonify(error="Pessoa não encontrada"), 404
                conn.commit()
                log_message('info', f'Deleted person with CPF: {cpf}')
                return jsonify(success="Pessoa deletada com sucesso"), 200
    except Exception as e:
        log_message('error', f'Error handling request for CPF {cpf}: {e}')
        return jsonify(error=str(e)), 500

@app.route('/pessoa', methods=['POST'])
def insere_atualiza_pessoa():
    data = request.get_json(force=True)
    nome = data.get('nome')
    sobrenome = data.get('sobrenome')
    cpf = data.get('cpf')
    datanascimento = data.get('data_nascimento')
    
    try:
        with sqlite3.connect('crud.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM pessoa WHERE cpf = ?', (cpf,))
            exists = cursor.fetchone()
            if exists:
                cursor.execute('UPDATE pessoa SET nome=?, sobrenome=?, data_nascimento=? WHERE cpf=?', (nome, sobrenome, datanascimento, cpf))
                conn.commit()
                log_message('info', f'Updated person with CPF: {cpf}')
                return jsonify(success="Pessoa atualizada com sucesso"), 200
            cursor.execute('INSERT INTO pessoa (nome, sobrenome, cpf, data_nascimento) VALUES (?, ?, ?, ?)', (nome, sobrenome, cpf, datanascimento))
            conn.commit()
            log_message('info', f'Inserted new person with CPF: {cpf}')
            return jsonify(success="Pessoa inserida com sucesso"), 201
    except Exception as e:
        log_message('error', f'Error inserting/updating person: {e}')
        return jsonify(error=str(e)), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
