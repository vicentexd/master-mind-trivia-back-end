from flask import Blueprint, jsonify, request
import requests
import html
import os
from flask_socketio import  join_room
from app import socketio
from .utils.generateCodeGame import generate_game_code
import json
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Cria um Blueprint para rotas
bp = Blueprint("routes", __name__)

games = {}

translatedCategories = []

# Rota básica de teste
@bp.route("/")
def index():
    return "Página inicial do aplicativo"

# Rota para a criação de um jogo novo
@bp.route("/create_game", methods=["POST"])
def create_game():
    body = request.json

    category = body.get("category")
    language = body.get("language")
    difficulty = body.get("difficulty")
    username = body.get("username")

    categoryId = category["id"]
    categoryDescription = category["name"]

    url = f"https://opentdb.com/api.php?amount=10&category={categoryId}&difficulty={difficulty}&type=multiple"

    response = requests.get(url)

    if response.status_code == 200:
      openTDB_response = response.json()["results"]

      clean_data = []
      questions = []

      for question_data in openTDB_response:
            answers = [
                html.unescape(answer) for answer in question_data["incorrect_answers"]
            ]
            answers.append(html.unescape(question_data["correct_answer"]))
            question = html.unescape(question_data["question"])
            correct_answer = html.unescape(question_data["correct_answer"])
            message = {
                "question": question,
                "answers": answers,
                "correct_answer": correct_answer,
            }
            clean_data.append(message)
      
      if language == "pt-br":
            responseChat = client.chat.completions.create(
                model="gpt-3.5-turbo-1106",
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a question translator who translates a quiz into Brazilian Portuguese, which respects the context of the question, which returns a json in the same way you received it, but, you must not translate de keys of JSON",
                    },
                    {"role": "user", "content": f"{clean_data}"},
                ],
            )

            translatedData = json.loads(responseChat.choices[0].message.content)
            clean_data = translatedData["questions"]

      for question in clean_data:
          newQuestion = {
              "correct_answer":question["correct_answer"],
              "answers":question["answers"],
              "question":question["question"],
          }

          questions.append(newQuestion)      

      game_code = generate_game_code()

      new_game = {
        "code": game_code,
        "category": categoryDescription,
        "difficulty": difficulty,
        "language": language,
        "players": [username],
        "questions": questions,
        "started": False,
      }

      games[game_code] = new_game
      
      return jsonify({"Game": new_game})
    else:
        return jsonify({"error": "Erro ao obter perguntas da API"})

# Rota para consultar todos os jogos
@bp.route("/getAllGames", methods=["GET"])
def get_all_games():
    return jsonify({"Games": games})

# Rota para consultar um jogo pelo code
@bp.route("/game/<code>", methods=["GET"])
def consult_game_by_code(code):
    if code in games:
        return jsonify({"Game": games[code]})
    else:
        return jsonify({"message": "Game not found!"}), 404

# Rota para consultar as categorias de quiz
@bp.route("/categories/<language>", methods=["GET"])
def get_categories(language):
    url= "https://opentdb.com/api_category.php"

    response = requests.get(url)

    if response.status_code == 200:
      openTDB_response = response.json()["trivia_categories"]

      categories = openTDB_response

      if(language == "ptBr"):
          global translatedCategories
          if(len(translatedCategories) == 0):
            message = {
              "categories": categories
            }

            responseChat = client.chat.completions.create(
              model="gpt-3.5-turbo-1106",
              response_format={"type": "json_object"},
              messages=[
               {
                "role": "system",
                "content": "You are a  translator who translates a categories list into Brazilian Portuguese, which returns a json in the same way you received it, but, you must not translate de keys of JSON",
               },
                {"role": "user", "content": f"{message}"},
              ],
            )

            translatedData = json.loads(responseChat.choices[0].message.content)
            categories = translatedData["categories"]
            translatedCategories = categories
          else:
              categories = translatedCategories
          

      return jsonify({"categories" : categories});
    else:
      return jsonify({"error": "Erro ao obter perguntas da API"})
        
        
  
# Quando um jogador se conecta
@socketio.on('connect')
def handle_connect():
    print('Novo jogador conectado')
