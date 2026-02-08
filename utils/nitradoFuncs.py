from config import Config
import aiohttp
import json
import requests
import sqlite3

class NitradoFunctions():
    deviceban = sqlite3.connect("db/deviceidban.db")
    dbans = deviceban.cursor()
    stats = sqlite3.connect("db/stats.db")
    st = stats.cursor()

    async def getSettings(self, id):
        headers = {"Authorization": f"Bearer {Config.NITRADO_TOKEN}"}
        async with aiohttp.ClientSession() as ses:
            async with ses.get(f"https://api.nitrado.net/services/{id}/gameservers", headers=headers) as e:
                return await e.content.read()

    async def postSetting(self, category, key, value, id):
        headers = {"Authorization": f"Bearer {Config.NITRADO_TOKEN}"}
        data = {
            "category": category,
            "key": key,
            "value": value,
        }
        response = requests.post(
            f"https://api.nitrado.net/services/{id}/gameservers/settings",
            headers=headers,
            data=data
        )
        return response.status_code

    async def banPlayer(self, id, username, ban):
        data = await self.getSettings(id)
        if not data:
            return "Something went wrong"

        banData = json.loads(data)['data']['gameserver']['settings']['general']['bans']
        currentBans = banData.split('\r\n')

        if ban.name == 'Add':
            if username in currentBans:
                return "User already banned"

            self.st.execute("SELECT device_id FROM stats WHERE user = ?", (username,))
            result = self.st.fetchone()
            device_id = result[0] if result else None

            banData += f'\r\n{username}'
            value = banData.replace("\\n", '\n').replace("\\r", '\r')
            resp = await self.postSetting('general', 'bans', value, id)

            if resp == 200:
                if device_id:
                    self.dbans.execute(
                        "INSERT OR REPLACE INTO deviceid_bans (username, device_id) VALUES (?, ?)",
                        (username, device_id)
                    )
                    msg = f"Successfully added {username} (Device ID {device_id}) to the ban list"
                else:
                    self.dbans.execute(
                        "INSERT OR REPLACE INTO deviceid_bans (username, device_id) VALUES (?, NULL)",
                        (username,)
                    )
                    msg = f"Successfully added {username} to the ban list. Note: No device ID associated with the player."
                print(msg)
                return msg
            else:
                msg = f"Something went wrong when trying to ban {username}. Try again in a few moments."
                print(msg)
                return msg

        if ban.name == 'Remove':
            if username not in currentBans:
                print("User not banned")
                return "User not banned"

            banData = banData.replace(f'\r\n{username}', '')
            value = banData.replace("\\n", '\n').replace("\\r", '\r')
            resp = await self.postSetting('general', 'bans', value, id)

            if resp == 200:
                self.dbans.execute("DELETE FROM deviceid_bans WHERE username = ?", (username,))
                msg = f"Successfully removed {username} from the ban list"
                print(msg)
                return msg
            else:
                msg = f"Something went wrong when trying to unban {username}. Try again in a few moments."
                print(msg)
                return msg

    async def Priority(self, id, username, priority):
        data = await self.getSettings(id)
        print(data)
        if not data:
            return "Something went wrong"

        print("Passed")
        priorityData = json.loads(data)['data']['gameserver']['settings']['general']['priority']
        currentPriority = priorityData.split('\r\n')

        if priority.name == 'Add':
            print(currentPriority)
            if str(username) in currentPriority:
                return "User already priority"

            print(username)
            priorityData += f'\r\n{username}'
            value = priorityData.replace("\\n", '\n').replace("\\r", '\r')
            resp = await self.postSetting('general', 'priority', value, id)

            if resp == 200:
                msg = f"Successfully added {username} to the priority list"
                print(msg)
                return msg
            else:
                msg = f"Something went wrong when trying to priority {username}. Try again in a few moments."
                print(msg)
                return msg

        if priority.name == 'Remove':
            if username not in currentPriority:
                print("User not priority")
                return "User not priority"

            priorityData = priorityData.replace(f'\r\n{username}', '')
            value = priorityData.replace("\\n", '\n').replace("\\r", '\r')
            resp = await self.postSetting('general', 'priority', value, id)

            if resp == 200:
                msg = f"Successfully removed {username} from the priority list"
                print(msg)
                return msg
            else:
                msg = f"Something went wrong when trying to unpriority {username}. Try again in a few moments."
                print(msg)
                return msg