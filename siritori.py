import discord
from discord.ext import commands
import jaconv

# --- 設定エリア ---
TOKEN = 'ここにステップ1で取得したトークンを貼り付け'
# ----------------

# ボットの設定（インテントの有効化）
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# しりとりの状態を管理する変数
game_active = False
word_history = []
last_word = ""

@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました！')

@bot.command()
async def start(ctx):
    """しりとりを開始するコマンド"""
    global game_active, word_history, last_word
    game_active = True
    word_history = []
    last_word = ""
    await ctx.send('🟢 しりとりを開始します！好きな単語を入力してください。')

@bot.command()
async def stop(ctx):
    """しりとりを強制終了するコマンド"""
    global game_active
    game_active = False
    await ctx.send('🔴 しりとりを終了しました。')

@bot.event
async def on_message(message):
    # ボット自身の発言は無視
    if message.author.bot:
        return

    # コマンド処理を優先させる
    await bot.process_commands(message)

    global game_active, word_history, last_word

    # ゲーム中でなければ何もしない
    if not game_active:
        return

    # 入力されたメッセージを取得
    content = message.content.strip()

    # --- 1. 文字種チェック（造語対策の簡易版） ---
    # ひらがな・カタカナ以外が含まれていたら無視（漢字などは読み方が複数あるため、今回は禁止にするのが簡単）
    # ※ 本格的にやるなら形態素解析ライブラリ(Janome等)が必要です
    for char in content:
        if not ('\u3040' <= char <= '\u309F' or '\u30A0' <= char <= '\u30FF' or char == 'ー'):
             # ひらがな・カタカナ・長音以外は無視してスルー（警告しても良い）
            return

    # カタカナをひらがなに変換して統一処理
    hiragana_word = jaconv.kata2hira(content)

    # --- 2. しりとりの繋がりチェック ---
    if last_word:
        # 前の単語の語尾を取得（小文字や長音の処理は簡易的に実装）
        prev_end = last_word[-1]
        if prev_end == 'ー': 
            prev_end = last_word[-2] # 長音の場合はその前の文字
        # 小文字（ゃゅょ等）を大文字に直す処理などは必要に応じて追加

        if hiragana_word[0] != prev_end:
            await message.channel.send(f'⚠️ 「{prev_end}」から始まる言葉ではありません！')
            return

    # --- 3. 「ん」で終わるかチェック ---
    if hiragana_word.endswith('ん'):
        await message.channel.send(f'😱 「{content}」... 「ん」がついたので負けです！\nゲーム終了！')
        game_active = False
        return

    # --- 4. 重複チェック ---
    if hiragana_word in word_history:
        await message.channel.send(f'⚠️ 「{content}」は既に出ています！')
        return

    # --- 正常な入力として受理 ---
    word_history.append(hiragana_word)
    last_word = hiragana_word
    await message.add_reaction('⭕') # 受理した合図