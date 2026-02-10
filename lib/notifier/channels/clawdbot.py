"""
ClawdbotChannel - Send notifications via Clawdbot tools/invoke API.
CRITICAL: Direct REST API, NOT through AI session.
"""

import asyncio
import os

# Default gateway URL - can be overridden via CLAWDBOT_GATEWAY_URL env var
DEFAULT_GATEWAY_URL = os.environ.get("CLAWDBOT_GATEWAY_URL", "http://127.0.0.1:18789")

HAS_HTTPX = False
HAS_REQUESTS = False

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    pass

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    pass


class ClawdbotChannel:
    """
    Sends messages via Clawdbot's /tools/invoke endpoint.

    Endpoint: POST /tools/invoke
    Tool: message (action=send)
    """

    def __init__(self, config: dict):
        """
        Args:
            config: {
                'gateway_url': Gateway URL (default from CLAWDBOT_GATEWAY_URL env or localhost),
                'token': 'xxx',
                'default_channel': 'whatsapp',
                'default_to': '+971529111025'
            }
        """
        self.gateway_url = config.get("gateway_url", DEFAULT_GATEWAY_URL).rstrip("/")
        self.token = config.get("token", "")
        self.default_channel = config.get("default_channel", "whatsapp")
        self.default_to = config.get("default_to", "")

    async def send(
        self,
        message: str,
        channel: str = None,
        to: str = None,
        priority: str = "normal",
    ) -> dict:
        """
        Send message via Clawdbot tools/invoke.

        Args:
            message: Message text to send
            channel: Channel name (whatsapp, telegram, etc.)
            to: Recipient identifier
            priority: Message priority (affects formatting)

        Returns:
            {success: bool, message_id?: str, error?: str}
        """
        if not HAS_HTTPX:
            return {"success": False, "error": "httpx not installed"}

        target_channel = channel or self.default_channel
        target_to = to or self.default_to

        if not target_to:
            return {"success": False, "error": "No recipient specified"}

        # Add priority prefix for critical/high
        formatted_message = message
        if priority == "critical":
            formatted_message = f"🚨 URGENT\n\n{message}"
        elif priority == "high":
            formatted_message = f"⚠️ {message}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.gateway_url}/tools/invoke"
                headers = {"Content-Type": "application/json"}
                if self.token:
                    headers["Authorization"] = f"Bearer {self.token}"

                # Use message tool with action=send
                payload = {
                    "tool": "message",
                    "args": {
                        "action": "send",
                        "channel": target_channel,
                        "target": target_to,
                        "message": formatted_message,
                    },
                }

                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return {
                            "success": True,
                            "message_id": data.get("result", {}).get("id"),
                        }
                    return {
                        "success": False,
                        "error": data.get("error", {}).get("message", "Unknown error"),
                    }
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }

        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out"}
        except httpx.ConnectError:
            return {"success": False, "error": "Could not connect to gateway"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_sync(
        self,
        message: str,
        channel: str = None,
        to: str = None,
        priority: str = "normal",
    ) -> dict:
        """
        Synchronous send using requests (fallback) or httpx.
        """
        target_channel = channel or self.default_channel
        target_to = to or self.default_to

        if not target_to:
            return {"success": False, "error": "No recipient specified"}

        # Add priority prefix
        formatted_message = message
        if priority == "critical":
            formatted_message = f"🚨 URGENT\n\n{message}"
        elif priority == "high":
            formatted_message = f"⚠️ {message}"

        url = f"{self.gateway_url}/tools/invoke"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        payload = {
            "tool": "message",
            "args": {
                "action": "send",
                "channel": target_channel,
                "target": target_to,
                "message": formatted_message,
            },
        }

        # Try requests first (more common), then httpx
        if HAS_REQUESTS:
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return {
                            "success": True,
                            "message_id": data.get("result", {}).get("id"),
                        }
                    return {
                        "success": False,
                        "error": data.get("error", {}).get("message", "Unknown"),
                    }
                return {"success": False, "error": f"HTTP {response.status_code}"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        elif HAS_HTTPX:
            return asyncio.run(self.send(message, channel, to, priority))
        else:
            return {
                "success": False,
                "error": "No HTTP client available (install requests or httpx)",
            }
