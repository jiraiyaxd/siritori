import discord
from discord.ext import commands
import pykakasi
import asyncio
import jaconv
import os
import re
from keep_alive import keep_alive

# --- 設定エリア ---
TOKEN = os.getenv("DISCORD_TOKEN")

# ▼▼▼ 1. 禁止ワードリスト（ひらがな） ▼▼▼
NG_WORDS = {
    'あなる', 'あま', 'いんわい', 'いんぽ', 'いやがらせ', 'いらまちお', 'いんぴ', 'いまらちお', 'うせろ', 
    'うざい', 'うるさい', 'うぐ', 'えろ', 'おな', 'おなにー', 'おまんこ', 'おまんまん', 'おちんちん',
    'かんとんほうけい', 'かす', 'きじょうい', 'きちく', 'きえろ', 'きもい', 
    'きちがい', 'くそ', 'くそみそてくにっく', 'くそくらえ', 'くそったれ', 
    'くんに', 'くたばれ', 'くるくるぱー', 'くず', 'くずやろう', 'ころす', 
    'さいあく', 'さいこぱす', 'しね', 'しぬ', 'しばく', 
    'しんで', 'すまた', 'せくろす', 'せくはら', 'ちつ', 'ちんかす',
    'ちんげ', 'ちんこ', 'ちしょう', 'ちろう', 'ちんき', 'なかだし', 
    'はめ', 'へんたい', 'ほうけい', 'まんぽ', 'ますかき', 
    'まんこ', 'めくら', 'ろりーたこんぷれっくす', 'がいじ', 'じじい', 
    'じじー', 'じゅくじょ', 'だっちわいふ', 'でぶ', 'どかた', 'ばか', 
    'ばかやろう', 'ばーか', 'ばばあ', 'びっち', 'びっこ', 'ぶす', 'ぷりけつ', 'ぷっしー', 'ぺにす', 'ぐぐれかす',
    'へたれ', 'ほも', 'ほもたち', 'めす', '知的障害者', '精神障害者', '身体障害者','障害者','障碍者',
    '発達障害','キチガイ','ファシスト','ナチス','死ね','氏ね','殺す','殺せ','死刑','自殺','自害',
    'クズ','カス','ゴミ','屑','糞','糞野郎','痴漢','強姦','強制性交','レイプ','売春','売女','売人',
    '薬物','覚醒剤','大麻','麻薬','脱法ハーブ','ピル','媚薬','精液','潮吹き','中出し','顔射','種付け',
    '孕ませ','妊娠','堕胎','中絶','売春婦','売女','売人','援交','JC','JK','援助交際',
    'ロリコン','ショタコン','ロリ','ショタ','幼女','幼児','未成年','処女','童貞',
    'レズ','ゲイ','ホモ','バイセクシャル','ニューハーフ','オカマ','オナニー','自慰',
    'セックス','セクロス','エッチ','エロ','エロ動画','エロ画像','AV','かくせいざい',
}

# ▼▼▼ 2. セーフリスト ▼▼▼
SAFE_WORDS = {
    '貸す', '化す', '粕',
    '羽目', '破滅',
    '品', '科', '支那',
    '雨', '尼',
    '巫女',
    '明日',
    '去る',
    '移転',
}

# ボットの設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

kks = pykakasi.kakasi()

# 変数
game_active = False
word_history = []  # ここに漢字のまま保存するように変更します
last_word = ""     # しりとりの繋がりチェック用に、前の単語の「読み」だけ保存します
last_user_id = None

@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました！')
    print('準備完了。「!start」で開始、「!stop」で終了です。')

@bot.command()
async def start(ctx):
    global game_active, word_history, last_word, last_user_id
    game_active = True
    word_history = []
    last_word = ""
    last_user_id = None
    await ctx.send('🟢 しりとりスタート！')

@bot.command()
async def stop(ctx):
    global game_active
    score = len(word_history)
    game_active = False
    await ctx.send(f'🔴 しりとり終了！今回は **{score}回** 続いたよ！お疲れ様！')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.content.startswith('!'):
        return

    global game_active, word_history, last_word, last_user_id

    if not game_active:
        return

    # スペース削除
    content = message.content.strip().replace(" ", "").replace("　", "")

    if not content:
        return

    # 連続回答防止
    if last_user_id == message.author.id:
        await message.add_reaction('🚫')
        return

    # --- ローマ字対応 & 記号削除 ---
    converted_content = jaconv.alphabet2kana(content)
    result = kks.convert(converted_content)
    hiragana_word = ''.join([item['hira'] for item in result])

    # 記号を削除（読み仮名の判定用）
    hiragana_word = re.sub(r'[^ぁ-んー]', '', hiragana_word)

    if not hiragana_word:
        return
    # -------------------

    # --- 禁止ワードチェック ---
    is_ng = False
    if content in NG_WORDS or converted_content in NG_WORDS or hiragana_word in NG_WORDS:
        is_ng = True
    
    if is_ng and (content in SAFE_WORDS or converted_content in SAFE_WORDS):
        is_ng = False

    if is_ng:
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        await message.channel.send(f'🙅‍♂️ 禁止用語が含まれているから消すよ！（{message.author.mention}）')
        return

    # --- しりとり繋がりチェック ---
    if last_word:
        prev_end = last_word[-1]
        if prev_end == 'ー': 
            prev_end = last_word[-2]
        
        trans_table = str.maketrans('ぁぃぅぇぉっゃゅょゎ', 'あいうえおつやゆよわ')
        prev_end_normalized = prev_end.translate(trans_table)

        if hiragana_word[0] != prev_end_normalized and hiragana_word[0] != prev_end:
            await message.channel.send(f'⚠️ つながってないよ！\n「{content}（{hiragana_word}）」は、「{prev_end}」から始まらないよ。')
            return

    # --- 「ん」がついた時の処理 ---
    if hiragana_word.endswith('ん'):
        game_active = False
        score = len(word_history)

        q_msg = await message.channel.send(
            f'😱 「{content}（{hiragana_word}）」... 「ん」がついたからゲームオーバー！\n'
            f'📊 今回は **{score}回** 続いたよ！\n\n'
            f'**どうする？（30秒以内に選択）**\n'
            f'🔄 : もう一度最初から始める\n'
            f'❌ : 終了する'
        )
        
        await q_msg.add_reaction('🔄')
        await q_msg.add_reaction('❌')

        def check(reaction, user):
            return user != bot.user and str(reaction.emoji) in ['🔄', '❌'] and reaction.message.id == q_msg.id

        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)

            if str(reaction.emoji) == '🔄':
                game_active = True
                word_history = []
                last_word = ""
                last_user_id = None
                await message.channel.send('🟢 新しいゲームをスタート！最初の単語をどうぞ！')
            else:
                await message.channel.send('🔴 お疲れ様！')

        except asyncio.TimeoutError:
            await message.channel.send('⏰ 時間切れのため終了！！！ ')
        
        return

    # --- 重複チェック（修正箇所）---
    # 以前は hiragana_word でチェックしていましたが、
    # content（入力された文字そのもの）でチェックするように変更しました。
    if content in word_history:
        await message.channel.send(f'⚠️ 「{content}」はもう出たよ！')
        return

    # 受理
    # 履歴には「漢字」を保存し、次の人のために「読み仮名」をlast_wordに入れます
    word_history.append(content)
    last_word = hiragana_word
    last_user_id = message.author.id
    
    await message.add_reaction('⭕')

# --- Webサーバーを立ち上げてからボットを起動 ---
keep_alive()

try:
    bot.run(TOKEN)
except:
    print("TOKENが見つかりません。環境変数が設定されているか確認してください。")
