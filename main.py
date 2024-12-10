# main.py
import os
import discord
import sqlite3
from discord.ext import commands
from config import settings, channel_logs
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
# В файле .env должен быть ключ: DISCORD_BOT_TOKEN=<ваш токен>
load_dotenv()

TOKEN = os.getenv('TOKEN')
print(TOKEN)  # Выводит ли ваш токен?
if not TOKEN:
    raise ValueError("Токен не найден! Добавьте TOKEN в ваш .env файл.")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=settings['prefix'], intents=intents)
data_base = sqlite3.connect('bot_test.db', timeout=10)
cursor = data_base.cursor()
game = discord.Game("FNAF: Security Breach Ruin")

# Создаем таблицы при запуске, если их нет
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    nickname TEXT,
    mention TEXT,
    money INTEGER
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS shop (
    id INTEGER PRIMARY KEY,
    name TEXT,
    type TEXT,
    cost INTEGER
);
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS server (
    id INTEGER PRIMARY KEY,
    logs INTEGER
);
''')

data_base.commit()


@bot.event
async def on_ready():
    print('Запуск бота успешен')
    print(f'Меня звать {bot.user.name}')
    print(f'Мой id в ДС {bot.user.id}')
    await bot.change_presence(activity=game)
    for guild in bot.guilds:
        print(f'ID подключенного сервера: {guild.id}')
        for member in guild.members:
            cursor.execute("SELECT id FROM users WHERE id=?", (member.id,))
            if cursor.fetchone() is None:
                # Очищаем имя от неалфанумерических символов
                f = "".join(c for c in member.name if c.isalnum())
                cursor.execute("INSERT INTO users (id, nickname, mention, money) VALUES (?, ?, ?, 0)",
                               (member.id, f, member.mention))
            data_base.commit()


@bot.command()
async def clear_user(ctx, user: discord.Member):
    s = ctx.author
    if s.guild_permissions.administrator:
        await ctx.channel.purge(limit=50, check=lambda m: m.author == user)
        # Предполагается, что logs хранится в таблице server
        cursor.execute("SELECT logs FROM server")
        res = cursor.fetchone()
        if res is not None and res[0] is not None:
            log_channel_id = res[0]
            channel = bot.get_channel(log_channel_id)
            if channel:
                await channel.send(f'<@{s.id}> удалил последние 50 сообщений от {user.mention}')
    else:
        embed = discord.Embed(title='У Вас недостаточно полномочий', color=0x42f566)
        await ctx.send(embed=embed)


@bot.command()
async def balance_user(ctx, mention):
    mention = str(mention).replace('!', '')
    cursor.execute("SELECT nickname, money FROM users WHERE mention=?", (mention,))
    row = cursor.fetchone()
    if row:
        embed = discord.Embed(title=f'Аккаунт пользователя {row[0]}', color=0x42f566)
        embed.add_field(name='Баланс:', value=f'{row[1]} поинтов', inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Пользователь не найден в базе.")


@bot.command()
async def delete(ctx, amount: int):
    s = ctx.author
    if amount > 100:
        amount = 100
    if s.guild_permissions.administrator:
        await ctx.channel.purge(limit=amount + 1)
        # Используем ID лог-канала, если он есть
        if channel_logs:
            channel = bot.get_channel(channel_logs)
            if channel:
                await channel.send(f'<@{s.id}> удалил {amount} сообщений')
    else:
        embed = discord.Embed(title='У Вас недостаточно полномочий', color=0x42f566)
        await ctx.send(embed=embed)


@bot.command()
async def give(ctx, mention, money):
    s = ctx.author
    if s.guild_permissions.administrator:
        try:
            mention = str(mention).replace('!', '')
            cursor.execute("SELECT money FROM users WHERE mention=?", (mention,))
            row = cursor.fetchone()
            if row:
                old_money = row[0]
                new_money = int(money) + old_money
                cursor.execute("UPDATE users SET money=? WHERE mention=?", (new_money, mention))
                data_base.commit()
                cursor.execute("SELECT nickname FROM users WHERE mention=?", (mention,))
                row = cursor.fetchone()
                if row:
                    embed = discord.Embed(title='Пополнение баланса', color=0x42f566)
                    embed.set_author(name='Community Bot')
                    embed.add_field(name='Оповещение', value=f'Баланс пользователя {row[0]} пополнен на {money} поинтов')
                    await ctx.send(embed=embed)
            else:
                await ctx.send("Пользователь не найден.")
        except Exception as E:
            print(f'give_money command error: {E}')
            embed = discord.Embed(title='Оповещение', color=0xFF0000)
            embed.add_field(name='Оповещение', value='Ошибка при выполнении программы.')
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title='У Вас недостаточно полномочий', color=0x42f566)
        await ctx.send(embed=embed)


@bot.command()
async def points_set(ctx, mention, money):
    mention = str(mention).replace('!', '')
    s = ctx.author
    if s.guild_permissions.administrator:
        cursor.execute("SELECT nickname FROM users WHERE mention=?", (mention,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE users SET money=? WHERE mention=?", (int(money), mention))
            data_base.commit()
            embed = discord.Embed(title='Корректировка баланса', color=0x42f566)
            embed.set_author(name='Community Bot')
            embed.add_field(name='Оповещение', value=f'Баланс пользователя {row[0]} скорректирован на {money} поинтов')
            await ctx.send(embed=embed)
        else:
            await ctx.send('Error: Пользователь не найден.')
    else:
        embed = discord.Embed(title='У Вас недостаточно полномочий', color=0x42f566)
        await ctx.send(embed=embed)


@bot.command()
async def points_give(ctx, user_id, amount):
    user_id = str(user_id).replace('!', '').replace('<@', '').replace('>', '')
    money = int(amount)
    # Проверяем баланс отправителя
    cursor.execute("SELECT money FROM users WHERE id=?", (ctx.author.id,))
    sender_row = cursor.fetchone()
    if sender_row:
        sender_balance = sender_row[0]
        if sender_balance >= money:
            cursor.execute("SELECT nickname, money FROM users WHERE id=?", (int(user_id),))
            receiver_row = cursor.fetchone()
            if receiver_row:
                receiver_balance = receiver_row[1] + money
                cursor.execute("UPDATE users SET money=? WHERE id=?", (receiver_balance, int(user_id)))

                new_sender_balance = sender_balance - money
                cursor.execute("UPDATE users SET money=? WHERE id=?", (new_sender_balance, ctx.author.id))
                data_base.commit()

                embed = discord.Embed(title='Передача баланса', color=0x42f566)
                embed.add_field(name='Оповещение', value=f'Баланс пользователя {receiver_row[0]} увеличен на {money} поинтов')
                await ctx.send(embed=embed)
            else:
                await ctx.send('Получатель не найден в базе.')
        else:
            await ctx.send('У вас не хватает поинтов!')
    else:
        await ctx.send('Ваш аккаунт не найден в базе.')


@bot.command()
async def balance(ctx):
    cursor.execute("SELECT nickname, money FROM users WHERE id=?", (ctx.author.id,))
    row = cursor.fetchone()
    if row:
        embed = discord.Embed(title=f'Аккаунт пользователя {row[0]}', color=0x42f566)
        embed.add_field(name='Баланс:', value=f'{row[1]} поинтов', inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Ваш аккаунт не найден.")


@bot.command()
async def buy_item(ctx, item_id):
    cursor.execute("SELECT name, cost FROM shop WHERE id=?", (item_id,))
    shop_row = cursor.fetchone()
    if not shop_row:
        await ctx.send("Товар не найден!")
        return

    nazvan, cena = shop_row
    cursor.execute("SELECT money FROM users WHERE id=?", (ctx.author.id,))
    user_row = cursor.fetchone()
    if not user_row:
        await ctx.send("Ваш аккаунт не найден.")
        return

    points = user_row[0]
    if points >= cena:
        vyxod = points - cena
        cursor.execute("UPDATE users SET money=? WHERE id=?", (vyxod, ctx.author.id))
        data_base.commit()
        embed = discord.Embed(title=f'Вы успешно приобрели товар {nazvan}', color=0x42f566)
        await ctx.send(embed=embed)

        if channel_logs:
            channel = bot.get_channel(channel_logs)
            if channel:
                await channel.send(f'<@{ctx.author.id}> купил товар под названием {nazvan}')
    else:
        await ctx.send("Нет денег!")


@bot.command()
async def add_item(ctx, item_id: int, nazva: str, tip: str, cena: int):
    s = ctx.author
    if s.guild_permissions.administrator:
        cursor.execute("SELECT id FROM shop WHERE id=?", (item_id,))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO shop (id, name, type, cost) VALUES (?, ?, ?, ?)", (item_id, nazva, tip, cena))
            data_base.commit()
            await ctx.send(f"Товар {nazva} успешно добавлен!")
        else:
            embed = discord.Embed(title=f'Такой id уже существует: {item_id}', color=0x42f566)
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title='У Вас недостаточно полномочий', color=0x42f566)
        await ctx.send(embed=embed)


bot.run(TOKEN)
