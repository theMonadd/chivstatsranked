import os
import asyncio
import discord
from discord import Embed
import re
from collections import Counter  # Import Counter class from collections module
from discord.ext import commands
from discord.ext.commands import check, CheckFailure
from datetime import datetime, timedelta, timezone
import time
import asyncpg
import traceback
import pytz
import json
from discord.ui import Button, View
from discord.ext import commands

from lts import LTSCog
from coin import CoinCog
from admin import AdminCommands
from privateservers import PrivateServers


# Database connection credentials
DATABASE = "chivstats"
USER = "postgresuser"
PASSWORD = "$tlMlb3728964"
HOST = "localhost"

# URL for the duels leaderboard and list of Discord guild IDs where the bot is active.
# Not including guild ids causes a delay in command update replication.
#DUELS_LEADERBOARD_URL = "https://chivstats.xyz/leaderboards/ranked_combat/" 
GUILD_IDS = [
             #878005964685582406, #Tournament grounds @funk
             #1163168644524687394, #Goblins @short
             #1108303022834069554,#Divided Loyalty @chillzone
             #1152345485747691560, #WILD WEST @SMD408
             #1213625786163011714, #Duelyard server @short
             #987187886094962828, #The Crucible, @kait
             1227017798916505780, #the Monad, @lambss_
             1228057171972063323, #blehtest, @lambss_
             ]

target_guild_id = 1227017798916505780  # ID of the 'Chivalry Unchained' guild
audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel

# Fetch the Discord bot token from environment variables
#TOKEN = os.getenv('CHIVBOT_KEY')
TOKEN = 'MTIyNzA3NzY5NzUyNDczMjAzNQ.GyLRw4.tLnKr6SR8O357RHfv-AU0uEl2lqhwYZV8eLIjo'
# Check if the token is retrieved successfully
if TOKEN:
    print("Discord bot token:", TOKEN)
else:
    print("Error: Discord bot token not found in environment variables.")

# Initialize the bot with command prefix and defined intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

    

# Indicate bot startup in console
print("Bot is starting up...")

# Global variables and constants
duel_queue = []
duo_queue = []

#leaderboard_classes = ["GlobalXp", "experienceknight"] # List of leaderboards (todo)

# Async function to establish a database connection
async def create_db_connection():
    return await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

# Async function to close a database connection
async def close_db_connection(conn):
    await conn.close()

async def get_discord_name_from_id(guild, discord_id):
    member = guild.get_member(discord_id)
    if member:
        return member.display_name  # or member.name for the actual Discord username
    return "Unknown User"

async def get_player_rank(conn, elo_rating):
    # This query counts how many players have a higher ELO rating than the given rating
    rank = await conn.fetchval("""
        SELECT COUNT(*) + 1 FROM ranked_players
        WHERE elo_duelsx > $1
    """, elo_rating)
    return rank

# Decorator to restrict command usage to specific channels
def is_channel_named(allowed_channel_names):
    async def predicate(interaction: discord.Interaction):
        if interaction.channel.name not in allowed_channel_names:
            raise commands.CheckFailure(
                "This command can only be used in specified channels."
            )
        return True
    return commands.check(predicate)
    r

async def fetch_username(user_id, conn):
    common_name = await conn.fetchval('SELECT common_name FROM ranked_players WHERE discordid = $1', user_id)
    return common_name if common_name else "Unknown"


bot.event
async def on_ready():
    print("Bot has started up.")
    try:
        # Establish a database connection
        conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

        # Define the IDs of the target guild and audit channel
        target_guild_id = 1227017798916505780  # ID of the 'Chivalry Unchained' guild
        audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel

        # Retrieve the target guild and audit channel
        target_guild = bot.get_guild(target_guild_id)
        audit_channel = target_guild.get_channel(audit_channel_id) if target_guild else None

        # Get the count and information of pending duels
        pending_duels_info = await conn.fetch("SELECT * FROM duel_confirmations WHERE status = 'pending'")

        # Create the summary message
        summary_message = "**Summary of Pending Duels**\n"
        summary_message += f"Total pending duels: {len(pending_duels_info)}\n"

        # Calculate total confirmations and find the user with the most confirmations
        confirmation_counts = Counter(duel_info['submitter_id'] for duel_info in pending_duels_info)
        if confirmation_counts:
            max_confirmation_user, max_confirmation_count = confirmation_counts.most_common(1)[0]

            # Fetch the name of the user with the most confirmations
            max_confirmation_user_name = await conn.fetchval(
                "SELECT discord_username FROM ranked_players WHERE discordid = $1", max_confirmation_user)
            summary_message += f"User with Most Confirmations: {max_confirmation_user_name} (Total Confirmations: {max_confirmation_count})\n"

        # Calculate total requests per channel
        channel_counts = Counter(duel_info['channel_id'] for duel_info in pending_duels_info)
        if channel_counts:
            max_pending_channel, max_pending_count = channel_counts.most_common(1)[0]
            summary_message += f"Channel with Most Pending Requests: {max_pending_channel} (Total Requests: {max_pending_count})\n"

        # Send the summary message to the audit channel
        if audit_channel:
            await audit_channel.send(summary_message)

        # Iterate through each pending duel, send report to audit channel
        for duel_info in pending_duels_info:
            # Extract data using attribute access or indexing
            submitter_id = duel_info['submitter_id']
            opponent_id = duel_info['opponent_id']
            submitter_score = duel_info['submitter_score']
            opponent_score = duel_info['opponent_score']
            winner_id = duel_info['winner_id']
            loser_id = duel_info['loser_id']
            message_id = duel_info['message_id']  # Include the message_id
            creation_time = duel_info['creation_time']  # Include creation_time

            # Construct and send the embed for pending duel confirmation
            embed = Embed(title="Pending Duel Confirmation", color=0xFFFF00)  # Yellow color
            embed.add_field(name="Message ID", value=message_id, inline=False)  # Include message_id
            embed.add_field(name="Submitter vs Opponent", value=f"{submitter_name} vs {opponent_name}",
                            inline=False)
            embed.add_field(name="Scores", value=f"({submitter_score}-{opponent_score})", inline=False)
            embed.add_field(name="Winner - Loser", value=f"{winner_name} - {loser_name}", inline=False)

            # Send the embed to the audit channel
            if audit_channel:
                await audit_channel.send(embed=embed)

        # Check expiration for each pending duel
        expired_duels_count = 0
        for duel_info in pending_duels_info:
            creation_time = duel_info['creation_time']  # Include creation_time

            # Check if creation_time is over 2 hours old
            if (datetime.now() - creation_time).total_seconds() > 7200:  # 2 hours in seconds
                # Extract message_id
                message_id = duel_info['message_id']

                # If creation_time is over 2 hours old, update the status of the duel to 'expired'
                await conn.execute("UPDATE duel_confirmations SET status = 'expired' WHERE message_id = $1", message_id)

                # Send an embed message for the expired duel to the audit channel
                expired_embed = Embed(title="Duel Expired", color=0xFF0000)  # Red color
                expired_embed.add_field(name="Message ID", value=message_id, inline=False)
                expired_embed.add_field(name="Status", value="Expired", inline=False)
                if audit_channel:
                    await audit_channel.send(embed=expired_embed)
                expired_duels_count += 1

        # Send summary of expired duels
        await audit_channel.send(f"Summary: {expired_duels_count} duels expired.")

    except Exception as e:
        # Handle exceptions
        error_msg = f"Error loading and processing pending confirmations: {e}"
        print(error_msg)
        if audit_channel:
            await audit_channel.send(f"```{error_msg}```")
    finally:
        # Close the database connection
        await conn.close()


        
# Global error handler for interactions
@bot.event
async def on_interaction_error(interaction, error):
    print(f"Interaction failed: {error}")
    await interaction.response.send_message("There was an error with this interaction. Please contact an administrator.", ephemeral=True)

# Ensure the bot has the necessary permissions to edit messages and manage messages in the channels it operates in.

async def send_audit_message(interaction):
    target_guild_id = 1227017798916505780  # ID of the 'Chivalry Unchained' guild
    audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel
    target_guild = bot.get_guild(target_guild_id)
    audit_channel = target_guild.get_channel(audit_channel_id) if target_guild else None

    if audit_channel:
        user_id = interaction.user.id
        user_display_name = interaction.user.display_name

        # Reconstruct the command from the interaction
        command_name = interaction.command.name
        entered_command = f"/{command_name}"

        # Check if the interaction has options and append them to the command
        if interaction.options:
            for option in interaction.options:
                # Append option name and value to the command string
                entered_command += f" {option.name}={option.value}"

        # Create and send the audit message
        audit_message = f"Command executed: {entered_command} by {user_display_name} (ID: {user_id})"
        await audit_channel.send(audit_message)

@bot.slash_command(guild_ids=GUILD_IDS, description="Lists the discords the chivbot is in, highlighting those with a chivstats-ranked channel.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def chivstats_network(interaction: discord.Interaction):
    await interaction.response.defer()
    # Predefined order for specific guilds
    priority_guilds = {
        'the Monad': None,
        'Tournament Grounds': None,
        'Chivalry 2 Unchained': None
    }
    other_guilds = []

    total_unique_members = set()  # Set to store unique member IDs across all servers

    for guild in bot.guilds:
        chivstats_channel = discord.utils.get(guild.text_channels, name="chivstats-ranked")
        checkmark = "✅" if chivstats_channel else "❌"

        # Count members in the chivstats-ranked channel, if it exists
        member_count = len(chivstats_channel.members) if chivstats_channel else 0

        # Add unique member IDs to the total count
        if chivstats_channel:
            for member in chivstats_channel.members:
                total_unique_members.add(member.id)

        guild_info = f"{checkmark} {guild.name} - ID: {guild.id} (👥{member_count})"
        
        # Place priority guilds in their specific slots
        if guild.name in priority_guilds:
            priority_guilds[guild.name] = guild_info
        else:
            other_guilds.append(guild_info)

    # Build the final server list with priority guilds first
    server_list = [info for info in priority_guilds.values() if info] + other_guilds
    description = "\n".join(server_list)
    description += f"\n\n🌍 Total unique members with visibility to #chivstats-ranked: 👥{len(total_unique_members)}"

    embed = discord.Embed(
        title="Chivstats 亗 Ranked Combat 亗 Network",
        description=description,
        color=discord.Color.blue()
    )
    
    # Set the footer text
    embed.set_footer(text="Add your clan discord to the Ranked Combat Network! Click the chivbot user profile for details or contact the Monad.")
    
    await interaction.followup.send(embed=embed)  # Sends the message to the channel where the command was used




@bot.slash_command(guild_ids=GUILD_IDS, description="RANKED COMBAT: Provides help information about chivbot commands.")
async def help(interaction: discord.Interaction):
    commands_info = {
        "/register": "Links your Discord account to a new user. Usage: `/register`", # was `/register [PlayFabID]` before
        "/submit_duel": "Submit the result of a duel between two players. Usage: `/submit_duel @User1 [score1] @User2 [score2]`",
        "/rank": "Displays the rank and stats of a player. Usage: `/rank [@User] (target member) or /rank [alias]. (target string)""`",
        "/stats": "Displays stats based of Discord ID And User Names. Different Stats from Rank.",
        "/status": "Checks registered status. Usage: `/status based on Discord User or Alias`",
        "/retire": "Retire your account from ranked matches. Usage: `/retire`",
        "/reactivate": "Reactivate your account for ranked matches. Usage: `/reactivate`",
        "/setname": "Manually set an in-game name. Usage: `/setname [name]`",
        "/elo": "Explains how the ELO system works. Usage: `/elo (public)`",
        "/duo_teams": "List all duo teams, their players, and ELO ranks in descending order. Usage: `/duo_teams`",
        "/duo_setup_team": "Create and update the name of your duo team. Usage: `/duo_setup_team @TeamMember [team_name]`",
        "/submit_duo": "Submit the result of a 2v2 duel between two teams. Usage: `/submit_duo @TeamMember [team_score] @Enemy1 @Enemy2 [enemy_score]`"
    }
    
    embed = discord.Embed(
        title="Chivbot Help",
        description="Here are the commands you can use with Chivbot:",
        color=discord.Color.blue()
    )
    for cmd, desc in commands_info.items():
        embed.add_field(name=cmd, value=desc, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def get_display_name_from_ranked_players(playfabid):
    conn = await create_db_connection()
    try:
        row = await conn.fetchrow("SELECT gamename, common_name FROM ranked_players WHERE playfabid = $1", playfabid)
        return row['gamename'] if row and row['gamename'] else (row['common_name'] if row else "Unknown Player")
    finally:
        await close_db_connection(conn)

async def format_playfab_id_with_url(playfabid):
    conn = await create_db_connection()
    try:
        most_common_alias = await get_most_common_alias(conn, playfabid)
        alias_display = f"{playfabid} ('{most_common_alias}')"
        return f"[{alias_display}]" # deleted for now (https://chivstats.xyz/leaderboards/player/{playfabid}/)
    finally:
        await close_db_connection(conn)

async def get_most_common_alias(conn, playfabid):
    try:
        result = await conn.fetchrow("SELECT alias_history FROM players WHERE playfabid = $1", playfabid)
        if result and result['alias_history']:
            alias_history = json.loads(result['alias_history'])
            most_common_alias = max(alias_history, key=alias_history.get, default="Unknown Alias")
            return most_common_alias
        else:
            return "Unknown Alias"
    except Exception as e:
        print(f"Error in get_most_common_alias: {e}")
        return "Error"

async def get_playfabid_of_discord_id(conn, discord_id):
    result = await conn.fetchrow("SELECT playfabid FROM ranked_players WHERE discordid = $1", discord_id)
    return result[0] if result else None

async def get_common_name_from_ranked_players(conn, playfabid):
    result = await conn.fetchrow("SELECT common_name FROM ranked_players WHERE playfabid = $1", playfabid)

    if result and result['common_name']:  # Return the common name if found
        return result['common_name']
    else:  # If no common name found in ranked_players, look in the players table
        return await get_most_common_alias(conn, playfabid)


import re

def remove_mentions(text):
    # Regular expression pattern to match Discord user and role mentions
    pattern = r'<@!?[0-9]+>|<@&[0-9]+>'
    # Replace found mentions with an empty string
    return re.sub(pattern, '', text)

async def echo_to_guilds(interaction, embed, echo_channel_name):
    origin_guild_name = interaction.guild.name
    guild_names_sent_to = []

    for guild in bot.guilds:
        echo_channel = discord.utils.get(guild.text_channels, name=echo_channel_name)
        if echo_channel and echo_channel.id != interaction.channel.id:
            try:
                embed_copy = embed.copy()

                # Use the custom remove_mentions function
                if embed_copy.title:
                    embed_copy.title = remove_mentions(embed_copy.title)
                if embed_copy.description:
                    embed_copy.description = remove_mentions(embed_copy.description)

                # Optionally, strip mentions from fields
                for field in embed_copy.fields:
                    field.name = remove_mentions(field.name)
                    field.value = remove_mentions(field.value)

                await echo_channel.send(embed=embed_copy)
                guild_names_sent_to.append(guild.name)
            except Exception as e:
                print(f"Failed to send message to {echo_channel.name} in {guild.name}: {e}")

    if guild_names_sent_to:
        audit_message = f"Message from {origin_guild_name} echoed to the following guilds: {', '.join(guild_names_sent_to)}"
    else:
        audit_message = f"Message from {origin_guild_name} was not echoed to any other guilds."
    return audit_message


@bot.slash_command(guild_ids=GUILD_IDS, description="Calculate the odds of one player beating another.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def odds(interaction: discord.Interaction, player1: discord.Member, player2: discord.Member):
    await interaction.response.defer()

    conn = await create_db_connection()
    try:
        # Fetch necessary data
        elo_player1, playfabid_player1 = await get_player_data(conn, player1.id)
        elo_player2, playfabid_player2 = await get_player_data(conn, player2.id)

        total_matches_player1 = await conn.fetchval("SELECT COUNT(*) FROM duels WHERE winner_playfabid = $1 OR loser_playfabid = $1", playfabid_player1)
        total_matches_player2 = await conn.fetchval("SELECT COUNT(*) FROM duels WHERE winner_playfabid = $1 OR loser_playfabid = $1", playfabid_player2)

        head_to_head_stats, total_kills_deaths = await fetch_head_to_head_detailed(conn, playfabid_player1, playfabid_player2)

        # Calculate odds
        odds_player1, odds_player2, chance_p1, chance_p2 = calculate_odds(elo_player1, elo_player2)

        # Create the embed
        embed = discord.Embed(title="Duel Odds Analysis", color=discord.Color.blue())
        embed.add_field(
            name="Matchup Odds of Winning",
            value=f"{player1.display_name}: {odds_player1}:1 ({chance_p1}%)\n{player2.display_name}: {odds_player2}:1 ({chance_p2}%)",
            inline=False
        )

        avg_winner, h2h_wins, h2h_losses, total_h2h_matches, win_rate, h2h_percent_p1, h2h_percent_p2 = calculate_head_to_head_stats(
            head_to_head_stats, playfabid_player1, playfabid_player2, total_matches_player1, total_matches_player2, player1.display_name, player2.display_name
        )

        # Add head-to-head statistics to the embed
        embed.add_field(
            name=f"Pair's Head-to-Head Record ({total_h2h_matches} Duels)",
            value=f"Average Winner: {avg_winner} ({h2h_wins}:{h2h_losses} - {win_rate}%)",
            inline=False
        )
        embed.add_field(
            name=f"{player1.display_name}'s Kills to Deaths vs {player2.display_name}",
            value=total_kills_deaths,
            inline=False
        )
        embed.add_field(
            name="Times the pair fought eachother vs others.",
            value=(
                f"{player1.display_name} - {h2h_percent_p1}% ({total_h2h_matches} duels of {total_matches_player1})\n"
                f"{player2.display_name} - {h2h_percent_p2}% ({total_h2h_matches} duels of {total_matches_player2})"
            ),
            inline=False
        )
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
    finally:
        await close_db_connection(conn)

def calculate_confidence(head_to_head_stats, id_player1, id_player2):
    wins_player1 = sum(1 for match in head_to_head_stats if match['winner_playfabid'] == id_player1)
    losses_player1 = sum(1 for match in head_to_head_stats if match['loser_playfabid'] == id_player1)
    wins_player2 = sum(1 for match in head_to_head_stats if match['winner_playfabid'] == id_player2)
    losses_player2 = sum(1 for match in head_to_head_stats if match['loser_playfabid'] == id_player2)

    total_matches = len(head_to_head_stats)

    if total_matches > 0:
        confidence_p1 = round((wins_player1 / total_matches) * 100, 2)
        confidence_p2 = round((wins_player2 / total_matches) * 100, 2)
    else:
        confidence_p1 = confidence_p2 = 50  # Equal confidence if no matches played

    return confidence_p1, confidence_p2, total_matches, wins_player1, losses_player1, wins_player2, losses_player2

def calculate_odds(elo_player1, elo_player2):
    expected_score_p1 = 1 / (1 + 10 ** ((elo_player2 - elo_player1) / 400))
    odds_player1 = round((1 / expected_score_p1) - 1, 2)
    chance_p1 = round(expected_score_p1 * 100, 2)
    expected_score_p2 = 1 / (1 + 10 ** ((elo_player1 - elo_player2) / 400))
    odds_player2 = round((1 / expected_score_p2) - 1, 2)
    chance_p2 = round(expected_score_p2 * 100, 2)
    return odds_player1, odds_player2, chance_p1, chance_p2

async def get_player_data(conn, discord_id):
    elo = await conn.fetchval("SELECT elo_duelsx FROM ranked_players WHERE discordid = $1", discord_id)
    playfabid = await conn.fetchval("SELECT playfabid FROM ranked_players WHERE discordid = $1", discord_id)
    return elo, playfabid

async def fetch_head_to_head(conn, playfabid1, playfabid2):
    return await conn.fetch("""
        SELECT winner_playfabid, loser_playfabid FROM duels
        WHERE (winner_playfabid = $1 AND loser_playfabid = $2) OR (winner_playfabid = $2 AND loser_playfabid = $1)
    """, playfabid1, playfabid2)

async def fetch_head_to_head_detailed(conn, playfabid1, playfabid2):
    # Fetch head-to-head matches
    head_to_head_matches = await conn.fetch("""
        SELECT winner_playfabid, loser_playfabid, winner_score, loser_score FROM duels
        WHERE (winner_playfabid = $1 AND loser_playfabid = $2) OR (winner_playfabid = $2 AND loser_playfabid = $1)
    """, playfabid1, playfabid2)

    # Count wins for each player
    wins_for_playfabid1 = sum(1 for match in head_to_head_matches if match['winner_playfabid'] == playfabid1)
    wins_for_playfabid2 = len(head_to_head_matches) - wins_for_playfabid1

    # Determine which player to focus on based on who has more overall wins
    focused_playfabid = playfabid1 if wins_for_playfabid1 > wins_for_playfabid2 else playfabid2

    # Initialize counters for the focused player's kills and deaths
    total_kills = 0
    total_deaths = 0

    # Iterate over matches to calculate kills and deaths for the focused player
    for match in head_to_head_matches:
        if match['winner_playfabid'] == focused_playfabid:
            # Add winner's kills and loser's score (as deaths for winner in that match)
            total_kills += match['winner_score']
            total_deaths += match['loser_score']
        else:
            # When the focused player loses, their kills are reflected in the loser's score
            total_kills += match['loser_score']
            # Add winner's score as deaths for the focused player
            total_deaths += match['winner_score']

    return head_to_head_matches, f"{total_kills} Kills, {total_deaths} Deaths"

def calculate_head_to_head_stats(head_to_head_stats, id_player1, id_player2, total_p1, total_p2, name_player1, name_player2):
    h2h_wins_p1 = sum(1 for match in head_to_head_stats if match['winner_playfabid'] == id_player1)
    h2h_losses_p1 = sum(1 for match in head_to_head_stats if match['loser_playfabid'] == id_player1)
    total_h2h_matches = len(head_to_head_stats)

    win_rate = round((h2h_wins_p1 / total_h2h_matches) * 100, 2) if total_h2h_matches > 0 else 0

    if h2h_wins_p1 > h2h_losses_p1:
        avg_winner = name_player1
    elif h2h_wins_p1 < h2h_losses_p1:
        avg_winner = name_player2
    else:
        avg_winner = "Equal"

    h2h_percent_p1 = round((total_h2h_matches / total_p1) * 100, 2) if total_p1 > 0 else 0
    h2h_percent_p2 = round((total_h2h_matches / total_p2) * 100, 2) if total_p2 > 0 else 0

    return avg_winner, h2h_wins_p1, h2h_losses_p1, total_h2h_matches, win_rate, h2h_percent_p1, h2h_percent_p2

@bot.slash_command(guild_ids=GUILD_IDS, description="Display the top 10 leaderboard for duels or duos.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def leaderboard(interaction: discord.Interaction, category: str):
    if category.lower() not in ['duel', 'duels', 'duo', 'duos']: # original string ['duel', 'duels', 'duo', 'duos']:
        await interaction.response.send_message("Invalid category. Please enter 'duel(s)' for duel leaderboard or 'duo(s)' for duo leaderboard.", ephemeral=True)
        return

    await interaction.response.defer()

    conn = await create_db_connection()
    try:
        embed = discord.Embed(title=f"{category.title()} Leaderboard", color=discord.Color.blue())

        if category.lower() in ['duel', 'duels']:
            players = await conn.fetch("""
                SELECT discordid, discord_username, elo_duelsx, playfabid FROM ranked_players
                WHERE retired = FALSE
                ORDER BY elo_duelsx DESC
                LIMIT 10
            """)

            tier_assignments = await calculate_tiers(conn)
            embed = discord.Embed(title=f"{category.title()} Leaderboard", color=discord.Color.blue())

            leaderboard_lines = []
            for index, player in enumerate(players, 1):
                discord_id = player['discordid']
                playfabid = player['playfabid']
                elo_rating = round(player['elo_duelsx'])  # Round the ELO rating
                tier_emoji = tier_assignments.get(playfabid, '❓')  # Get tier emoji
                discord_name = player['discord_username']  # Fetch the display name

                leaderboard_line = f"{index}. {tier_emoji} {discord_name} - {elo_rating}"
                leaderboard_lines.append(leaderboard_line)

            leaderboard_text = "\n".join(leaderboard_lines)
            embed.description = leaderboard_text

            await interaction.followup.send(embed=embed)

        elif category.lower() in ['duo', 'duos']:
              teams = await conn.fetch("""
                  SELECT dt.team_name, dt.elo_rating, rp1.id as player1_id, rp2.id as player2_id
                  FROM duo_teams dt
                  JOIN ranked_players rp1 ON dt.player1_id = rp1.playfabid
                  JOIN ranked_players rp2 ON dt.player2_id = rp2.playfabid
                  WHERE dt.retired = FALSE
                  ORDER BY dt.elo_rating DESC
                  LIMIT 10
              """)

              rank_tier = [f"{index}." for index, _ in enumerate(teams, 1)]
              team_names = [team['team_name'] for team in teams]
              elos = [str(team['elo_rating']) for team in teams]

              # Fetch player common names using separate queries
              player_names = []
              async def get_common_name(player_id):
                  player = await conn.fetchval("""
                      SELECT common_name FROM ranked_players WHERE id = $1;
                  """, player_id)
                  return player if player else "Unknown Name"  # Set a default value for missing names

              for team in teams:
                  player1_name = await get_common_name(team['player1_id'])
                  player2_name = await get_common_name(team['player2_id'])
                  player_names.append(f"{player1_name} & {player2_name}")

              combined_info = [f"{rank_tier[i]} **{team_names[i]}** (ELO: **{elos[i]}**) - **{player_names[i]}**" for i in range(len(rank_tier))]
              embed.add_field(name="Top Teams", value="\n".join(combined_info))



              await interaction.followup.send(embed=embed)
    finally:
        await close_db_connection(conn)
        

async def update_leaderboard_message():
    conn = await create_db_connection()
    try:
        embed = discord.Embed(title="Duels Leaderboard", color=discord.Color.blue())

        players = await conn.fetch("""
            SELECT discordid, elo_duelsx, discord_username FROM ranked_players
            WHERE retired = FALSE
            ORDER BY elo_duelsx DESC
            LIMIT 10
        """)

        tier_assignments = await calculate_tiers(conn)

        leaderboard_lines = []
        for index, player in enumerate(players, 1):
            discord_id = player['discordid']
            elo_rating = round(player['elo_duelsx'])
            discord_username = player['discord_username']
            tier_emoji = tier_assignments.get(discord_id, '❓')
            
            leaderboard_line = f"{index}. {tier_emoji} {discord_username} - {elo_rating}"
            leaderboard_lines.append(leaderboard_line)

        leaderboard_text = "\n".join(leaderboard_lines)
        embed.description = leaderboard_text

        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name="ranked-leaderboards")
            if channel:
                last_message = await channel.history(limit=1).flatten()
                last_message = last_message[0] if last_message else None

                if last_message and last_message.author == bot.user:
                    await last_message.edit(embed=embed)
                else:
                    await channel.send(embed=embed)

    finally:
        await close_db_connection(conn)

####################################
#ELO Duel related code

async def calculate_tiers(conn):
    # Fetch all active players' ELO scores
    active_players = await conn.fetch(
        "SELECT discordid, elo_duelsx FROM ranked_players WHERE retired = FALSE AND matches > 0 ORDER BY elo_duelsx DESC"
    )

    # Extract ELO scores into a list
    elo_scores = [(player['discordid'], player['elo_duelsx']) for player in active_players]

    # Calculate the total number of active players
    total_players = len(elo_scores)
    print(f"Total active players: {total_players}")

    # Use actual Discord emoji in tier assignments instead of the colon format
    tier_assignments = {
        elo_scores[0][0]: '🥇',  # first place medal
        elo_scores[1][0]: '🥈',  # second place medal
        elo_scores[2][0]: '🥉'   # third place medal
    }
    emoji_mapping = {
        ':regional_indicator_s:': '🇸',  # regional indicator symbol letter S
        ':regional_indicator_a:': '🇦',  # regional indicator symbol letter A
        ':regional_indicator_b:': '🇧',  # regional indicator symbol letter B
        ':regional_indicator_c:': '🇨',  # regional indicator symbol letter C
        ':regional_indicator_d:': '🇩'   # regional indicator symbol letter D
    }
    # Adjust the list of active players to exclude the top 3 for tier calculations
    remaining_players = elo_scores[3:]

    # Define the percentage cutoffs for each tier
    tier_cutoffs = {
        ':regional_indicator_s:': 0.10,
        ':regional_indicator_a:': 0.20,
        ':regional_indicator_b:': 0.50,
        ':regional_indicator_c:': 0.80,
        ':regional_indicator_d:': 1.00  # 100% for the remaining players
    }

    # Calculate the index cutoffs based on the percentage
    tier_indices = {tier: int(percentage * (total_players - 3)) for tier, percentage in tier_cutoffs.items()}  # Adjust for top 3

    # Assign tiers to each remaining player based on their ELO score
    current_index = 0
    for tier, index_cutoff in tier_indices.items():
        while current_index < index_cutoff:
            if current_index < len(remaining_players):
                discordid, elo_score = remaining_players[current_index]
                tier_assignments[discordid] = emoji_mapping[tier]
                current_index += 1
            else:
                break

    # Debug print to check the final assignments
    print(f"Final tier assignments: {tier_assignments}")

    return tier_assignments

async def log_duel(conn, submitting_discordid, winner_discordid, winner_score, winner_elo, loser_discordid, loser_score, loser_elo):
    try:
        await conn.execute("""
            INSERT INTO duels (submitting_discordid, winner_discordid, winner_score, winner_elo, loser_discordid, loser_score, loser_elo)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            submitting_discordid, winner_discordid, winner_score, winner_elo, loser_discordid, loser_score, loser_elo)
    except Exception as e:
        print(f"Error in log_duel: {e}")
        
def calculate_elo(R, K, games_won, games_played, opponent_rating, c=400):
    """
    Calculate the new ELO rating based on games played.
    :param R: Current ELO rating
    :param K: Weight of the game
    :param games_won: Total games won
    :param games_played: Total games played (should be 1 for a duel)
    :param opponent_rating: ELO rating of the opponent
    :param c: Constant determining the influence of the rating difference
    :return: New ELO rating as a float
    """
    expected_score = 1 / (1 + 10 ** ((opponent_rating - R) / c))
    actual_score = games_won / games_played
    new_rating = R + K * (actual_score - expected_score)
    return new_rating  # Return as float for precise calculation

#async def update_leaderboard_message():
    # Function to update the leaderboard message
    # Implementation of this function depends on how the leaderboard message is managed in your bot

@bot.slash_command(guild_ids=GUILD_IDS, description="Submit the result of a duel between two players.")
async def submit_duel(interaction: discord.Interaction, submitter_score: int, opponent: discord.Member, opponent_score: int):
    await interaction.response.defer()
    duel_message = None
    try:
        if interaction.user.id == opponent.id:
            await interaction.followup.send("You cannot duel yourself!", ephemeral=True)
            return

        conn = await create_db_connection()

        records = await conn.fetch("SELECT discordid, retired FROM ranked_players WHERE discordid = ANY($1::bigint[])", [interaction.user.id, opponent.id])
        retired_players = {record['discordid']: record['retired'] for record in records if record['retired']}

        if retired_players:
            message = ""
            for discord_id, retired in retired_players.items():
                if retired:
                    mention = f"<@{discord_id}>"
                    message += f"{mention} has retired. Please reactivate your account using /reactivate.\n" if discord_id == interaction.user.id else f"Please ask {mention} to reactivate.\n"
            await interaction.followup.send(message, ephemeral=True)
            return

        submitter_discordid = interaction.user.id
        opponent_discordid = opponent.id

        winner, loser = (interaction.user, opponent) if submitter_score > opponent_score else (opponent, interaction.user)
        winner_score, loser_score = max(submitter_score, opponent_score), min(submitter_score, opponent_score)
        winner_label = " (winner)" if winner != interaction.user else " (winner, submitter)"
        submitter_label = " (submitter)" if interaction.user == winner else ""

        command_text = f"/submit_duel @{interaction.user.display_name} {submitter_score} @{opponent.display_name} {opponent_score}"

        target_guild_id = 1227017798916505780  # ID of the 'Chivalry Unchained' guild
        audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel
        target_guild = bot.get_guild(target_guild_id)
        audit_channel = target_guild.get_channel(audit_channel_id) if target_guild else None

        if audit_channel:
            audit_message = f"Command executed: `/submit_duel {submitter_score} @{opponent.display_name} {opponent_score}` by {interaction.user.display_name} ({interaction.user.id})"
            await audit_channel.send(audit_message)

        embed = discord.Embed(title="Duel Result (UNVERIFIED)", description=f"Command: `{command_text}`", color=discord.Color.orange())
        embed.add_field(name="Matchup", value=f"{winner.display_name}{winner_label} vs {loser.display_name}{submitter_label}", inline=False)
        embed.add_field(name="Score", value=f"{winner_score}-{loser_score}", inline=True)

        duel_message = await interaction.followup.send(embed=embed)

        try:
            await conn.execute("""
                INSERT INTO duel_confirmations (message_id, channel_id, submitter_id, opponent_id, winner_id, loser_id, submitter_score, opponent_score, winner_score, loser_score, status) 
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'pending')
            """, duel_message.id, duel_message.channel.id, interaction.user.id, opponent.id, winner.id, loser.id, submitter_score, opponent_score, winner_score, loser_score)
        finally:
            await conn.close()

        cst_timezone = pytz.timezone('America/Chicago')
        current_time_cst = datetime.now(pytz.utc).astimezone(cst_timezone)
        expiration_time_cst = current_time_cst + timedelta(minutes=60)
        expiration_unix_timestamp = int(expiration_time_cst.timestamp())

        verification_request = f"This result will automatically expire <t:{expiration_unix_timestamp}:R>.\n"
        verification_request += f"{opponent.mention} please react to this message confirming or denying the match results."
        embed.description += f"\n\n{verification_request}"

        verification_message = await interaction.followup.send(f"{opponent.mention} please react to the above message confirming or denying the match results.")
        view = ConfirmationView(interaction.user.id, opponent.id, duel_message, winner.id, loser.id, winner_score, loser_score, verification_message=verification_message)
        await duel_message.edit(view=view)

    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(error_message)
        traceback.print_exc()
        if audit_channel:
            await audit_channel.send(embed=discord.Embed(
                title="Duel Confirmation Error",
                description=error_message,
                color=discord.Color.red()
            ))
        await interaction.followup.send("An error occurred while processing the duel.", ephemeral=True)


class ConfirmationView(discord.ui.View):
    def __init__(self, submitter_id, non_submitter_id, duel_message, winner_id, loser_id, winner_score, loser_score, verification_message=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.submitter_id = submitter_id
        self.non_submitter_id = non_submitter_id
        self.opponent_id = non_submitter_id
        self.duel_message = duel_message
        self.winner_id = winner_id
        self.loser_id = loser_id
        self.winner_score = winner_score
        self.loser_score = loser_score
        self.verification_message = verification_message
        self.duel_message_id = duel_message.id
        self.channel_id = duel_message.channel.id

        self.confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.green, custom_id=f"confirm_{duel_message.id}")
        self.confirm_button.callback = self.confirm_button_clicked

        self.deny_button = discord.ui.Button(label="Deny", style=discord.ButtonStyle.red, custom_id=f"deny_{duel_message.id}")
        self.deny_button.callback = self.deny_button_clicked

        self.add_item(self.confirm_button)
        self.add_item(self.deny_button)

        # Keep track of button click state
        self.confirm_clicked = False
        self.deny_clicked = False

        # Disable buttons for the submitter who submitted the results
        if self.submitter_id == duel_message.author.id:
            self.confirm_button.disabled = True
            self.deny_button.disabled = True

    async def confirm_button_clicked(self, interaction: discord.Interaction):
        if interaction.user.id == self.non_submitter_id and not self.confirm_clicked:
            self.confirm_clicked = True
            await self.handle_confirm(interaction, self.winner_score, self.loser_score)
        else:
            await interaction.response.send_message("Only the challenged player can confirm this duel or you have already confirmed.", ephemeral=True)

    async def deny_button_clicked(self, interaction: discord.Interaction):
        if interaction.user.id in [self.submitter_id, self.non_submitter_id] and not self.deny_clicked:
            self.deny_clicked = True
            await self.handle_deny(interaction)
        else:
            await interaction.response.send_message("You are not authorized to deny this duel or you have already denied.", ephemeral=True)

    async def handle_deny(self, interaction: discord.Interaction):
        submitter_name = interaction.guild.get_member(self.submitter_id).display_name
        opponent_name = interaction.guild.get_member(self.non_submitter_id).display_name

        updated_embed = discord.Embed(
            title="Duel Cancelled",
            description=f"Duel between {submitter_name} and {opponent_name} has been cancelled by {interaction.user.display_name}.",
            color=discord.Color.red()
        )

        self.clear_buttons()
        await self.duel_message.edit(embed=updated_embed, view=self)

        if self.verification_message:
            await self.verification_message.delete()
        await interaction.response.send_message("Duel cancelled.", ephemeral=True)
        
        def clear_buttons(self):
        # Clear all buttons from the view
            self.children.clear()  # This will remove all UI elements from the view
            # Update the message to show the view without buttons
            return self.duel_message.edit(view=self)

async def handle_confirm(self, interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        await self.clear_buttons()
        conn = await create_db_connection()

        target_guild_id = 1227017798916505780  # ID of the 'Chivalry Unchained' guild
        audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel

        target_guild = bot.get_guild(target_guild_id)
        audit_channel = target_guild.get_channel(audit_channel_id) if target_guild else None

        winner_data = await conn.fetchrow("SELECT discordid, elo_duelsx FROM ranked_players WHERE discordid = $1", self.winner_id)
        loser_data = await conn.fetchrow("SELECT discordid, elo_duelsx FROM ranked_players WHERE discordid = $1", self.loser_id)

        if winner_data and loser_data:
            winner_discordid, winner_rating = winner_data
            loser_discordid, loser_rating = loser_data
            await self.clear_buttons()
            new_winner_elo_exact = calculate_elo(winner_rating, 32, 1, 1, loser_rating)
            new_loser_elo_exact = calculate_elo(loser_rating, 32, 0, 1, winner_rating)

            winner_elo_change = round(new_winner_elo_exact - winner_rating)
            loser_elo_change = round(new_loser_elo_exact - loser_rating)
            winner_elo_change_formatted = f"+{winner_elo_change}" if winner_elo_change >= 0 else f"{winner_elo_change}"
            loser_elo_change_formatted = f"+{loser_elo_change}" if loser_elo_change >= 0 else f"{loser_elo_change}"
            submitting_discordid = winner_discordid if interaction.user.id == self.winner_id else loser_discordid

            await log_duel(conn, submitting_discordid, winner_discordid, self.winner_score, new_winner_elo_exact, loser_discordid, self.loser_score, new_loser_elo_exact)

            await conn.execute("UPDATE ranked_players SET kills = kills + $1, deaths = deaths + $2, elo_duelsx = $3, matches = matches + 1 WHERE discordid = $4", self.winner_score, self.loser_score, new_winner_elo_exact, self.winner_id)
            await conn.execute("UPDATE ranked_players SET kills = kills + $1, deaths = deaths + $2, elo_duelsx = $3, matches = matches + 1 WHERE discordid = $4", self.loser_score, self.winner_score, new_loser_elo_exact, self.loser_id)

            coin_reward = 3
            await conn.execute("UPDATE ranked_players SET coins = coins + $1 WHERE discordid = ANY($2::bigint[])", coin_reward, [winner_discordid, loser_discordid])

            house_account_result = await conn.fetchrow("SELECT balance, payout_rate FROM house_account ORDER BY id DESC LIMIT 1")
            house_balance, payout_rate_percentage = house_account_result if house_account_result else (0, 0)
            payout_rate_percentage /= 100

            payout_amount = 0
            new_house_balance = house_balance
            if house_balance > 0 and payout_rate_percentage > 0:
                payout_amount = round(house_balance * payout_rate_percentage)
                if house_balance >= payout_amount * 2:
                    new_house_balance = house_balance - (payout_amount * 2)
                    await conn.execute("UPDATE ranked_players SET coins = coins + $1 WHERE discordid = ANY($2::bigint[])", payout_amount, [self.winner_id, self.loser_id])
                    await conn.execute("UPDATE house_account SET balance = $1", new_house_balance)

            updated_winner_data = await conn.fetchrow("SELECT elo_duelsx, coins FROM ranked_players WHERE discordid = $1", self.winner_id)
            updated_loser_data = await conn.fetchrow("SELECT elo_duelsx, coins FROM ranked_players WHERE discordid = $1", self.loser_id)

            updated_winner_elo, updated_winner_purse = updated_winner_data['elo_duelsx'], updated_winner_data['coins']
            updated_loser_elo, updated_loser_purse = updated_loser_data['elo_duelsx'], updated_loser_data['coins']
            tier_assignments = await calculate_tiers(conn)
            winner_tier_emoji = tier_assignments.get(winner_discordid, ':regional_indicator_d:')
            loser_tier_emoji = tier_assignments.get(loser_discordid, ':regional_indicator_d:')

            updated_embed = discord.Embed(
                title=f"1v1 Duel Winner: {interaction.guild.get_member(self.winner_id).display_name} vs {interaction.guild.get_member(self.loser_id).display_name} ({self.winner_score}-{self.loser_score})",
                color=discord.Color.green()
            )
            updated_embed.add_field(name=f"{interaction.guild.get_member(self.winner_id).display_name}: {round(updated_winner_elo)} ({winner_elo_change_formatted})", value=f"{winner_tier_emoji}   :coin: {updated_winner_purse}", inline=True)
            updated_embed.add_field(name=f"{interaction.guild.get_member(self.loser_id).display_name}: {round(updated_loser_elo)} ({loser_elo_change_formatted})", value=f"{loser_tier_emoji}   :coin: {updated_loser_purse}", inline=True)
            updated_embed.set_footer(text=f"Match result confirmed by {interaction.user.display_name}")
            updated_embed.timestamp = datetime.now()

            total_reward = coin_reward + payout_amount

            description_lines = [
                f"`/submit_duel {self.winner_score} @{interaction.guild.get_member(self.non_submitter_id).display_name} {self.loser_score}`",
                f"Payout: **{total_reward}** [ {coin_reward} + ({payout_amount} house tip) ]",
                f"Purse: 0"  # Placeholder, replace with actual purse logic if necessary
            ]
            updated_embed.description = "\n".join(description_lines)

            #updated_embed.url = "https://chivstats.xyz/leaderboards/ranked_combat/"

            await self.duel_message.edit(embed=updated_embed)

            # Call echo_to_guilds function to send the message to other guilds
            audit_message = await echo_to_guilds(interaction, updated_embed, 'chivstats-ranked')

            # Send audit message to the audit channel
            if audit_channel:
                await audit_channel.send(audit_message)

            winner_rank = await get_player_rank(conn, updated_winner_elo)
            loser_rank = await get_player_rank(conn, updated_loser_elo)

            # Modify the confirmation message to include ranks instead of tier emojis
            confirmation_message = (
                f"**Duel**: [{self.winner_score}-{self.loser_score}] **{interaction.guild.get_member(self.winner_id).display_name}** _({round(updated_winner_elo)})_ "
                f"vs. **{interaction.guild.get_member(self.loser_id).display_name}** _({round(updated_loser_elo)})_ [elo:{winner_elo_change}, coin:{total_reward}]."
            )
            for guild in bot.guilds:
                ranked_audit_channel = discord.utils.get(guild.text_channels, name='ranked-audit')
                if ranked_audit_channel:
                    await ranked_audit_channel.send(confirmation_message)

            if self.verification_message:
                await self.verification_message.delete()

            await self.clear_buttons()
            await self.duel_message.edit(view=self)
            await update_leaderboard_message()

            if interaction.response.is_done():
                await interaction.followup.send("Duel confirmed.", ephemeral=True)
        else:
            await interaction.response.send_message("One or both players are not registered in the ranking system.", ephemeral=True)
        await conn.close()
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(error_message)
        traceback.print_exc()
        if audit_channel:
            await audit_channel.send(embed=discord.Embed(
                title="Duel Confirmation Error",
                description=error_message,
                color=discord.Color.red()
            ))
        await interaction.followup.send("An error occurred while processing the duel.", ephemeral=True)




##############
# END DUELS



@bot.slash_command(guild_ids=GUILD_IDS, description="Challenge another player to a duel with a bet.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def challenge(interaction: discord.Interaction, target_player: discord.Member, bet_amount: int):
    await interaction.response.defer()

    conn = await create_db_connection()
    try:
        # Calculate the total amount to be deducted (bet + 10%)
        total_deduction = bet_amount + int(bet_amount * 0.1)

        # Fetch the challenger's coin balance
        challenger_coins = await conn.fetchval("SELECT coins FROM ranked_players WHERE discordid = $1", interaction.user.id)
        
        # Check if the challenger can afford the bet
        if challenger_coins < total_deduction:
            await interaction.followup.send("You do not have enough coins to make this challenge.", ephemeral=True)
            return

        # Subtract the bet from the challenger's account and add the 10% to the house account
        await conn.execute("UPDATE ranked_players SET coins = coins - $1 WHERE discordid = $2", total_deduction, interaction.user.id)
        await update_house_account_balance(conn, int(bet_amount * 0.1))  # Update house account

        # Record the challenge in the challenges table
        await conn.execute("""
            INSERT INTO challenges (challenger_id, challenged_id, bet_amount, purse, status)
            VALUES ($1, $2, $3, $4, 'pending acceptance')
            """, interaction.user.id, target_player.id, bet_amount, bet_amount * 2)

        # Create an embed with challenge details and buttons for accepting/denying
        embed = discord.Embed(
            title="Duel Challenge",
            description=f"{interaction.user.display_name} has challenged {target_player.display_name} to a duel with a bet of {bet_amount} coins. Total purse: {bet_amount * 2} coins.",
            color=discord.Color.blue()
        )
        view = ChallengeView(interaction, target_player.id, bet_amount, interaction.user.display_name, target_player.display_name)
        await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        await interaction.followup.send(f"An error occurred while creating the challenge: {e}", ephemeral=True)
    finally:
        await close_db_connection(conn)

class ChallengeView(discord.ui.View):
    def __init__(self, interaction, challenged_id, bet_amount, challenger_name, challenged_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interaction = interaction
        self.challenged_id = challenged_id
        self.bet_amount = bet_amount
        self.challenger_name = challenger_name
        self.challenged_name = challenged_name

    async def update_challenge_embed(self, interaction, status_message):
        embed = discord.Embed(
            title="Duel Challenge",
            description=f"{self.challenger_name} has challenged {self.challenged_name} to a duel with a bet of {self.bet_amount} coins. Total purse: {self.bet_amount * 2} coins.\n\nStatus: {status_message}",
            color=discord.Color.blue()
        )
        self.clear_items()  # Remove all buttons
        await interaction.message.edit(embed=embed, view=self)  # Update the message with the new embed and view


    async def accept_challenge(self):
        conn = await create_db_connection()
        try:
            # Fetch the challenged player's coin balance
            challenged_coins = await conn.fetchval("SELECT coins FROM ranked_players WHERE discordid = $1", self.challenged_id)
            
            # Check if the challenged player can afford the bet
            if challenged_coins < self.bet_amount:
                return False, "You do not have enough coins to accept this challenge."

            # Subtract the bet from the challenged player's account
            await conn.execute("UPDATE ranked_players SET coins = coins - $1 WHERE discordid = $2", self.bet_amount, self.challenged_id)

            # Update the challenge status to 'accepted'
            await conn.execute("""
                UPDATE challenges
                SET status = 'accepted'
                WHERE challenger_id = $1 AND challenged_id = $2 AND status = 'pending acceptance'
                """, self.interaction.user.id, self.challenged_id)

            return True, "Challenge accepted."
        finally:
            await close_db_connection(conn)

    async def deny_challenge(self):
        conn = await create_db_connection()
        try:
            # Refund the bet and 10% fee to the challenger
            total_refund = self.bet_amount + int(self.bet_amount * 0.1)
            await conn.execute("UPDATE ranked_players SET coins = coins + $1 WHERE discordid = $2", total_refund, self.interaction.user.id)

            # Update the challenge status to 'denied'
            await conn.execute("""
                UPDATE challenges
                SET status = 'denied'
                WHERE challenger_id = $1 AND challenged_id = $2 AND status = 'pending acceptance'
                """, self.interaction.user.id, self.challenged_id)

            return "Challenge denied."
        finally:
            await close_db_connection(conn)

    @discord.ui.button(label="Accept Challenge", style=discord.ButtonStyle.green)
    async def accept_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Ensure the responding user is the challenged player
        if interaction.user.id != self.challenged_id:
            await interaction.response.send_message("You are not the player challenged in this duel.", ephemeral=True)
            return
        if interaction.user.id == self.challenged_id:
            success, message = await self.accept_challenge()
            await self.update_challenge_embed(interaction, f"Accepted by {interaction.user.display_name}. {message}")
        success, message = await self.accept_challenge()
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Deny Challenge", style=discord.ButtonStyle.red)
    async def deny_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Ensure the responding user is the challenged player
        if interaction.user.id != self.challenged_id:
            await interaction.response.send_message("You are not the player challenged in this duel.", ephemeral=True)
            return
        if interaction.user.id == self.challenged_id:
            message = await self.deny_challenge()
            await self.update_challenge_embed(interaction, f"{interaction.user.display_name} denied the challenge. {message}")
        message = await self.deny_challenge()
        await interaction.response.send_message(message, ephemeral=True)




@bot.slash_command(guild_ids=GUILD_IDS, description="Explains how the ELO system works.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def elo(interaction: discord.Interaction, public: bool = False):
    # Create the embed with a detailed explanation of the ELO system
    embed = discord.Embed(
        title="Understanding the Ranked Combat ELO System",
        description=(
            "**Ranked Combat Chivstats ELO System Overview**\n"
            "The ELO rating system is a method for calculating the relative skill levels of players in competitive chiv 2 matches. It's a dynamic system that adjusts after each game based on the match's victor outcome. This is under continual refinement, please help.\n\n"

            "**How ELO is Calculated**\n"
            "1. **Win Expectancy:** Before a match, the system calculates the expected outcome based on the difference in ELO between the players.\n"
            "2. **ELO Adjustment:** After the match, your ELO is adjusted. A win against a stronger opponent yields a higher ELO increase than a win against a weaker opponent.\n"
            "3. **K-Factor:** The weight applied to the outcome of a match. A higher K-factor can result in larger swings in your ELO score.\n\n"

            "**Detailed ELO Calculation**\n"
            "`ELO_new = ELO_current + K * (S_actual - S_expected)`\n"
            "Where:\n"
            "- ELO_current: Current ELO rating of the player\n"
            "- K: K-factor, which adjusts the volatility of the ELO (set to 32 in our system)\n"
            "- S_actual: Actual match outcome (1 for a win, 0 for a loss)\n"
            "- S_expected: Expected match outcome, calculated using the formula below\n"
            "- c: A constant that determines the influence of the ELO difference (set to 400 in our system)\n\n"
            "`S_expected = 1 / (1 + 10^((ELO_opponent - ELO_current) / c))`\n\n"

            "**Establishing ELO**\n"
            "New players start with a default ELO, which is fine-tuned as they play more games.\n\n"

            "**Ranked Combat Success in ELO**\n"
            "In ranked combat, the focus is on match outcomes over individual performance metrics...\n\n"

            "**Impact of Kills and Deaths**\n"
            "Kills and deaths are significant for personal stats and other rankings but do not directly affect the ELO score.\n\n"

            "**TL;DR - The ELO System in Brief**\n"
            "Your ELO score changes after every match, depending on whether you win or lose, and by how much you were expected to win or lose. It's a way to measure your skill level compared to other players, and it keeps changing as you play more games. Type `/register` to get started.\n\n"

            "*Ranked Combat: To the victor go the spoils. Chivstats Coming Soon.*" #[chivstats.xyz/leaderboards/ranked_combat](https://chivstats.xyz/leaderboards/ranked_combat/)
        ),
        color=discord.Color.blue()
    )

    # Decide whether to send the embed as a public or ephemeral message
    if public:
        await interaction.response.send_message(embed=embed, ephemeral=False)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)


###################
#DUOS LOGIC
###################
# Helper function to calculate new ELO ratings for a duo match
async def calculate_duo_elo(team1_elo, team2_elo, team1_score, team2_score):
    # K factor for ELO calculation - may vary based on your requirements
    K = 32
    team1_new_elo = calculate_elo(team1_elo, K, team1_score > team2_score, 1, team2_elo)
    team2_new_elo = calculate_elo(team2_elo, K, team2_score > team1_score, 1, team1_elo)
    return team1_new_elo, team2_new_elo

# Helper function to check if a duo team exists and create one if not
async def check_or_create_duo_team(conn, discordid1, discordid2):
    try:
        # Check if the team already exists
        team = await conn.fetchrow("""
            SELECT id FROM duo_teams
            WHERE (player1_id = $1 AND player2_id = $2) OR (player1_id = $2 AND player2_id = $1)
            """, discordid1, discordid2)

        if not team:
            # Retrieve the display names of both players
            player1_name = await get_display_name_from_ranked_players(discordid1)
            player2_name = await get_display_name_from_ranked_players(discordid2)

            # Generate team name
            part1 = player1_name[:4] if player1_name else "Unk"
            part2 = player2_name[:4] if player2_name else "Unk"
            team_name = f"{part1}{part2}"
            # Create the new team with the generated team name and initial ELO rating
            initial_elo = 1500  # Example initial ELO rating
            team_id = await conn.fetchval("""
                INSERT INTO duo_teams (player1_id, player2_id, team_name, elo_rating)
                VALUES ($1, $2, $3, $4) RETURNING id
                """, discordid1, discordid2, team_name, initial_elo)
            return team_id
        else:
            return team['id']

    except Exception as e:
        print(f"Error in check_or_create_duo_team: {e}")
        raise e  # Re-raise the exception so that it can be handled by the calling function



class ConfirmationViewDuo(discord.ui.View):
    def __init__(self, submitter, opponents, team1_score, team2_score, team1_id, team2_id, team1_elo, team2_elo, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.submitter = submitter
        self.opponents = opponents
        self.team1_score = team1_score
        self.team2_score = team2_score
        self.team1_id = team1_id
        self.team2_id = team2_id
        self.team1_elo = team1_elo
        self.team2_elo = team2_elo
        self.conn = None

        self.confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.green)
        self.confirm_button.callback = self.confirm_button_clicked

        self.deny_button = discord.ui.Button(label="Deny", style=discord.ButtonStyle.red)
        self.deny_button.callback = self.deny_button_clicked

        self.add_item(self.confirm_button)
        self.add_item(self.deny_button)

    async def initialize_connection(self):
        self.conn = await create_db_connection()

    async def confirm_button_clicked(self, interaction: discord.Interaction):
        # Check if the interaction user is one of the opponents
        if interaction.user.id not in [self.opponents[0].id, self.opponents[1].id]:
            await interaction.response.send_message("You are not authorized to confirm this match.", ephemeral=True)
            return

        # Calculate new ELO ratings
        team1_new_elo, team2_new_elo = await calculate_duo_elo(self.team1_elo, self.team2_elo, self.team1_score, self.team2_score)

        # Update the duo_teams table with new ELO ratings, increment match counter
        await self.conn.execute("UPDATE duo_teams SET elo_rating = $1 WHERE id = $2", team1_new_elo, self.team1_id)
        await self.conn.execute("UPDATE duo_teams SET elo_rating = $1 WHERE id = $2", team2_new_elo, self.team2_id)
        await self.conn.execute("UPDATE duo_teams SET matches_played = matches_played + 1 WHERE id = ANY($1::bigint[])", [self.team1_id, self.team2_id])

        # Fetch team names
        team1_name = await self.conn.fetchval("SELECT team_name FROM duo_teams WHERE id = $1", self.team1_id)
        team2_name = await self.conn.fetchval("SELECT team_name FROM duo_teams WHERE id = $1", self.team2_id)

        # Calculate ELO changes
        team1_elo_change = int(team1_new_elo - self.team1_elo)
        team2_elo_change = int(team2_new_elo - self.team2_elo)

        # Round ELO ratings to whole numbers
        team1_new_elo_rounded = round(team1_new_elo)
        team2_new_elo_rounded = round(team2_new_elo)
        team1_elo_change_rounded = round(team1_new_elo - self.team1_elo)
        team2_elo_change_rounded = round(team2_new_elo - self.team2_elo)

        submitter_discordid = interaction.user.id
        # Insert the match data into the "duos" table
        await self.conn.execute("INSERT INTO duos (submitting_discordid, winner_team_id, winner_score, winner_elo, loser_team_id, loser_score, loser_elo) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            submitter_discordid, self.team1_id, self.team1_score, team1_new_elo, self.team2_id, self.team2_score, team2_new_elo)

        # Update the embed to show the match confirmation
        embed = interaction.message.embeds[0]
        embed.title = "2v2 Duos Match Result Confirmed"
        embed.clear_fields()  # Clear previous fields if any
        embed.add_field(name=f"Team {team1_name}", value=f"New ELO: {team1_new_elo_rounded} (Change: {team1_elo_change_rounded:+d})", inline=True)
        embed.add_field(name=f"Team {team2_name}", value=f"New ELO: {team2_new_elo_rounded} (Change: {team2_elo_change_rounded:+d})", inline=True)
        embed.color = discord.Color.green()
        embed.set_footer(text=f"Match result confirmed by {interaction.user.display_name}.")
        await interaction.message.edit(embed=embed, view=None)
        # Call echo_to_guilds to echo the embed to other guilds
        origin_channel_name = interaction.channel.name
        await echo_to_guilds(interaction, embed, origin_channel_name)

    async def deny_button_clicked(self, interaction: discord.Interaction):
        # Check if the interaction user is one of the opponents or the submitter
        if interaction.user.id not in [self.opponents[0].id, self.opponents[1].id, self.submitter.id]:
            await interaction.response.send_message("You are not authorized to deny this match.", ephemeral=True)
            return

        # Update the embed to show the match denial
        embed = interaction.message.embeds[0]
        embed.title = "2v2 Duos Match Result Denied"
        embed.color = discord.Color.red()
        embed.set_footer(text=f"Match result denied by {interaction.user.display_name}.")
        await interaction.message.edit(embed=embed, view=None)

        # Optionally, you can add logic here if there's anything specific you want to do when a match is denied
        # For example, logging the event, notifying specific channels, etc.

        # Send a response back to the user who clicked the button
        await interaction.response.send_message("The match submission has been denied.", ephemeral=True)


@bot.slash_command(guild_ids=GUILD_IDS, description="Submit the result of a 2v2 duel between two teams.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def submit_duo(interaction: discord.Interaction, team_member: discord.Member, team_score: int, enemy1: discord.Member, enemy2: discord.Member, enemy_score: int):
    await interaction.response.defer()

    conn = await create_db_connection()
    try:
        # Fetch PlayFab IDs for all members of both teams
        print("Fetching PlayFab IDs")
        team1_playfabid1 = await get_playfabid_of_discord_id(conn, interaction.user.id)
        team1_playfabid2 = await get_playfabid_of_discord_id(conn, team_member.id)
        team2_playfabid1 = await get_playfabid_of_discord_id(conn, enemy1.id)
        team2_playfabid2 = await get_playfabid_of_discord_id(conn, enemy2.id)
        command_text = f"/submit_duo @{interaction.user.display_name} & @{team_member.display_name} {team_score} vs @{enemy1.display_name} & @{enemy2.display_name} {enemy_score}"

        # Check for duplicate players
        print("Checking for duplicate players")
        players = [interaction.user, team_member, enemy1, enemy2]
        if len(players) != len(set(player.id for player in players)):
            await interaction.response.send_message("Duplicate players detected! Please ensure all players are unique.", ephemeral=True)
            return

        # Verify none of the players are retired
        print("Verifying retired players")
        player_ids = [interaction.user.id, team_member.id, enemy1.id, enemy2.id]
        results = await conn.fetch("SELECT discordid, retired FROM ranked_players WHERE discordid = ANY($1)", player_ids)
        retired_players = [discord_id for discord_id, retired in results if retired]
        if retired_players:
            message = "The following players are retired: "
            message += ', '.join(f"<@{discord_id}>" for discord_id in retired_players)
            message += "\nPlease reactivate your account using /reactivate."
            await interaction.response.send_message(message, ephemeral=True)
            return
        print("ephemeral message to submitter")
        # Send an ephemeral response to the submitter to indicate the submission was accepted
        await interaction.followup.send("Submission accepted. Please wait for confirmation from the opposing team.", ephemeral=True)
        print("Preparing embed message")
        # Check for existing teams or create new ones
        team1_id = await check_or_create_duo_team(conn, team1_playfabid1, team1_playfabid2)
        team2_id = await check_or_create_duo_team(conn, team2_playfabid1, team2_playfabid2)
        # Fetch current ELO ratings
        team1_elo = await conn.fetchval("SELECT elo_rating FROM duo_teams WHERE id = $1", team1_id)
        team2_elo = await conn.fetchval("SELECT elo_rating FROM duo_teams WHERE id = $1", team2_id)

        embed = discord.Embed(
            title="2v2 Duos Match Submitted (UNVERIFIED)",
            description=f"`{command_text}`\n\n"
                        f"Team 1: <@{interaction.user.id}> and <@{team_member.id}> - Score: {team_score}\n"
                        f"Team 2: <@{enemy1.id}> and <@{enemy2.id}> - Score: {enemy_score}",
            color=discord.Color.orange()
        )
        # After sending the initial response message with the view attached
        print("Creating ConfirmationViewDuo instance")
        # Create the view and associate it with the embed
        view = ConfirmationViewDuo(
            interaction.user, [enemy1, enemy2], team_score, enemy_score,
            team1_id, team2_id, team1_elo, team2_elo
        )
        print("Sending follow-up message with embed and view")
        await view.initialize_connection()
        
        # Send the follow-up message with the embed and view
        await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        print(f"Error in submit_duo: {e}")
        await interaction.followup.send("An error occurred while processing the duo match submission.", ephemeral=True)
    finally:
        await close_db_connection(conn)

@bot.slash_command(guild_ids=GUILD_IDS, description="Create and or update your duos team name.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def duo_setup_team(interaction: discord.Interaction, team_member: discord.Member, team_name: str, debug: bool = False):
    conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

    # Fetch PlayFab IDs for both members of the team
    playfabid1 = await get_playfabid_of_discord_id(conn, interaction.user.id)  # Assuming this is not an async function
    playfabid2 = await get_playfabid_of_discord_id(conn, team_member.id)      # Assuming this is not an async function

    try:
        # Check for an existing team or create a new one
        team_id = await check_or_create_duo_team(conn, playfabid1, playfabid2)  # Assuming this is not an async function

        # Update the team name
        await conn.execute("UPDATE duo_teams SET team_name = $1 WHERE id = $2", team_name, team_id)

        # Announce the update
        announcement_message = f"{interaction.user.display_name} (with {team_member.display_name}) set the duo's name to {team_name}"

        # Iterate through guild_ids
        for guild_id in GUILD_IDS:
            guild = bot.get_guild(guild_id)
            if guild:
                local_channel = discord.utils.get(guild.text_channels, name="chivstats-ranked")  # Replace with your local channel name
                if local_channel:
                    await local_channel.send(announcement_message)
        await interaction.response.send_message(f"Team name set to '{team_name}'.", ephemeral=True)

    except Exception as e:
        print(f"Error in duo_setup_team: {e}")
        await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)

    finally:
        await conn.close()




@bot.slash_command(guild_ids=GUILD_IDS, description="List top 25 duo teams that have participated in matches, ranked by ELO.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def duo_teams(interaction: discord.Interaction):
    conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

    try:
        # Query top 25 active duo teams with match participation, ordered by ELO in descending order
        teams = await conn.fetch("""
            SELECT dt.team_name, dt.player1_id, dt.player2_id, dt.elo_rating, COUNT(d.team_id) AS match_count
            FROM duo_teams dt
            LEFT JOIN (
                SELECT winner_team_id AS team_id FROM duos
                UNION ALL
                SELECT loser_team_id AS team_id FROM duos
            ) AS d ON dt.id = d.team_id
            WHERE dt.retired = false
            GROUP BY dt.id
            HAVING COUNT(d.team_id) > 0
            ORDER BY dt.elo_rating DESC
            LIMIT 25;
        """)

        if not teams:
            await interaction.response.send_message("There are currently no active duo teams with match participation.", ephemeral=True)
            return

        # Create an embed to list the duo teams
        embed = discord.Embed(
            title="Top 25 Active Duo Teams with Match Participation",
            description="Here are the top 25 active duo teams that have participated in matches, sorted by their ELO in descending order:",
            color=discord.Color.blue()
        )
        
        # Loop through the teams and add each to the embed
        for team in teams:
            team_name, player1_id, player2_id, elo_rating, match_count = team
            player1_name = await get_common_name_from_ranked_players(conn, player1_id)
            player2_name = await get_common_name_from_ranked_players(conn, player2_id)
            embed.add_field(
                name=f"{team_name} - {elo_rating}  (Matches Played: {match_count})",
                value=f"Players: {player1_name} and {player2_name}",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        print(f"Error in duo_teams: {e}")
        await interaction.response.send_message("An error occurred while retrieving the duo teams.", ephemeral=True)
    finally:
        await conn.close()


##########END OF DUOS#############
##################################

@bot.slash_command(guild_ids=GUILD_IDS, description="Displays the rank and stats of a player based on Alias or @Discord input.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def rank(interaction: discord.Interaction, discord_member: discord.Member = None, player_name: str = None):
    # Prioritize discord_member if provided
    discord_id = discord_member.id if discord_member else None

    try:
        # Establish an asynchronous connection to the database
        conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

        if discord_id:
            # Fetch player's data based on discord_id
            result = await conn.fetchrow("""
                SELECT elo_duelsx, kills, deaths, matches, playfabid, discord_username, common_name, coins
                FROM ranked_players
                WHERE discordid = $1
            """, discord_id)
        elif player_name:
            # Fetch player's data based on player_name
            result = await conn.fetchrow("""
                SELECT elo_duelsx, kills, deaths, matches, playfabid, discord_username, common_name, coins
                FROM ranked_players
                WHERE lower(common_name) = lower($1)
            """, player_name)
            # If no match found by player_name, try matching by discord_username
            if not result:
                result = await conn.fetchrow("""
                    SELECT elo_duelsx, kills, deaths, matches, playfabid, discord_username, common_name, coins
                    FROM ranked_players
                    WHERE lower(discord_username) = lower($1)
                """, player_name)

        if result:
            elo_duelsx, kills, deaths, matches, playfabid, discord_username, common_name, coins = result
            elo_duelsx_rounded = round(elo_duelsx)  # Round ELO to a whole number
            kdr = kills / deaths if deaths > 0 else kills  # Avoid division by zero

            # Calculate player's ranks
            wealth_rank_result = await conn.fetchval("""
                SELECT COUNT(*) + 1
                FROM ranked_players
                WHERE coins > $1
            """, coins)
            wealth_rank = f"**#{wealth_rank_result}**" if wealth_rank_result else '**N/A**'

            elo_rank_result = await conn.fetchval("""
                SELECT COUNT(*) + 1
                FROM ranked_players
                WHERE elo_duelsx > $1
            """, elo_duelsx)
            elo_rank = f"**#{elo_rank_result}**" if elo_rank_result else '**N/A**'

            kdr_rank_result = await conn.fetchval("""
                SELECT COUNT(*) + 1
                FROM ranked_players
                WHERE (CAST(kills AS FLOAT) / NULLIF(deaths, 0)) > $1
            """, kdr)
            kdr_rank = f"**#{kdr_rank_result}**" if kdr_rank_result else '**N/A**'

            matches_rank_result = await conn.fetchval("""
                SELECT COUNT(*) + 1
                FROM ranked_players
                WHERE matches > $1
            """, matches)
            matches_rank = f"**#{matches_rank_result}**" if matches_rank_result else '**N/A**'

            # Embed construction
            embed = discord.Embed(
                title=f"{common_name} Ranked Statistics",
                description=(
                    f"{common_name}'s Stats:\n"
                    f"[Duels ELO Rating:] {round(elo_duelsx)} ({elo_rank})\n"
                    f"KDR: {kills}:{deaths} ({kdr_rank})\n"
                    f"Matches: {matches} ({matches_rank})\n"
                    f"Purse: {coins} coins ({wealth_rank})\n\n"
                ),
                color=discord.Color.blue(),
            )
            # Include Discord username if the match was found using discord_username column
            if player_name and player_name.lower() == discord_username.lower():
                embed.add_field(name="Discord Name", value=discord_username, inline=False)

            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("Player not found in the ranking system.", ephemeral=True)
    except Exception as e:
        print(f"Database error: {e}")
        await interaction.response.send_message("An error occurred while fetching the player rank.", ephemeral=True)
    finally:
        # Close the connection
        if conn:
            await conn.close()

    if not discord_id and not player_name:
        await interaction.response.send_message("Please provide a username or mention a member.", ephemeral=True)
        return






      
      
@bot.slash_command(guild_ids=GUILD_IDS, description="1v1 Toggle your active status for the duels ranked combat.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def ready_duel(interaction: discord.Interaction):
    role_name = "1v1 pings"
    active_duelists = set()  # Set to store unique user IDs
    sent_channels = set()  # Set to keep track of channels where the message has been sent

    # Update the user's role in the guild where the command was used
    role = discord.utils.get(interaction.guild.roles, name=role_name)
    if role:
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            embed_color = discord.Color.red()
            action_message = "You are no longer active for 1v1 duels. Waiting 2 seconds for changes to cascade through discords.."
        else:
            await interaction.user.add_roles(role)
            embed_color = discord.Color.green()
            action_message = "You are now active for 1v1 duels. Waiting 2 seconds for changes to cascade through discords.."

        # Respond to the user's action with an ephemeral message
        await interaction.response.send_message(action_message, ephemeral=True)

    # Wait for the role changes to propagate
    await asyncio.sleep(2)

    # Clear the set to ensure it's empty before recounting
    active_duelists.clear()

    # Count active duelists across all guilds
    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            active_duelists.update(member.id for member in role.members if not member.bot)

    # Prepare the public embed message
    embed = discord.Embed(
        title="1v1 Ranked Pool Status Change",
        description=f"{interaction.user.display_name} is now {'active' if embed_color == discord.Color.green() else 'inactive'} for 1v1 duels.",
        color=embed_color
    )
    embed.add_field(name="Active Duelists", value=str(len(active_duelists)))
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"Ping `@1v1 pings` to ping these users and arrange a duel.")

    # Echo the embed message to all guilds in #chivstats-ranked channel
    for guild in bot.guilds:
        chivstats_channel = discord.utils.get(guild.text_channels, name="chivstats-ranked")
        if chivstats_channel:
            await chivstats_channel.send(embed=embed)

@bot.slash_command(guild_ids=GUILD_IDS, description="Get the status of active duelists and teams across all guilds.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def ready_status(interaction: discord.Interaction):
    role_name_1v1 = "1v1 pings"
    role_name_2v2 = "2v2 pings"
    active_duelists_1v1 = set()  # Set to store unique user IDs for 1v1
    active_duelists_2v2 = set()  # Set to store unique user IDs for 2v2

    # Count active duelists for 1v1 across all guilds
    for guild in bot.guilds:
        role_1v1 = discord.utils.get(guild.roles, name=role_name_1v1)
        if role_1v1:
            active_duelists_1v1.update(member.id for member in role_1v1.members if not member.bot)

    # Count active duelists for 2v2 across all guilds
    for guild in bot.guilds:
        role_2v2 = discord.utils.get(guild.roles, name=role_name_2v2)
        if role_2v2:
            active_duelists_2v2.update(member.id for member in role_2v2.members if not member.bot)

    # Prepare the embed message
    embed = discord.Embed(
        title="Active Duelists Status",
        description=(
            f"Total active duelists for 1v1 across all guilds: {len(active_duelists_1v1)} (`@1v1 pings`)\n"
            f"Total active duelists for 2v2 across all guilds: {len(active_duelists_2v2)} (`@2v2 pings`)"
        ),
        color=discord.Color.blue()
    )

    # Send the embed message
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(guild_ids=GUILD_IDS, description="2v2 Toggle yourself and an optional teammate for duo ranked combat.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def ready_duo(interaction: discord.Interaction, teammate: discord.Member = None):
    role_name = "2v2 pings"
    active_duo_teams = set()  # Set to store unique user IDs for duo teams

    try:
        # Update the user's and optional teammate's role in the guild where the command was used
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                message = "You are no longer active for 2v2 duels."
                embed_color = discord.Color.red()
            else:
                await interaction.user.add_roles(role)
                message = "You are now active for 2v2 duels."
                embed_color = discord.Color.green()

            if teammate:
                if role in teammate.roles:
                    await teammate.remove_roles(role)
                    message += f" {teammate.display_name} is also no longer active for 2v2 duels."
                else:
                    await teammate.add_roles(role)
                    message += f" {teammate.display_name} is now active for 2v2 duels."

            # Respond to the user's action with an ephemeral message
            await interaction.response.send_message(message, ephemeral=True)

            # Wait for the role changes to propagate
            await asyncio.sleep(1)

        # Count active duo teams across all guilds after waiting
        for guild in bot.guilds:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                active_duo_teams.update((member.id, member.display_name) for member in role.members if not member.bot)

        # Prepare the public embed message
        active_duo_teams_count = len(active_duo_teams)
        embed = discord.Embed(
            title="2v2 Ranked Pool Status Change",
            description=message,
            color=embed_color
        )
        embed.add_field(name="Active Duo Teams", value=str(active_duo_teams_count))
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Ping `@2v2 pings` to ping these users and arrange a duo.")

        # Echo the embed message to all guilds in #chivstats-ranked channel
        for guild in bot.guilds:
            chivstats_channel = discord.utils.get(guild.text_channels, name="chivstats-ranked")
            if chivstats_channel:
                await chivstats_channel.send(embed=embed)

    except Exception as e:
        print(f"An error occurred: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while processing your request. Please try again.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while processing your request. Please try again.", ephemeral=True)



@bot.slash_command(guild_ids=GUILD_IDS, description="Exit the ready pool for matches.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def ready_exit(interaction: discord.Interaction):
    roles_to_remove = ["1v1 pings", "2v2 pings"]
    roles = [discord.utils.get(interaction.guild.roles, name=role_name) for role_name in roles_to_remove]
    roles = [role for role in roles if role is not None]  # Filter out None values
    if roles:
        await interaction.user.remove_roles(*roles)
        await interaction.response.send_message("You have been removed from the ready pool and the roles have been revoked.", ephemeral=True)
    else:
        await interaction.response.send_message("No relevant roles to remove.", ephemeral=True)

#### END READY FUNCTIONS ###

async def update_house_account_balance(conn, amount):
    try:
        # Fetch the latest house balance or initialize if no entry exists
        house_balance = await conn.fetchval("SELECT balance FROM house_account ORDER BY last_updated DESC LIMIT 1")

        if house_balance is not None:
            house_balance += amount
        else:
            # Initialize house account with a zero balance if it's the first transaction
            house_balance = amount
            await conn.execute("INSERT INTO house_account (balance, last_updated, payout_rate) VALUES ($1, CURRENT_TIMESTAMP, 5.00)", house_balance)

        # Update house account with new balance
        await conn.execute("UPDATE house_account SET balance = $1", house_balance)
    except Exception as e:
        print(f"An error occurred while updating house account balance: {e}")



@bot.slash_command(guild_ids=GUILD_IDS, description="Displays the house account value and the current payout rate.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def house(interaction: discord.Interaction):
    try:
        # Establish an asynchronous connection to the database
        conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

        # Fetch the latest house account entry
        house_account_entry = await conn.fetchrow("SELECT balance, payout_rate FROM house_account ORDER BY last_updated DESC LIMIT 1")

        if house_account_entry:
            balance, payout_rate = house_account_entry
            embed = discord.Embed(
                title=":bank: House Account",
                description=f"**Account Balance:** {balance} coins (:coin:)\n**Payout Rate:** {payout_rate}%",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed)

            # Rebuild the entered slash command for auditing
            command_name = interaction.command.name
            entered_command = f"/{command_name}"

            # Send an audit message to a specific guild and channel
            target_guild_id = 1227017798916505780  # ID of the 'Chivalry Unchained' guild
            audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel

            # Get the target guild and channel
            target_guild = bot.get_guild(target_guild_id)
            audit_channel = target_guild.get_channel(audit_channel_id) if target_guild else None

            if audit_channel:
                audit_message = f"{interaction.user.display_name} (ID: {interaction.user.id}) has executed: {entered_command}"
                await audit_channel.send(audit_message)
        else:
            await interaction.response.send_message("The house bank information is currently unavailable.", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message("An error occurred while retrieving the bank information.", ephemeral=True)
        print(f"Database error: {e}")

    finally:
        # Close the connection
        if conn:
            await conn.close()


@bot.slash_command(guild_ids=GUILD_IDS, description="Displays stats for a Discord ID or Alias.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def stats(interaction: discord.Interaction, discord_name: discord.Member = None, player_name: str = None):
    try:
        # Connect to the PostgreSQL database
        conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

        if discord_name:
            # Get the Discord ID of the selected member
            discord_id = discord_name.id
            # Fetch user's stats by Discord ID
            stats = await get_player_stats(conn, discord_id)
            if stats:
                # Send the formatted stats as a message
                await send_stats_message(interaction, stats, input_type="Discord ID")
            else:
                await interaction.response.send_message("No stats found for the provided Discord ID.", ephemeral=True)

        elif player_name:
            # Fetch user's stats by player name
            stats = await get_player_stats_by_name(conn, player_name)
            if stats:
                # Send the formatted stats as a message
                await send_stats_message(interaction, stats, input_type="Player Name")
            else:
                await interaction.response.send_message("No stats found for the provided player name.", ephemeral=True)

        else:
            await interaction.response.send_message("Please provide either a Discord ID or player name.", ephemeral=True)

    except Exception as e:
        print(f"Database error: {e}")
        await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)

    finally:
        if conn:
            await conn.close()


async def get_player_stats(conn, discord_id):
    try:
        # Query to get the stats of the user from ranked_players table by Discord ID
        query = """
            SELECT kills, deaths, matches, elo_rating, elo_duelsx, discord_username, gamename, common_name
            FROM ranked_players
            WHERE discordid = $1
        """
        stats = await conn.fetchrow(query, discord_id)
        return stats

    except Exception as e:
        print(f"Database error: {e}")
        return None


async def get_player_stats_by_name(conn, player_name):
    try:
        # Query to get the stats of the user from ranked_players table by player name
        query = """
            SELECT kills, deaths, matches, elo_rating, elo_duelsx, discord_username, gamename, common_name
            FROM ranked_players
            WHERE common_name ILIKE $1 OR discord_username ILIKE $1 OR gamename ILIKE $1
        """
        stats = await conn.fetchrow(query, player_name)
        return stats

    except Exception as e:
        print(f"Database error: {e}")
        return None


async def send_stats_message(interaction, stats, input_type):
    embed = discord.Embed(
        title=f"Stats ({input_type})",
        color=discord.Color.blue()
    )

    # Check if discord_username, gamename, and common_name exist in stats
    if 'discord_username' in stats:
        embed.add_field(name="Discord Username", value=stats['discord_username'], inline=False)
    if 'gamename' in stats:
        embed.add_field(name="Gamename", value=stats['gamename'], inline=False)
    if 'common_name' in stats:
        embed.add_field(name="Common Name", value=stats['common_name'], inline=False)

    # Add kills, deaths, matches, and elo rating fields
    embed.add_field(name="Kills", value=stats['kills'], inline=True)
    embed.add_field(name="Deaths", value=stats['deaths'], inline=True)
    embed.add_field(name="Matches", value=stats['matches'], inline=True)
    embed.add_field(name="Elo Rating", value=stats['elo_rating'], inline=True)
    embed.add_field(name="Elo Duels", value=stats['elo_duelsx'], inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    
@bot.slash_command(guild_ids=GUILD_IDS, description="Checks registered status based on Discord user or Alias.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def status(interaction: discord.Interaction, player_name: str = None, discord_member: discord.Member = None):
    """
    Retrieves the registered status of a player based on their Discord user or PlayFab ID.

    Parameters:
        player_name (str): Input alias of the player. Can be a common name or Discord username.
        discord_member (discord.Member): Discord member to retrieve the status for.

    Example Usage:
        /status player_name
        /status @discord_member
    """
    await interaction.response.defer()  # Defer the response
    
    if not player_name and not discord_member:
        await interaction.followup.send("No player details provided. Please use the command with a PlayFab ID, Discord mention, or mention a member.", ephemeral=True)
        return
    
    conn = None  # Initialize conn to None before the try block

    try:
        conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)
        common_name, discord_username, retired, elo = None, None, None, None

        # Check if the discord_member parameter is provided
        if discord_member:
            discord_id = discord_member.id
            query = "SELECT common_name, discord_username, retired, elo_duelsx FROM ranked_players WHERE discordid = $1"
            result = await conn.fetchrow(query, discord_id)

            if result:
                common_name = result['common_name']
                discord_username = result['discord_username']
                retired = result['retired']
                elo = int(result['elo_duelsx'])  # Convert ELO to integer
                retirement_status = "Retired" if retired else "Active"
                
                # Prepare the embed message with consistent spacing
                description = f"Common Name: {common_name}\n\nDiscord Username: {discord_username}\n\n{':skull_crossbones:' if retired else ':crossed_swords:'}  Status: {retirement_status}\n\n🏆  ELO: {elo}"
                embed_color = discord.Color.greyple() if retired else discord.Color.green()
            else:
                description = "No player found with the provided Discord member."
                embed_color = discord.Color.red()

            embed_title = "🔍  Account Status (Discord Member)"

        else:
            # Check if the player_name parameter is provided
            if player_name and re.match(r"<@!?(\d+)>", player_name):
                discord_id = re.findall(r'\d+', player_name)[0]
                query = "SELECT common_name, discord_username, retired, elo_duelsx FROM ranked_players WHERE discordid = $1"
                result = await conn.fetchrow(query, int(discord_id))

                if result:
                    common_name = result['common_name']
                    discord_username = result['discord_username']
                    retired = result['retired']
                    elo = int(result['elo_duelsx'])  # Convert ELO to integer
                    retirement_status = "Retired" if retired else "Active"
                    
                    # Prepare the embed message with consistent spacing
                    description = f"Common Name: {common_name}\n\nDiscord Username: {discord_username}\n\n{':skull_crossbones:' if retired else ':crossed_swords:'}  Status: {retirement_status}\n\n🏆  ELO: {elo}"
                    embed_color = discord.Color.greyple() if retired else discord.Color.green()
                else:
                    description = "No player found with the provided Discord member."
                    embed_color = discord.Color.red()

                embed_title = "🔍  Account Status (Discord Member)"

            else:
                # Check if the player_name matches a common name or discord username
                if player_name:
                    query = """
                        SELECT common_name, discord_username, retired, elo_duelsx
                        FROM ranked_players
                        WHERE lower(common_name) = lower($1) OR lower(discord_username) = lower($1)
                    """
                    result = await conn.fetchrow(query, player_name)

                    if result:
                        common_name = result['common_name']
                        discord_username = result['discord_username']
                        retired = result['retired']
                        elo = int(result['elo_duelsx'])  # Convert ELO to integer
                        retirement_status = "Retired" if retired else "Active"
                        
                        # Prepare the embed message with consistent spacing
                        description = f"Common Name: {common_name}\n\nDiscord Username: {discord_username}\n\n{':skull_crossbones:' if retired else ':crossed_swords:'}  Status: {retirement_status}\n\n🏆  ELO: {elo}"
                        embed_color = discord.Color.greyple() if retired else discord.Color.green()
                    else:
                        description = "No player found with the provided Player name."
                        embed_color = discord.Color.red()

                    embed_title = "🔍  Account Status (Player Name)"

        # Prepare the embed message
        embed = discord.Embed(
            title=embed_title,
            description=description,
            color=embed_color
        )

        # Add a shield emoji to the title for uniqueness and visual appeal
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2896/2896363.png")

        # Send the followup message
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)

    finally:
        if conn:
            await conn.close()


@bot.slash_command(guild_ids=GUILD_IDS, description="Links your Discord account for ranked verification.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def register(interaction: discord.Interaction):
    # Connect to the psql database (moved outside the try block)
    conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

    try:
        # Check for existing Discord ID in ranked_players table
        query = "SELECT 1 FROM ranked_players WHERE discordid = $1"
        existing_user = await conn.fetchval(query, interaction.user.id)

        if existing_user:
            # Inform user about already linked account
            if interaction.response.is_done():
                await interaction.followup.send("Your Discord account is already linked for ranked verification. Reactivate your account for ranked matches. Usage: /reactivate. Contact the Monad for persistent issues.", ephemeral=True)
            else:
                await interaction.response.send_message("Your Discord account is already linked for ranked verification. Reactivate your account for ranked matches. Usage: /reactivate. Contact the Monad for persistent issues.", ephemeral=True)
            return  # Exit after checking for existing user

        # Insert the user's information into the database
        query = "INSERT INTO ranked_players (discordid, discord_username) VALUES ($1, $2)"
        await conn.execute(query, interaction.user.id, interaction.user.name)

        # Confirmation message with reminder to set in-game name
        confirmation_message = (
            f"✅ {interaction.user.mention}, your Discord account has been linked for ranked verification. "
            f"You are now eligible to participate in ranked matches! "
            f"**Please set your in-game name using the command `/setname [Your In-Game Name]`**"
        )
        if interaction.response.is_done():
            await interaction.followup.send(confirmation_message, ephemeral=True)
        else:
            await interaction.response.send_message(confirmation_message, ephemeral=True)
        
        # Send an embedded message to the chivstats-audit channel
        audit_embed = discord.Embed(
            title="New Account Registered",
            description=f"A new account has been registered: {interaction.user.mention}",
            color=discord.Color.green()
        )
        audit_embed.set_footer(text=f"User ID: {interaction.user.id}")
        audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel
        audit_channel = bot.get_channel(audit_channel_id)
        if audit_channel:
            await audit_channel.send(embed=audit_embed)

    except Exception as e:
        if interaction.response.is_done():
            await interaction.followup.send("An error occurred while processing your request. Please try again.", ephemeral=True)
        else:
            await interaction.response.send_message("An error occurred while processing your request. Please try again.", ephemeral=True)
        print(f"Database error: {e}")

    finally:
        # Close the database connection (if it was opened)
        if conn:
            await conn.close()




@bot.slash_command(guild_ids=GUILD_IDS, description="Reactivate your account for ranked matches.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def reactivate(interaction: discord.Interaction):
  conn = None
  try:
    # Establish an asynchronous connection
    conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

    # Check if user is already active (retired=FALSE)
    query = "SELECT retired FROM ranked_players WHERE discordid = $1"
    retired_status = await conn.fetchval(query, interaction.user.id)

    if not retired_status:  # User is already active (retired=FALSE)
      await interaction.response.send_message(
          "Your account is already active for ranked matches.", ephemeral=True
      )
      return

    # ... rest of your reactivation logic ... (assuming retired=TRUE indicates inactive)

    # Execute the query asynchronously and fetch the result (assuming retired update)
    result = await conn.fetchrow(
        "UPDATE ranked_players SET retired = FALSE WHERE discordid = $1 RETURNING playfabid, common_name, elo_rating",
        interaction.user.id
    )
    playfabid, common_name, elo_rating = result

    # Find the "Ranked Combatant" role in the guild
    role = discord.utils.get(interaction.guild.roles, name="Ranked Combatant")

    # Role assignment and embed message (formatted)
    if role:
      try:
        await interaction.user.add_roles(role)
        role_message = f"\n✅ You have been re-assigned the '{role.name}' role."
      except Exception as e:
        print(f"Failed to assign role: {e}")
        role_message = f"\n⚠️ Error: Unable to re-add you to the '{role.name}' role."
    else:
      role_message = "\n⚠️ 'Ranked Combatant' role not found in this server."

    embed = discord.Embed(
        title="Reactivation Successful",
        description=f"{interaction.user.mention} ({common_name}), your account has been reactivated for ranked matches!\n\n"
                    f"Duels ELO: {elo_rating}{role_message}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

    # ... rest of your code (audit logging) ...

  except Exception as e:
    await interaction.response.send_message("An error occurred while processing your request. Please try again.", ephemeral=True)
    print(f"Database error: {e}")
  finally:
    if conn is not None:
      await conn.close()



@bot.slash_command(guild_ids=GUILD_IDS, description="Retire your account from ranked matches.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def retire(interaction: discord.Interaction):
    conn = None
    try:
        # Establish an asynchronous connection
        conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

        # Check if the user has already retired
        existing_retired = await conn.fetchval(
            "SELECT retired FROM ranked_players WHERE discordid = $1", 
            interaction.user.id
        )
        if existing_retired:
            # If user is already retired, send error message
            await interaction.response.send_message("Your account is already retired. You can reactivate it by typing `/reactivate`.", ephemeral=True)
            return

        # Execute the query asynchronously and fetch the result
        result = await conn.fetchrow(
            "UPDATE ranked_players SET retired = TRUE WHERE discordid = $1 RETURNING playfabid, common_name, elo_rating", 
            interaction.user.id
        )
        playfabid, common_name, elo_rating = result

        # Find the "Ranked Combatant" role in the guild
        role = discord.utils.get(interaction.guild.roles, name="Ranked Combatant")
        if role:
            try:
                # Remove the role from the user
                await interaction.user.remove_roles(role)
                role_message = "Player removed from the 'Ranked Combatant' role."
            except Exception as e:
                print(f"Failed to remove role: {e}")
                role_message = "Error: Unable to remove player from the 'Ranked Combatant' role."
        else:
            role_message = "Error: The 'Ranked Combatant' role was not found in this server."

        embed = discord.Embed(
            title="Retirement Announcement",
            description=f"{interaction.user.mention} ({common_name}) has retired from ranked matches.\n\nDuels ELO: {elo_rating}\n{role_message}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

        command_name = interaction.command.name
        command_options = " ".join([f"{opt.name}={opt.value}" for opt in interaction.command.options])
        entered_command = f"/{command_name} {command_options}"

        target_guild_id = 1227017798916505780  # ID of the 'Chivalry Unchained' guild
        audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel

        target_guild = bot.get_guild(target_guild_id)
        audit_channel = target_guild.get_channel(audit_channel_id) if target_guild else None

        if audit_channel:
            audit_message = f"Player {common_name} (ID: {interaction.user.id}, PlayFab ID: {playfabid}) has executed: {entered_command}"
            await audit_channel.send(audit_message)

    except Exception as e:
        await interaction.response.send_message("An error occurred while processing your request. Please try again.", ephemeral=True)
        print(f"Database error: {e}")
    finally:
        if conn is not None:
            await conn.close()


@bot.slash_command(guild_ids=GUILD_IDS, description="Set your in-game name.")
@is_channel_named(['chivstats-ranked', 'chivstats-test'])
async def setname(interaction: discord.Interaction, name: str):
    try:
        # Connect to the psql database
        conn = await asyncpg.connect(database=DATABASE, user=USER, password=PASSWORD, host=HOST)

        # Check if the provided name is already in use by another user
        name_check_query = """
            SELECT COUNT(*)
            FROM ranked_players
            WHERE common_name = $1 OR gamename = $1
        """
        name_count = await conn.fetchval(name_check_query, name)

        if name_count > 0:
            # Name is already in use, return an error message
            await interaction.response.send_message("This name is already in use. Please choose a different one.", ephemeral=True)
            return

        # Update the ranked_players table with the provided in-game name
        update_query = """
            UPDATE ranked_players
            SET gamename = $1, common_name = $2
            WHERE discordid = $3
        """
        await conn.execute(update_query, name, name, interaction.user.id)

        # Send confirmation message
        confirmation_message = f"Your in-game name has been updated to: {name}"
        await interaction.response.send_message(confirmation_message, ephemeral=True)

        # Log the command execution in the audit channel
        target_guild_id = 1227017798916505780  # ID of the 'Chivalry Unchained' guild
        audit_channel_id = 1227018572937564170  # ID of the '#chivstats-audit' channel

        target_guild = bot.get_guild(target_guild_id)
        audit_channel = target_guild.get_channel(audit_channel_id) if target_guild else None

        if audit_channel:
            audit_message = f"Player (ID: {interaction.user.id}) has executed: /setname name={name}"
            await audit_channel.send(audit_message)

    except Exception as e:
        print(f"Database error: {e}")
        await interaction.response.send_message("An error occurred while updating your in-game name.", ephemeral=True)

    finally:
        if conn:
            await conn.close()



def setup():
    bot.add_cog(AdminCommands(bot))
    bot.add_cog(LTSCog(bot))
    bot.add_cog(CoinCog(bot))
    bot.add_cog(PrivateServers(bot))


setup()
# Run the Chivalry 2 discord ranked combat bot, maaan
bot.run(TOKEN)
