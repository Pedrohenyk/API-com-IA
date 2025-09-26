import os
from flask import Flask, request, jsonify, render_template, abort
from flask_sqlalchemy import SQLAlchemy
import google.generativeai as genai
from dotenv import load_dotenv

# Fornece o caminho explícito para o .env, resolvendo o problema do reloader do Flask.
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=dotenv_path)

# -----------------------------------------------------------------------------
# 1. CONFIGURAÇÃO INICIAL
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///queries.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 2. CONFIGURAÇÃO DA API GEMINI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("AVISO: A variável de ambiente GEMINI_API_KEY não foi definida. A análise de IA não funcionará.")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    print("SUCESSO: A API do Gemini foi configurada.")


# -----------------------------------------------------------------------------
# 3. MODELO DO BANCO DE DADOS
# -----------------------------------------------------------------------------
class QueryCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(120), nullable=False)
    observacao = db.Column(db.Text, nullable=True)
    query_sql = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'cliente': self.cliente,
            'obs': self.observacao,
            'query': self.query_sql
        }

# -----------------------------------------------------------------------------
# 4. ROTAS DA APLICAÇÃO (ENDPOINTS)
# -----------------------------------------------------------------------------
with app.app_context():
    db.create_all()
    print("Banco de dados e tabelas criados/verificados com sucesso.")


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/cards', methods=['GET', 'POST'])
def handle_cards():
    if request.method == 'POST':
        data = request.json
        if not data or not data.get('cliente') or not data.get('query'):
            abort(400, description="Cliente e Query são campos obrigatórios.")
        new_card = QueryCard(cliente=data['cliente'], observacao=data.get('obs', ''), query_sql=data['query'])
        db.session.add(new_card)
        db.session.commit()
        return jsonify(new_card.to_dict()), 201
    else:
        cards = QueryCard.query.order_by(QueryCard.id.desc()).all()
        return jsonify([card.to_dict() for card in cards])

@app.route('/api/analisar-query', methods=['POST'])
def analisar_query():
    """Recebe uma query e a envia para a API do Gemini para análise."""
    if not GEMINI_API_KEY:
        return jsonify({'erro': 'A chave da API Gemini não foi configurada no servidor.'}), 500

    try:
        data = request.json
        query_para_analisar = data.get('query')
        if not query_para_analisar:
            abort(400, description="Nenhuma query foi fornecida para análise.")

        # CORREÇÃO APLICADA AQUI: Usando o nome do modelo estável.
        model = genai.GenerativeModel('gemini-2.5-pro')
        
        prompt = f"""
        Você é um especialista em SQL. 
        Analise a query abaixo e explique o que ela faz em um parágrafo claro e conciso.
        Explique o que cada função faz.

        Query SQL:
        ```sql
        {query_para_analisar}
        ```
        """
        response = model.generate_content(prompt)
        explicacao = response.text
        return jsonify({'explicacao': explicacao.strip()})

    except Exception as e:
        print(f"Um erro inesperado ocorreu: {e}")
        return jsonify({'erro': f'Ocorreu um erro ao contatar a API de IA: {str(e)}'}), 500

@app.route('/api/cards/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    card = QueryCard.query.get(card_id)
    if card is None:
        abort(404, description="Card não encontrado.")
    db.session.delete(card)
    db.session.commit()
    return jsonify({'message': 'Card excluído com sucesso!'})

# -----------------------------------------------------------------------------
# 5. INICIAR A APLICAÇÃO
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

