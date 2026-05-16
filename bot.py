import os
import discord
from dotenv import load_dotenv

from github_client import GitHubClient
from ollama_client import OllamaClient
from handlers import handle_message

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

github = GitHubClient()
ollama = OllamaClient()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    print(f"Repo: {os.environ['GITHUB_REPO']}  Model: {ollama.model}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if bot.user not in message.mentions:
        return

    content = message.content
    for mention in message.mentions:
        content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
    content = content.strip()

    if not content:
        await message.reply(
            f"Hey! Mention me with a question or request about `{os.environ['GITHUB_REPO']}`.\n"
            "Examples:\n"
            "- `@bot explain the architecture`\n"
            "- `@bot review PR #12`\n"
            "- `@bot write a PR that adds rate limiting to the API`\n"
            "- `@bot where is the authentication logic?`"
        )
        return

    async with message.channel.typing():
        await handle_message(message, content, github, ollama)


bot.run(os.environ["DISCORD_TOKEN"])
