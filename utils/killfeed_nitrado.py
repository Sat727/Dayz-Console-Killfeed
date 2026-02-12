"""
Nitrado API utilities for fetching server logs.
"""
import aiohttp
import aiofiles
import logging
import os
from os import path
from config import Config
from utils.nitradoFuncs import NitradoFunctions

Nitrado = NitradoFunctions()

logger = logging.getLogger(__name__)



async def fetch_server_log(server_id: int, server_maps: dict = None) -> bool:
    """
    Download the log file for a given Nitrado server.
    
    Args:
        server_id: The Nitrado server ID
        server_maps: Dict to store detected map info
    
    Returns:
        bool: True if log was successfully fetched, False otherwise
    """
    if server_maps is None:
        server_maps = {}
    
    logger.info(f"[{server_id}] Initiating log download")
    
    headers = {"Authorization": f"Bearer {Config.NITRADO_TOKEN}"}
    
    async with aiohttp.ClientSession() as session:
        try:
            # Fetch server info
            server_info = await session.get(
                f"https://api.nitrado.net/services/{server_id}/gameservers",
                headers=headers
            )
            if server_info.status != 200:
                logger.warning(f"[{server_id}] Failed to fetch server info ({server_info.status})")
                return False
            
            details = await server_info.json()
            username = details["data"]["gameserver"]["username"]
            game_type = details["data"]["gameserver"]["game"].lower()
            
            # Determine map from server name
            current_map = await Nitrado.getMapFromSettings(server_id)
            
            if server_maps is not None:
                server_maps[server_id] = current_map
            logger.info(f"[{server_id}] Detected map: {current_map}")
            
            # Determine game type and config path
            if game_type == "dayzps":
                relative_path = "dayzps/config/DayZServer_PS4_x64.ADM"
            elif game_type == "dayzxb":
                relative_path = "dayzxb/config/DayZServer_X1_x64.ADM"
            else:
                logger.error(f"[{server_id}] Unsupported game type: {game_type}")
                return False
            
            # List directory to find most recent .ADM file
            config_dir = f"/games/{username}/noftp/{'/'.join(relative_path.split('/')[:-1])}"
            list_endpoint = f"https://api.nitrado.net/services/{server_id}/gameservers/file_server/list?dir={config_dir}"
            list_response = await session.get(list_endpoint, headers=headers)
            
            if list_response.status != 200:
                logger.error(f"[{server_id}] Failed to list directory ({list_response.status})")
                return False
            
            list_data = await list_response.json()
            adm_files = [entry for entry in list_data["data"]["entries"] 
                        if entry["type"] == "file" and entry["name"].endswith(".ADM")]
            
            if not adm_files:
                logger.error(f"[{server_id}] No .ADM files found in {config_dir}")
                return False
            
            most_recent_file = max(adm_files, key=lambda x: x["modified_at"])
            file_path = most_recent_file["path"]
            
            # Get download token
            download_endpoint = f"https://api.nitrado.net/services/{server_id}/gameservers/file_server/download?file={file_path}"
            token_response = await session.get(download_endpoint, headers=headers)
            
            if token_response.status != 200:
                logger.error(f"[{server_id}] Failed to retrieve download token ({token_response.status})")
                return False
            
            token_data = await token_response.json()
            download_url = token_data["data"]["token"]["url"]
            
            # Download the actual file
            file_response = await session.get(download_url, headers=headers)
            if file_response.status != 200:
                logger.error(f"[{server_id}] Log file download failed ({file_response.status})")
                return False
            
            # Save to local file
            local_fp = path.abspath(path.join(path.dirname(__file__), "..", "files", f"{server_id}.ADM"))
            os.makedirs(os.path.dirname(local_fp), exist_ok=True)
            
            async with aiofiles.open(local_fp, mode="wb+") as f:
                await f.write(await file_response.read())
            
            logger.info(f"[{server_id}] Log download complete")
            return True
        
        except Exception as e:
            logger.exception(f"[{server_id}] Exception during log fetch: {e}")
            # Set default map on error
            if server_maps is not None and server_id not in server_maps:
                server_maps[server_id] = "chernarus"
            return False


def get_map_url(server_map: str = "chernarus") -> str:
    """
    Get the DayZ map URL for a given map.
    
    Args:
        server_map: Name of the map (chernarus, livonia, sahkal)
    
    Returns:
        str: Base URL for the map
    """
    map_urls = {
        "chernarus": "https://dayz.ginfo.gg/chernarusplus/#location=",
        "livonia": "https://dayz.ginfo.gg/livonia/#location=",
        "sahkal": "https://dayz.ginfo.gg/sahkal/#location=",
    }
    return map_urls.get(server_map.lower(), "https://dayz.ginfo.gg/chernarusplus/#location=")


async def fetch_server_rpt_log(server_id: int) -> bool:
    """
    Download the RPT (game script log) file for a given Nitrado server.
    RPT files contain device ID and UID information for alt account detection.
    
    Args:
        server_id: The Nitrado server ID
    
    Returns:
        bool: True if RPT log was successfully fetched, False otherwise
    """
    logger.info(f"[{server_id}] Initiating RPT log download")
    
    headers = {"Authorization": f"Bearer {Config.NITRADO_TOKEN}"}
    
    async with aiohttp.ClientSession() as session:
        try:
            # Fetch server info
            server_info = await session.get(
                f"https://api.nitrado.net/services/{server_id}/gameservers",
                headers=headers
            )
            if server_info.status != 200:
                logger.warning(f"[{server_id}] Failed to fetch server info for RPT ({server_info.status})")
                return False
            
            details = await server_info.json()
            username = details["data"]["gameserver"]["username"]
            game_type = details["data"]["gameserver"]["game"].lower()
            
            # Determine path based on game type
            if game_type == "dayzps":
                rpt_dir = f"/games/{username}/noftp/dayzps/config"
            elif game_type == "dayzxb":
                rpt_dir = f"/games/{username}/noftp/dayzxb/config"
            else:
                logger.error(f"[{server_id}] Unsupported game type for RPT: {game_type}")
                return False
            
            # List directory to find most recent .RPT file
            list_endpoint = f"https://api.nitrado.net/services/{server_id}/gameservers/file_server/list?dir={rpt_dir}"
            list_response = await session.get(list_endpoint, headers=headers)
            
            if list_response.status != 200:
                logger.warning(f"[{server_id}] Failed to list RPT directory ({list_response.status})")
                return False
            
            list_data = await list_response.json()
            rpt_files = [entry for entry in list_data["data"]["entries"] 
                        if entry["type"] == "file" and entry["name"].endswith(".RPT")]
            
            if not rpt_files:
                logger.warning(f"[{server_id}] No .RPT files found in {rpt_dir}")
                return False
            
            # Get most recent RPT file by modified time
            most_recent_file = max(rpt_files, key=lambda x: x["modified_at"])
            file_path = most_recent_file["path"]
            
            logger.info(f"[{server_id}] Found RPT file: {most_recent_file['name']}")
            
            # Get download token
            download_endpoint = f"https://api.nitrado.net/services/{server_id}/gameservers/file_server/download?file={file_path}"
            token_response = await session.get(download_endpoint, headers=headers)
            
            if token_response.status != 200:
                logger.error(f"[{server_id}] Failed to retrieve RPT download token ({token_response.status})")
                return False
            
            token_data = await token_response.json()
            download_url = token_data["data"]["token"]["url"]
            
            # Download the actual file
            file_response = await session.get(download_url, headers=headers)
            if file_response.status != 200:
                logger.error(f"[{server_id}] RPT file download failed ({file_response.status})")
                return False
            
            # Save to local file
            local_fp = path.abspath(path.join(path.dirname(__file__), "..", "files", f"{server_id}.RPT"))
            os.makedirs(os.path.dirname(local_fp), exist_ok=True)
            
            async with aiofiles.open(local_fp, mode="wb+") as f:
                await f.write(await file_response.read())
            
            logger.info(f"[{server_id}] RPT log download complete: {local_fp}")
            return True
        
        except Exception as e:
            logger.exception(f"[{server_id}] Exception during RPT log fetch: {e}")
            return False


def get_map_url(server_map: str = "chernarus") -> str:
    """
    Get the DayZ map URL for a given map.
    
    Args:
        server_map: Name of the map (chernarus, livonia, sahkal)
    
    Returns:
        str: Base URL for the map
    """
    map_urls = {
        "chernarus": "https://dayz.ginfo.gg/chernarusplus/#location=",
        "livonia": "https://dayz.ginfo.gg/livonia/#location=",
        "sahkal": "https://dayz.ginfo.gg/sahkal/#location=",
    }
    return map_urls.get(server_map.lower(), "https://dayz.ginfo.gg/chernarusplus/#location=") # Get the given map URL or default to Chernarus


def can_use_locations(server_map: str = "chernarus") -> bool:
    """
    Check if the given map supports location lookup.
    Currently only Chernarus supports location data.
    
    Args:
        server_map: Name of the map
    
    Returns:
        bool: True if locations are supported
    """
    return server_map.lower() == "chernarus"




