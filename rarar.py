from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from flask_socketio import SocketIO, emit
import discord
from discord.ext import commands
from discord import Client
from discord.ext import tasks, commands
from discord.utils import get
from threading import Thread
import logging
import random
import requests
import logging
import asyncio
import time

logging.basicConfig(level=logging.INFO)

# Discord bot
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
CHANNEL_ID = 1210254067952263322  # 監視するチャンネルIDを定数として定義


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")
    mute_cycle.start()
    
    


@bot.event
async def on_voice_state_update(member, before, after):
    channel = bot.get_channel(CHANNEL_ID)
    if isinstance(channel, discord.VoiceChannel):
        members_in_channel = [{'name': member.display_name, 'avatar_url': str(member.avatar.url) if member.avatar else None} for member in channel.members]
        socketio.emit('update_voice_members', members_in_channel)  # 通話メンバー情報の更新




def run_bot():
    bot.run("MTIxMDI1MzQyMzAwMjI1NTQxMQ.GrFm3Z.Iqca6F6OkjpBKUJhq8pvN_QZGWRHWttf4Zbpx8")

# Flask server
app = Flask(__name__)
socketio = SocketIO(app)
joined_users = []
answers = {}  # 全員の回答を保存するための辞書
current_question = None  # 現在の問題
current_choices = None  # 現在の選択肢
correct_answer = "正解の回答"  # 正解の回答をここに設定
answered_users = {}  # 回答したユーザーを保存するための辞書
game_in_progress = False  # ゲームが進行中かどうかを示すフラグ
ROLE_ID = 1212006533534056489  # 監視するロールIDを定数として定義
ratings = {}  # 各ユーザーの評価情報を保存するための辞書
server_state = 'no'  # サーバーの状態を保持する変数
# 各ユーザーの最終評価時間を記録する辞書
last_good_rating_time = {}
last_bad_rating_time = {}
# Good評価とBad評価のためのレートリミットインターバルを設定（秒単位）
GOOD_RATE_LIMIT_INTERVAL = 1  # 例としてGood評価は1分のクールダウン
BAD_RATE_LIMIT_INTERVAL = 1  # 例としてBad評価は2分のクールダウン

TARGET_USER_ID = 1210253423002255411  # 監視するユーザーIDを文字列で保持
ROLE_TO_WATCH = 1212812663546056775  # 監視するロールIDを文字列で保持
BAD_ROLE_ID = 1214004948338212896
                

@tasks.loop(seconds=50)
async def mute_cycle():
    for guild in bot.guilds:
        # 目的のロールオブジェクトを取得
        bad_role = guild.get_role(int(BAD_ROLE_ID))

        # ロールが見つからない場合はスキップ
        if bad_role is None:
            print(f"ういいいいい: {server_state}")
            continue

        # ボイスチャンネルで指定ロールを持つメンバーを取得
        members_to_mute = [member for member in guild.members if bad_role in member.roles and member.voice]

        # 各メンバーに対してミュートのON/OFFを繰り返す
        for _ in range(1):  # 5回の切り替えサイクル
            for member in members_to_mute:
                await member.edit(mute=True, deafen=True)  # ミュートとデフェンを有効にする
                await asyncio.sleep(1)  # 1秒待機
                await member.edit(mute=False, deafen=False)  # ミュートとデフェンを解除する
                await asyncio.sleep(1)  # 1秒待機
                await member.edit(mute=True, deafen=False)  # ミュートとデフェンを有効にする
                await asyncio.sleep(1)  # 1秒待機
                await member.edit(mute=False, deafen=True)  # ミュートとデフェンを解除する
                await asyncio.sleep(1)  # 1秒待機
                await member.edit(mute=True, deafen=False)  # ミュートとデフェンを有効にする
                await asyncio.sleep(1)  # 1秒待機
                await member.edit(mute=False, deafen=False)  # ミュートとデフェンを解除する
                await asyncio.sleep(1)  # 1秒待機

@bot.event
async def on_member_update(before, after):
    global server_state
    global joined_users
    global answers
    global answered_users
    global game_in_progress
    
    if after.id != TARGET_USER_ID:
        return

    if any(role.id == ROLE_TO_WATCH for role in after.roles) and not any(role.id == ROLE_TO_WATCH for role in before.roles):
        print(f"ユーザーID {after.id} に「人狼中」のロールが付与されました。")
        server_state = 'yes'
    
    if not any(role.id == ROLE_TO_WATCH for role in after.roles) and any(role.id == ROLE_TO_WATCH for role in before.roles):
        print(f"ユーザーID {after.id} から「人狼中」のロールが外されました。")
        server_state = 'no'

        # サーバーステータスが 'no' になったことを検知したら、ゲーム関連の変数をリセット
        if server_state == 'no':
            # ゲーム関連の変数をリセット
            joined_users = []           # 参加ユーザーを格納するリストを空に
            answers = {}                # 各ユーザーの回答を格納する辞書を空に
            answered_users = {}         # 回答したユーザーを格納する辞書を空に
            game_in_progress = False    # ゲーム進行中フラグをFalseに設定
            print("ゲーム関連の変数がリセットされました。")



        
@app.route('/check_status')
def check_status():
    # server_stateに基づいてボタンの表示をJSONで返す
    return jsonify(button_state=server_state)


joined_users = set()  # 空のセットを作成

@socketio.on('request_role_members')
def send_role_members():
    guild = bot.guilds[0]  # このBotが存在する最初のサーバーを取得
    role = discord.utils.get(guild.roles, id=ROLE_ID)  # 特定のロールを取得
    # ユーザーIDを文字列としてrole_members_infoに含める
    role_members_info = [{
        'id': str(member.id),  # ユーザーIDを文字列に変換
        'name': member.display_name,
        'avatar_url': str(member.avatar.url) if member.avatar else None
    } for member in guild.members if role in member.roles]
    socketio.emit('update_role_members', role_members_info)  # 特定の役職のメンバー情報の更新

def is_user_in_game(unique_id):
    global joined_users
    return unique_id in joined_users

GOOD_ROLE_ID = 1214005192157171723   # good評価一位のロールIDを文字列で保持
BAD_ROLE_ID = 1214004948338212896    # bad評価一位のロールIDを文字列で保持
current_good_leader = None  # 現在のgood評価一位のユーザーID
current_bad_leader = None  # 現在のbad評価一位のユーザーID

@socketio.on('rate_member')
def rate_member(data):
    user_id = int(data['user_id'])  # 数字を文字列に変える
    name = data['name']
    rating = data['rating']  # 'good' か 'bad' を想定

    # IPアドレスとユーザーエージェントからunique_idを生成
    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    unique_id = f"{ip_address}-{user_agent}"

    # 現在の時間を取得
    current_time = time.time()

    # good評価作のためのクールダウンをチェック
    if rating == 'good':
        last_time = last_good_rating_time.get(unique_id, 0)
        if current_time - last_time < GOOD_RATE_LIMIT_INTERVAL:
            socketio.emit('error', {'message': f'good評価は{GOOD_RATE_LIMIT_INTERVAL}秒間隔でのみ可能です。'}, to=unique_id)
            return
        last_good_rating_time[unique_id] = current_time
        
    # bad評価のためのクールダウンをチェック
    elif rating == 'bad':
        last_time = last_bad_rating_time.get(unique_id, 0)
        if current_time - last_time < BAD_RATE_LIMIT_INTERVAL:
            socketio.emit('error', {'message': f'bad評価は{BAD_RATE_LIMIT_INTERVAL}秒間隔でのみ可能です。'}, to=unique_id)
            return
        last_bad_rating_time[unique_id] = current_time

    
    # ユーザーの評価を更新
    if user_id not in ratings:
        ratings[user_id] = {'name': name, 'good': 0, 'bad': 0}
    ratings[user_id][rating] += 1

    # 評価情報を全てのクライアントに送信
    socketio.emit('update_ratings', ratings)

    # ロールの変更チェックと更新処理
    update_roles()

def update_roles():
    global current_good_leader, current_bad_leader

    # goodランキングでの1位を確認
    sorted_good_ratings = sorted(ratings.items(), key=lambda x: x[1]['good'], reverse=True)
    new_good_leader = sorted_good_ratings[0][0] if sorted_good_ratings else None
    
    # badランキングでの1位を確認
    sorted_bad_ratings = sorted(ratings.items(), key=lambda x: x[1]['bad'], reverse=True)
    new_bad_leader = sorted_bad_ratings[0][0] if sorted_bad_ratings else None

    # ランキングの変更があった場合、役職を更新する
    if new_good_leader != current_good_leader:
        print(f"New good leader is user ID {new_good_leader}.")  # new_good_leaderが変わったことをコンソールに出力
        change_role(current_good_leader, new_good_leader, GOOD_ROLE_ID)
        current_good_leader = new_good_leader
    
    if new_bad_leader != current_bad_leader:
        print(f"New bad leader is user ID {new_bad_leader}.")  # new_bad_leaderが変わったことをコンソールに出力
        change_role(current_bad_leader, new_bad_leader, BAD_ROLE_ID)
        current_bad_leader = new_bad_leader

def change_role(old_leader, new_leader, role_id):
    if old_leader:
        remove_role(old_leader, role_id)
    if new_leader:
        add_role(new_leader, role_id)

def add_role(user_id, role_id):
    # ユーザーID（user_id）とロールID（role_id）は文字列型を保持していることを前提とする
    guild = bot.guilds[0]  # ボットが所属するギルド（修正が必要な場合がある）
    member = discord.utils.get(guild.members, id=int(user_id))
    role = discord.utils.get(guild.roles, id=int(role_id))
    
    # メンバーに役職を付与
    if member and role:
        # 既にロールが付与されていないか確認する
        if role not in member.roles:
            coroutine = member.add_roles(role)
            bot.loop.create_task(coroutine)
        else:
            print(f"User {member} already has the role {role}.")
    else:
        print(f"Member or role not found. User ID: {user_id}, Role ID: {role_id}")

def remove_role(user_id, role_id):
    guild = bot.guilds[0]  # Botの対象ギルドを取得
    member = discord.utils.get(guild.members, id=int(user_id))
    role = discord.utils.get(guild.roles, id=int(role_id))
    
    # メンバーから役職を剥奪
    if member and role:
        # メンバーが実際にそのロールを持っているか確認する
        if role in member.roles:
            coroutine = member.remove_roles(role)
            bot.loop.create_task(coroutine)
        else:
            print(f"User {member} doesn't have the role {role}.")
    else:
        print(f"Member or role not found. User ID: {user_id}, Role ID: {role_id}")
    
    
@socketio.on('request_ratings')
def handle_request_ratings():
    socketio.emit('update_ratings', ratings)
    


def is_user_in_game(unique_id):
    global joined_users
    return unique_id in joined_users

def start_new_game():
    global current_question, current_choices, correct_answer, game_in_progress
    question_answer = random.choice(questions_answers)  # ランダムで問題と選択肢を選択
    current_question = question_answer[0]
    current_choices = question_answer[1:5]
    correct_answer = current_choices[int(question_answer[5]) - 1]  # 正解の選択肢を設定
    game_in_progress = True  # ゲームが開始されたことを示す
    socketio.emit('start_game')  # ゲーム開始のイベントを全てのクライアントに発行

@app.route('/check_game_start', methods=['POST'])
def check_game_start():
    # ゲームが開始しているかどうかを返す
    return jsonify({'game_started': game_in_progress})


@app.route('/check_game_status', methods=['POST'])
def check_game_status():
    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    unique_id = f"{ip_address}-{user_agent}"
    logging.info(f"check_game_status: Generated unique_id: {unique_id}")

    if is_user_in_game(unique_id):
        return jsonify({'redirect': url_for('game_index')})
    else:
        return jsonify({})

@app.route('/check_join_status', methods=['POST'])
def check_join_status():
    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    unique_id = f"{ip_address}-{user_agent}"
    logging.info(f"check_join_status: Generated unique_id: {unique_id}")

    if unique_id in joined_users:
        return jsonify({'joined': True})
    else:
        return jsonify({'joined': False})

@app.route('/', methods=['GET'])
def index():
    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    unique_id = f"{ip_address}-{user_agent}"
    logging.info(f"index: Generated unique_id: {unique_id}")

    if is_user_in_game(unique_id) and (len(joined_users) >= 2 or game_in_progress):
        return redirect(url_for('game_index'))  # 参加しているユーザーで、ゲームが満員または進行中の場合はgame_indexにリダイレクト
    else:
        return render_template('index.html')  # ユーザーが参加していない、またはゲームが開始されていない場合はindex.htmlを表示

@app.route('/join', methods=['POST'])
def join():
    global joined_users
    # 参加者がすでに3人いる場合
    if len(joined_users) >= 2:
        return jsonify({'full': True, 'message': 'Sorry, the game is full.'})
    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    unique_id = f"{ip_address}-{user_agent}"
    logging.info(f"join: Generated unique_id: {unique_id}")

    if unique_id not in joined_users:
        joined_users.append(unique_id)
        socketio.emit('update_joined_users', {'count': len(joined_users)})  # 参加ユーザー情報の更新
        if len(joined_users) >= 2:
            start_new_game()  # 新たにゲームを開始
            return jsonify({'redirect': '/game_index'})
        else:
            return jsonify({'redirect': None})
    return jsonify({'joined': True})  # すでに参加しているユーザーの場合

@app.route('/game_index', methods=['GET'])
def game_index():
    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    unique_id = f"{ip_address}-{user_agent}"
    logging.info(f"game_index: Generated unique_id: {unique_id}")

    if unique_id not in joined_users or not game_in_progress:
        return redirect(url_for('index'))  # 参加者以外のユーザーはindexページにリダイレクト
    return render_template('game_index.html', question=current_question, choices=current_choices)  # 現在の問題文と選択肢をテンプレートに渡す

def load_questions_answers(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        questions_answers = [line.strip().split(',') for line in f]
    return questions_answers

questions_answers = load_questions_answers('questions_answers.txt')



@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    global answers, answered_users, game_in_progress
    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    unique_id = f"{ip_address}-{user_agent}"
    answer = request.form['answer']

    if unique_id in joined_users and game_in_progress:  # ゲームが進行中の場合のみ回答を受け付ける
        if unique_id not in answered_users:  # ユーザーがまだ回答していない場合
            answered_users[unique_id] = True  # ユーザーを「回答済み」としてマーク
            answers[unique_id] = answer  
            if len(answers) == len(joined_users):  
                values = list(answers.values())
                most_common_answer = max(set(values), key=values.count)
                answers = {}
                  # 新しいゲームのために「回答済み」マークをリセットanswered_users = {}
                  # ゲームが終了したことを示すgame_in_progress = False取ったから要試験
                if most_common_answer == correct_answer:  
                    socketio.emit('correct_answer')  # 正解のイベントを発行
                    assign_role_to_user(1210253423002255411, 1214407932926631978)
                else:
                    socketio.emit('incorrect_answer')  # 不正解のイベントを発行
            return jsonify({'submitted': True})
        else:
            return jsonify({'message': 'あなたはすでに回答しました'})  # ユーザーが既に回答している場合
    else:
        abort(403)

def assign_role_to_user(user_id, role_id):
    guild = bot.guilds[0]  # Botが所属するギルドを取得
    member = discord.utils.get(guild.members, id=user_id)
    role = discord.utils.get(guild.roles, id=role_id)
    
    # メンバーに役職を付与
    if member and role:
        # 既にロールが付与されていないか確認する
        if role not in member.roles:
            coroutine = member.add_roles(role)
            asyncio.run_coroutine_threadsafe(coroutine, bot.loop)
        else:
            print(f"User {member} already has the role {role}.")
    else:
        print(f"Member or role not found. User ID: {user_id}, Role ID: {role_id}")


@app.route('/check_answer_status', methods=['GET'])
def check_answer_status():
    ip_address = request.remote_addr
    user_agent = request.user_agent.string
    unique_id = f"{ip_address}-{user_agent}"
    logging.info(f"check_answer_status: Generated unique_id: {unique_id}")

    if unique_id in answered_users:
        return jsonify({'submitted': True})  # ユーザーがすでに回答を提出している場合
    else:
        return jsonify({'submitted': False})  # ユーザーがまだ回答を提出していない場合


@socketio.on('connect')
def on_connect():
    channel = bot.get_channel(CHANNEL_ID)
    if isinstance(channel, discord.VoiceChannel):
        members_in_channel = [{'name': member.display_name, 'avatar_url': str(member.avatar.url) if member.avatar else None} for member in channel.members]
        emit('update_voice_members', members_in_channel)  # 通話メンバー情報を送信
        emit('update_joined_users', {'count': len(joined_users)})  # 現在の参加ユーザー数を送信

if __name__ == "__main__":
    t = Thread(target=run_bot)
    t.start()
    socketio.run(app, host='0.0.0.0', port=5000)
    

    

