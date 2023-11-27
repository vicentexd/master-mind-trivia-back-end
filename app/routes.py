from flask import Blueprint, jsonify, request
import requests
import html
import os
from flask_socketio import  join_room, send, emit
from app import socketio
from .utils.generateCodeGame import generate_game_code
import json
from openai import OpenAI
import uuid
import random
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
    avatar_url = body.get("avatar_url")

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
          question_answers = question["answers"]

          random.shuffle(question_answers)
          newQuestion = {
              "correct_answer": question["correct_answer"],
              "answers": question_answers,
              "question": question["question"],
          }

          questions.append(newQuestion)      

      game_code = generate_game_code()


      new_game = {
        "code": game_code,
        "category": categoryDescription,
        "difficulty": difficulty,
        "language": language,
        "players": [{
            "id": str(uuid.uuid4()),
            "username": username,
            "score": 0,
            "avatar_url": avatar_url,
        }],
        "questions": questions,
        "current_question": questions[0],
        "started": False,
      }

      games[game_code] = new_game
      
      return jsonify({"Game": new_game})
    else:
        return jsonify({"error": "Erro ao obter perguntas da API"})

# Rota para consultar todos os jogos
@bp.route("/get_all_games", methods=["GET"])
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
      return jsonify({"error": "Error get categories"}), 404
         
# Rota para entrar em um jogo
@bp.route("/join_game",  methods=["POST"])
def join_game():
    body = request.json
    username = body.get("username")       
    avatar_url = body.get("avatar_url")       
    game_code = body.get("gameCode")

    if game_code in games:
        update_game = games[game_code]
        if any(player["username"] == username for player in update_game["players"]):
          return jsonify({"message": "Username already used"}), 400
        
        new_player = {
            "id": str(uuid.uuid4()),
            "username": username,
            "score": 0,
            "avatar_url": avatar_url,
        }
        update_game["players"].append(new_player)

        games[game_code] = update_game
        return jsonify({"message": "Success!"})
    else:
        return jsonify({"message": "Game not found"}), 404    

# Rota para começar um jogo
@bp.route("/start_game",  methods=["POST"])
def start_game():
    body = request.json
    game_code = body.get("gameCode")

    if game_code in games:
        update_game = games[game_code]
        
        update_game["started"] = True

        games[game_code] = update_game
        return jsonify({"message": "Game Started!"})
    else:
        return jsonify({"message": "Game not found"}), 404

# Quando um jogador se conecta
@socketio.on('connect')
def handle_connect():
    print('Novo jogador conectado')

# Evento Socket para se juntar num jogo
@socketio.on('join_game')
def handle_join_game(data):
    print('join_game')
    game_code = data["game_code"]
    join_room(game_code)

# Evento Socket para Iniciar um jogo
@socketio.on('start_game')
def handle_start_game(data):
    print('start_game')
    game_code = data["game_code"]
    emit("game_started", to=game_code)

# Evento Socket para responder uma pergunta
@socketio.on('answer_question')
def handle_answer_question(data):
    print(data)
    game_code = data["game_code"]
    user_id = data["user_id"]
    user_answer = data["user_answer"]
    time = data["response_time"]
    

    get_game = games[game_code]

    print(get_game)

    current_question = get_game["current_question"]

    update_user = next((user for user in get_game["players"] if user["id"] == user_id), None)
    print(update_user)
    if(current_question["correct_answer"] == user_answer):
        print('Acertou a resposta 😁😀')
        update_user["score"] += time + 1
    else:
        print('Errou!!!!')

    emit_message = {
        "user_id": user_id,
    }
    games[game_code] = get_game
    emit("user_answer", emit_message, to=game_code)



@socketio.on('teste')
def teste(data):
    print('teste')
    game_code = data["game_code"]
    send("testado", to=game_code)