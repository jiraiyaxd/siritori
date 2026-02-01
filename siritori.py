import discord
from discord.ext import commands
import asyncio
import jaconv
import os
import re
import requests  # ★これを使います（Googleに聞くため）
from keep_alive import keep_alive

# --- 設定エリア ---
TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_CHANNEL_ID = 1294367814865518592

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

# 変数
game_active = False
word_history = []
last_word = ""

# --- ★★★ 革新的機能：Google IME APIで変換する関数 ★★★ ---
def google_convert(text):
    try:
        # Googleの非公開APIを叩いて、ひらがな変換を取得
        url = "http://www.google.com/transliterate"
        params = {
            'langpair': 'ja-Hira|ja', 
            'text': text
        }
        response = requests.get(url, params=params, timeout=3)
        data = response.json()
        
        # Googleからの返答を解析（一番確率の高い読みを取得）
        # dataの構造: [['漢字', ['かんじ', 'カンジ',...]], ...]
        reading = ""
        for segment in data:
            reading += segment[1][0] # 各文節の最初の候補（ひらがな）を結合
            
        return reading
    except:
        # ネットが繋がらないときなどは、そのまま返す
        return text
# ---------------------------------------------------------

@bot.event
async def on_ready():
    print(f'{bot.user} としてログインしました！')
    print('準備完了。「!start」で開始、「!stop」で終了です。')

@bot.command()
async def start(ctx):
    if ctx.channel.id != TARGET_CHANNEL_ID:
        return

    global game_active, word_history, last_word
    game_active = True
    word_history = []
    last_word = ""
    await ctx.send('🟢 しりとりスタート！')

@bot.command()
async def stop(ctx):
    if ctx.channel.id != TARGET_CHANNEL_ID:
        return

    global game_active
    score = len(word_history)
    game_active = False
    await ctx.send(f'🔴 しりとり終了！今回は **{score}回** 続いたよ！お疲れ様！')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if message.channel.id != TARGET_CHANNEL_ID:
        return

    await bot.process_commands(message)

    if message.content.startswith('!'):
        return

    global game_active, word_history, last_word

    if not game_active:
        return

    # スペース削除
    original_content = message.content.strip().replace(" ", "").replace("　", "")
    if not original_content:
        return

    # --- 読み仮名変換ロジック ---
    
    # 1. もしユーザーが「騎士道（きしどう）」のように手動指定してくれたらそれを最優先
    match = re.match(r'^(.*?)[（\(](.*)[）\)]$', original_content)
    
    if match:
        content_display = match.group(1) 
        reading_input = match.group(2)
        hiragana_word = jaconv.kata2hira(reading_input)
        content = content_display
    else:
        # 2. 手動指定がなければ、Google先生に聞く！
        content = original_content
        # カタカナを一旦ひらがなにしてから、漢字混じりの場合もGoogleで処理
        # Google APIは「漢字→ひらがな」が得意
        hiragana_word = google_convert(content)
        
        # 念の為 jaconv でカタカナ→ひらがな補正（Googleがカタカナで返すこともあるため）
        hiragana_word = jaconv.kata2hira(hiragana_word)

    # 記号を削除
    hiragana_word = re.sub(r'[^ぁ-んー]', '', hiragana_word)

    if not hiragana_word:
        return
    # ---------------------------

    # --- 禁止ワードチェック ---
    is_ng = False
    if content in NG_WORDS or original_content in NG_WORDS or hiragana_word in NG_WORDS:
        is_ng = True
    
    if is_ng and (content in SAFE_WORDS or original_content in SAFE_WORDS):
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
            # Google変換でも間違えることは稀にあるので、その場合は手動入力を促す
            await message.channel.send(
                f'⚠️ つながってないよ！\n'
                f'「{content}」は「{hiragana_word}」って読んだけど、「{prev_end}」から始まってないよ。\n'
                f'※読みが違う場合は `漢字（よみ）` のようにカッコで指定してね！'
            )
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
                await message.channel.send('🟢 新しいゲームをスタート！最初の単語をどうぞ！')
            else:
                await message.channel.send('🔴 お疲れ様！')

        except asyncio.TimeoutError:
            await message.channel.send('⏰ 時間切れのため終了！！！ ')
        
        return

    # --- 重複チェック ---
    if content in word_history:
        await message.channel.send(f'⚠️ 「{content}」はもう出たよ！')
        return

    # 受理
    word_history.append(content)
    last_word = hiragana_word
    
    await message.add_reaction('⭕')

# --- Webサーバーを立ち上げてからボットを起動 ---
keep_alive()

try:
    bot.run(TOKEN)
except:
    print("TOKENが見つかりません。環境変数が設定されているか確認してください。")

