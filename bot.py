import discord
from discord.ext import commands
from discord import app_commands
import anthropic
import aiohttp
import base64
import io
import os
from PIL import Image, ImageEnhance, ImageFilter

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_KEY"]

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)
claude = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

def ameliorer_photo(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    max_size = (1200, 1200)
    img.thumbnail(max_size, Image.LANCZOS)
    img = ImageEnhance.Brightness(img).enhance(1.15)
    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = ImageEnhance.Color(img).enhance(1.3)
    img = img.filter(ImageFilter.SMOOTH_MORE)
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=95)
    output.seek(0)
    return output

def analyser_avec_claude(image_base64):
    prompt = """Tu es un expert Vinted. Analyse cette photo de vêtement ou accessoire.

Réponds UNIQUEMENT avec ce format exact, sans texte supplémentaire :

TITRE: [titre accrocheur max 60 caractères]
DESCRIPTION: [description vendeuse 3-4 phrases, mentionne les détails visibles]
CATÉGORIE: [ex: Hauts > T-shirts, Bas > Jeans, Chaussures > Baskets, etc.]
MARQUE: [marque si visible sur l'étiquette ou logo, sinon: Sans marque]
ÉTAT: [Neuf avec étiquette / Neuf sans étiquette / Très bon état / Bon état / Satisfaisant]
COULEURS: [maximum 2 couleurs principales]
PRIX: [entre X€ et Y€]

Pour le prix, base-toi sur le marché Vinted actuel selon l'état et la marque."""

    response = claude.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )
    return response.content[0].text

def formater_fiche(analyse):
    lignes = analyse.strip().split("\n")
    fiche = {}
    for ligne in lignes:
        if ":" in ligne:
            cle, valeur = ligne.split(":", 1)
            fiche[cle.strip()] = valeur.strip()

    embed = discord.Embed(
        title="✅ Ta fiche Vinted est prête !",
        color=0x09B1BA
    )
    embed.add_field(name="📝 Titre", value=fiche.get("TITRE", "—"), inline=False)
    embed.add_field(name="📄 Description", value=fiche.get("DESCRIPTION", "—"), inline=False)
    embed.add_field(name="📂 Catégorie", value=fiche.get("CATÉGORIE", "—"), inline=True)
    embed.add_field(name="👕 Marque", value=fiche.get("MARQUE", "—"), inline=True)
    embed.add_field(name="⭐ État", value=fiche.get("ÉTAT", "—"), inline=True)
    embed.add_field(name="🎨 Couleurs", value=fiche.get("COULEURS", "—"), inline=True)
    embed.add_field(name="💰 Prix suggéré", value=fiche.get("PRIX", "—"), inline=True)
    embed.set_footer(text="VintedHelper • Photo améliorée automatiquement")
    return embed

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot connecté : {bot.user}")

@bot.tree.command(name="vinted", description="Envoie une photo pour créer ta fiche Vinted")
async def vinted(interaction: discord.Interaction, photo: discord.Attachment):
    if not photo.content_type or not photo.content_type.startswith("image/"):
        await interaction.response.send_message("❌ Envoie une image (JPG, PNG...)", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(photo.url) as resp:
                image_bytes = await resp.read()

        photo_amelioree = ameliorer_photo(image_bytes)
        image_base64 = base64.standard_b64encode(photo_amelioree.read()).decode("utf-8")
        photo_amelioree.seek(0)

        analyse = analyser_avec_claude(image_base64)
        embed = formater_fiche(analyse)

        fichier = discord.File(photo_amelioree, filename="photo_amelioree.jpg")
        await interaction.followup.send(
            content="📸 **Photo améliorée :**",
            file=fichier,
            embed=embed
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {str(e)}")

bot.run(DISCORD_TOKEN)
