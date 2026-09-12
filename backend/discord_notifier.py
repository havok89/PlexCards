import logging
import threading
from typing import Dict, Any, Optional
from pathlib import Path
import requests
from backend.db import get_setting

logger = logging.getLogger(__name__)

class DiscordNotifier:
    """Service for dispatching rich Discord embeds with card previews."""

    @property
    def webhook_url(self) -> Optional[str]:
        url = get_setting("discord_webhook_url", "").strip()
        return url if url else None

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    @property
    def notify_live_enabled(self) -> bool:
        return get_setting("discord_notify_live_episodes", "true").lower() == "true"

    @property
    def notify_batch_enabled(self) -> bool:
        return get_setting("discord_notify_batch_sync", "true").lower() == "true"

    @property
    def notify_manual_enabled(self) -> bool:
        return get_setting("discord_notify_manual_apply", "false").lower() == "true"

    def _post_payload_async(
        self,
        url: str,
        payload: Dict[str, Any],
        image_path: Optional[Path] = None,
        image_bytes: Optional[bytes] = None
    ):
        """Execute HTTP POST to Discord webhook in a background daemon thread."""
        raw_bytes = image_bytes
        if not raw_bytes and image_path:
            try:
                p = Path(image_path)
                if p.exists():
                    raw_bytes = p.read_bytes()
            except Exception as e:
                logger.warning(f"Failed to read image for Discord webhook: {e}")

        def _run():
            try:
                # Check if target is a direct Discord webhook endpoint
                is_discord_direct = (
                    "discord.com/api/webhooks" in url.lower()
                    or "discordapp.com/api/webhooks" in url.lower()
                )

                if is_discord_direct and raw_bytes:
                    # Discord API v9/v10 expects multipart with files and payload_json
                    files = {
                        "files[0]": ("card.jpg", raw_bytes, "image/jpeg"),
                        "file": ("card.jpg", raw_bytes, "image/jpeg")
                    }
                    payload["attachments"] = [{"id": 0, "filename": "card.jpg"}]
                    if payload.get("embeds") and len(payload["embeds"]) > 0:
                        payload["embeds"][0]["image"] = {"url": "attachment://card.jpg"}
                    import json
                    data = {"payload_json": json.dumps(payload)}
                    resp = requests.post(url, data=data, files=files, timeout=15)
                else:
                    # For custom webhook receivers / proxies / endpoints, always send pure application/json
                    if raw_bytes:
                        import base64
                        b64_str = base64.b64encode(raw_bytes).decode("utf-8")
                        payload["card_image_base64"] = b64_str
                        payload["card_data_uri"] = f"data:image/jpeg;base64,{b64_str}"
                    resp = requests.post(url, json=payload, timeout=10)

                if resp.status_code not in (200, 204):
                    logger.warning(f"Discord webhook failed with HTTP {resp.status_code}: {resp.text[:200]}")
                else:
                    logger.info("✓ Dispatched Discord webhook notification successfully.")
            except Exception as e:
                logger.warning(f"Failed to post to Discord webhook: {e}")

        threading.Thread(target=_run, name="DiscordWebhookNotifier", daemon=True).start()

    def send_test_notification(self, webhook_url: Optional[str] = None) -> Dict[str, Any]:
        """Dispatch a test embed to verify the webhook URL is valid."""
        target_url = webhook_url or self.webhook_url
        if not target_url:
            raise ValueError("No Discord webhook URL configured.")

        payload = {
            "username": "PlexCards",
            "avatar_url": "https://raw.githubusercontent.com/havok89/PlexCards/main/frontend/public/favicon.ico",
            "embeds": [
                {
                    "title": "🔔 PlexCards Webhook Connected",
                    "description": "Discord webhook notifications are configured and working properly!",
                    "color": 0xE5A00D, # Brand gold / amber
                    "fields": [
                        {"name": "Status", "value": "🟢 Connected & Active", "inline": True},
                        {"name": "Platform", "value": "PlexCards v0.8.0", "inline": True}
                    ],
                    "footer": {
                        "text": "PlexCards • Smart Title Card Automation"
                    }
                }
            ]
        }

        try:
            resp = requests.post(target_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                return {"status": "success", "message": "Test notification delivered to Discord successfully!"}
            else:
                return {
                    "status": "error",
                    "message": f"Discord returned HTTP {resp.status_code}: {resp.text[:200]}"
                }
        except Exception as e:
            logger.error(f"Error testing Discord webhook: {e}")
            return {"status": "error", "message": f"Connection error: {str(e)}"}

    def notify_episode_card(
        self,
        show_title: str,
        season_number: int,
        episode_number: int,
        episode_title: str,
        source: str,
        card_image_path_or_url: Optional[str] = None,
        card_image_bytes: Optional[bytes] = None,
        creator: Optional[str] = None,
        set_url: Optional[str] = None,
        library_name: Optional[str] = None,
        is_manual: bool = False,
        is_test: bool = False
    ):
        """Send notification for a single episode card."""
        target_url = self.webhook_url
        if not target_url:
            return

        if is_manual and not self.notify_manual_enabled:
            return
        if not is_manual and not self.notify_live_enabled:
            return

        is_mediux = source == "mediux" or "mediux" in str(source).lower()
        color = 0xE5A00D if is_mediux else 0x06B6D4 # Gold for MediUX, Cyan for Generator
        base_title = "✨ MediUX Title Card Applied" if is_mediux else "🎨 Smart Title Card Generated"
        title = f"🧪 [Simulated] {base_title}" if is_test else base_title
        ep_tag = f"S{season_number:02d}E{episode_number:02d}"

        fields = [
            {"name": "Episode", "value": f"{ep_tag}: *{episode_title}*", "inline": False}
        ]

        if is_mediux:
            src_desc = f"MediUX Set by **{creator}**" if creator else "MediUX Set"
            if set_url:
                src_desc = f"[{src_desc}]({set_url})"
            fields.append({"name": "Source", "value": src_desc, "inline": True})
        else:
            fields.append({"name": "Source", "value": "PlexCards Generator", "inline": True})

        if library_name:
            fields.append({"name": "Library", "value": library_name, "inline": True})

        if is_test:
            footer_text = "PlexCards • Simulation (Test Mode)"
        else:
            footer_text = "PlexCards • Manual Apply" if is_manual else "PlexCards • Live Sync"

        payload = {
            "username": "PlexCards",
            "event": "episode_card_updated",
            "is_test": is_test,
            "show_title": show_title,
            "season_number": season_number,
            "episode_number": episode_number,
            "episode_title": episode_title,
            "source": source,
            "embeds": [
                {
                    "title": f"{title} — {show_title}",
                    "description": f"New title card updated in Plex for **{show_title}**",
                    "color": color,
                    "fields": fields,
                    "footer": {
                        "text": footer_text
                    }
                }
            ]
        }

        image_path = None
        if card_image_path_or_url:
            if card_image_path_or_url.startswith("http://") or card_image_path_or_url.startswith("https://"):
                payload["embeds"][0]["image"] = {"url": card_image_path_or_url}
            else:
                p = Path(card_image_path_or_url)
                if p.exists():
                    image_path = p

        self._post_payload_async(target_url, payload, image_path=image_path, image_bytes=card_image_bytes)

    def notify_batch_cards_grouped(
        self,
        show_title: str,
        season_number: int,
        episodes_count: int,
        ep_range: str,
        source: str,
        creator: Optional[str] = None,
        set_url: Optional[str] = None,
        hero_image_path_or_url: Optional[str] = None,
        hero_image_bytes: Optional[bytes] = None,
        library_name: Optional[str] = None,
        is_manual: bool = False,
        is_test: bool = False
    ):
        """Send a single consolidated notification when multiple cards are synced for a show in a batch."""
        target_url = self.webhook_url
        if not target_url:
            return

        if is_manual and not self.notify_manual_enabled:
            return
        if not is_manual and not self.notify_batch_enabled:
            return

        is_mediux = source == "mediux" or "mediux" in str(source).lower()
        color = 0xE5A00D if is_mediux else 0x10B981 # Gold for MediUX, Emerald for Generator
        base_title = f"✨ {episodes_count} MediUX Cards Synced" if is_mediux else f"🎨 {episodes_count} Title Cards Generated"
        title = f"🧪 [Simulated] {base_title}" if is_test else base_title

        desc = f"Batch synced **{episodes_count} cards** for **{show_title}** (Season {season_number}: `{ep_range}`)."
        if is_mediux and creator:
            desc += f"\nFrom the MediUX set by **{creator}**."

        fields = [
            {"name": "Season Range", "value": f"Season {season_number} ({ep_range})", "inline": True},
            {"name": "Count", "value": f"{episodes_count} cards", "inline": True}
        ]

        if is_mediux and set_url:
            fields.append({"name": "Set Link", "value": f"[View on MediUX]({set_url})", "inline": True})
        if library_name:
            fields.append({"name": "Library", "value": library_name, "inline": True})

        if is_test:
            footer_text = "PlexCards • Batch Simulation (Test Mode)"
        else:
            footer_text = "PlexCards • Manual Apply" if is_manual else "PlexCards • Scheduled Sync Digest"

        payload = {
            "username": "PlexCards",
            "event": "batch_cards_synced",
            "is_test": is_test,
            "show_title": show_title,
            "season_number": season_number,
            "episodes_count": episodes_count,
            "source": source,
            "embeds": [
                {
                    "title": f"{title} — {show_title}",
                    "description": desc,
                    "color": color,
                    "fields": fields,
                    "footer": {
                        "text": footer_text
                    }
                }
            ]
        }

        image_path = None
        if hero_image_path_or_url:
            if hero_image_path_or_url.startswith("http://") or hero_image_path_or_url.startswith("https://"):
                payload["embeds"][0]["image"] = {"url": hero_image_path_or_url}
            else:
                p = Path(hero_image_path_or_url)
                if p.exists():
                    image_path = p

        self._post_payload_async(target_url, payload, image_path=image_path, image_bytes=hero_image_bytes)

discord_notifier = DiscordNotifier()
