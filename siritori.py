import discord
from discord.ext import commands
import pykakasi
import asyncio
import jaconv
import os
import re
import aiohttp
from keep_alive import keep_alive

# --- 設定エリア ---
TOKEN = os.getenv("DISCORD_TOKEN")
TARGET_CHANNEL_ID = 1294367814865518592

# ▼ 辞書（固定の読み方）
CUSTOM_DICTIONARY = {
    '騎士道': 'きしどう',
    '烏骨鶏': 'うこっけい',
    '海豚': 'いるか',
    '大熊猫': 'ぱんだ',
    '人気者': 'にんきもの',
    '鬼滅': 'きめつ',
    '呪術廻戦': 'じゅじゅつかいせん',
    'ランボルギーニ': 'らんぼるぎーに',
}

# ▼ 禁止ワード
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

# ▼ セーフワード
SAFE_WORDS = {
    '貸す', '化す', '粕', '羽目', '破滅', '品', '科', '支那', '雨', '尼', '巫女', '明日', '去る', '移転',
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

kks = pykakasi.kakasi()
game_active = False
word_history = []
last_word = ""

# --- Google API (非同期版) ---
async def google_convert(text):
    url = "http://www.google.com/transliterate"
    params = {'langpair': 'ja-Hira|ja', 'text': text}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=2) as response:
                if response.status == 200:
                    data = await response.json()
                    reading = ""
                    for segment in data:
                        reading += segment[1][0]
                    return reading
                else:
                    return None
    except:
        return None

@bot.event
async def on_ready():
    print(f'{bot.user} ログイン完了')

@bot.command()
async def start(ctx):
    if ctx.channel.id != TARGET_CHANNEL_ID: return
    global game_active, word_history, last_word
    game_active = True
    word_history = []
    last_word = ""
    await ctx.send('🟢 しりとりスタート！\n（※「？」を含む会話は無視します）')

@bot.command()
async def stop(ctx):
    if ctx.channel.id != TARGET_CHANNEL_ID: return
    global game_active
    score = len(word_history)
    game_active = False
    await ctx.send(f'🔴 終了！記録: {score}回')

@bot.event
async def on_message(message):
    if message.author.bot: return
    if message.channel.id != TARGET_CHANNEL_ID: return
    
    await bot.process_commands(message)
    if message.content.startswith('!'): return

    global game_active, word_history, last_word
    if not game_active: return

    original_content = message.content.strip().replace(" ", "").replace("　", "")
    if not original_content: return

    # ★ 「？」を含む発言は無視
    if '?' in original_content or '？' in original_content:
        return

    # ★ 先に「重複チェック」を行う（バグ修正の肝）
    # これで「反応しなかったからもう一回打った」時にエラーにならず、「既出だよ」で済みます
    if original_content in word_history:
        # すでにリストにある場合は、軽くリアクションだけ返すか、無視する
        await message.add_reaction('♻️') # 「もうあるよ」の合図
        return

    # --- 読み仮名変換 ---
    hiragana_word = ""
    if original_content in CUSTOM_DICTIONARY:
        hiragana_word = CUSTOM_DICTIONARY[original_content]
    else:
        match = re.match(r'^(.*?)[（\(](.*)[）\)]$', original_content)
        if match:
            hiragana_word = jaconv.kata2hira(match.group(2))
            content = match.group(1)
        else:
            content = original_content
            google_result = await google_convert(content)
            if google_result:
                hiragana_word = jaconv.kata2hira(google_result)
            else:
                converted = jaconv.alphabet2kana(content)
                result = kks.convert(converted)
                hiragana_word = ''.join([item['hira'] for item in result])

    hiragana_word = re.sub(r'[^ぁ-んー]', '', hiragana_word)
    if not hiragana_word: return

    # --- 禁止ワードチェック ---
    is_ng = False
    if content in NG_WORDS or original_content in NG_WORDS or hiragana_word in NG_WORDS:
        is_ng = True
    if is_ng and (content in SAFE_WORDS or original_content in SAFE_WORDS):
        is_ng = False
    
    if is_ng:
        try: await message.delete()
        except: pass
        await message.channel.send(f'🙅‍♂️ 禁止用語です！（{message.author.mention}）')
        return

    # --- 繋がりチェック ---
    # ここに到達する時点で「重複」は排除されているので、安心して比較できます
    if last_word:
        prev_end = last_word[-1]
        if prev_end == 'ー': prev_end = last_word[-2]
        trans_table = str.maketrans('ぁぃぅぇぉっゃゅょゎ', 'あいうえおつやゆよわ')
        prev_end_normalized = prev_end.translate(trans_table)

        if hiragana_word[0] != prev_end_normalized and hiragana_word[0] != prev_end:
            await message.channel.send(
                f'⚠️ つながってないよ！\n'
                f'前の言葉は「{word_history[-1]}（{prev_end}）」だよ。\n'
                f'（認識: {content} → {hiragana_word}）'
            )
            return

    # --- 「ん」チェック ---
    if hiragana_word.endswith('ん'):
        game_active = False
        score = len(word_history)
        q_msg = await message.channel.send(f'😱 「{content}（{hiragana_word}）」... 「ん」がついた！\n記録: **{score}回**\n\n🔄 再開 | ❌ 終了')
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
                await message.channel.send('🟢 再スタート！')
            else:
                await message.channel.send('🔴 お疲れ様！')
        except asyncio.TimeoutError:
            await message.channel.send('⏰ 時間切れ終了')
        return

    # 履歴に追加
    word_history.append(content)
    last_word = hiragana_word
    await message.add_reaction('⭕')

keep_alive()
try:
    bot.run(TOKEN)
except:
    print("TOKENエラー")
