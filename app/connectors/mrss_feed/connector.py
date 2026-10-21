"""Media RSS (MRSS) Feed connector generating and maintaining valid RSS 2.0 XML with Media namespace."""

import email.utils
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.connectors.base import BaseConnector
from app.storage.minio_client import get_storage_client

MEDIA_NS = "http://search.yahoo.com/mrss/"
ET.register_namespace("media", MEDIA_NS)


class MRSSFeedConnector(BaseConnector):
    """Generates and updates Media RSS 2.0 XML feeds in persistent storage."""

    def __init__(self):
        manifest_path = Path(__file__).parent / "manifest.yaml"
        super().__init__(manifest_path)

    def _get_feed_name(self, destination: dict[str, Any]) -> str:
        return destination.get("instance_config", {}).get("feed_name") or destination.get(
            "feed_name", "default_feed"
        )

    def _get_feed_path(self, feed_name: str) -> str:
        clean_name = "".join(c for c in feed_name if c.isalnum() or c in ("-", "_"))
        return f"feeds/{clean_name}.xml"

    def _load_or_create_tree(
        self, feed_name: str, destination: dict[str, Any]
    ) -> tuple[ET.ElementTree, ET.Element]:
        storage = get_storage_client()
        feed_path = self._get_feed_path(feed_name)
        raw_xml = storage.get_evidence(feed_path)

        if raw_xml:
            try:
                root = ET.fromstring(raw_xml)
                channel = root.find("channel")
                if channel is not None:
                    return ET.ElementTree(root), channel
            except Exception:
                pass

        # Create new base XML
        root = ET.Element("rss", {"version": "2.0"})
        channel = ET.SubElement(root, "channel")

        title_el = ET.SubElement(channel, "title")
        title_el.text = destination.get("name", f"{feed_name} Media Feed")

        link_el = ET.SubElement(channel, "link")
        link_el.text = destination.get("url", f"https://feeds.incubrix.local/{feed_name}")

        desc_el = ET.SubElement(channel, "description")
        desc_el.text = f"Media RSS feed generated for {feed_name}"

        return ET.ElementTree(root), channel

    def validate(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        violations = []
        title = rendition.get("title", "")
        if len(title) > 255:
            violations.append(
                {"field": "title", "rule": "max_chars", "limit": 255, "actual": len(title)}
            )
        return {"ok": len(violations) == 0, "violations": violations}

    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        feed_name = self._get_feed_name(destination)
        tree, channel = self._load_or_create_tree(feed_name, destination)

        guid = idempotency_key or rendition.get("guid") or f"mrss_{int(datetime.now().timestamp())}"

        # Check for existing item with this guid (idempotency)
        existing_item = None
        for item in channel.findall("item"):
            guid_el = item.find("guid")
            if guid_el is not None and guid_el.text == guid:
                existing_item = item
                break

        now_rfc822 = email.utils.format_datetime(datetime.now(UTC))

        if existing_item is not None:
            # Update in-place
            target_item = existing_item
            for child in list(target_item):
                if child.tag != "guid":
                    target_item.remove(child)
        else:
            # Append new item
            target_item = ET.SubElement(channel, "item")
            guid_el = ET.SubElement(target_item, "guid", {"isPermaLink": "false"})
            guid_el.text = guid

        # Set title
        title_el = ET.SubElement(target_item, "title")
        title_el.text = rendition.get("title", "Untitled Feed Item")

        # Set link
        link_el = ET.SubElement(target_item, "link")
        link_el.text = rendition.get("canonical_url") or f"https://content.incubrix.local/{guid}"

        # Set description
        desc_el = ET.SubElement(target_item, "description")
        desc_el.text = rendition.get("body", "")

        # Set pubDate
        pub_el = ET.SubElement(target_item, "pubDate")
        pub_el.text = now_rfc822

        # Media content
        media_url = (
            rendition.get("media_url")
            or (rendition.get("media_urls") and rendition["media_urls"][0])
            or rendition.get("image_url")
        )
        if media_url:
            ET.SubElement(
                target_item,
                f"{{{MEDIA_NS}}}content",
                {
                    "url": media_url,
                    "medium": "image",
                    "type": "image/jpeg",
                },
            )
            media_title = ET.SubElement(target_item, f"{{{MEDIA_NS}}}title")
            media_title.text = rendition.get("title", "")

        # Save XML to storage
        raw_xml = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)
        storage = get_storage_client()
        feed_path = self._get_feed_path(feed_name)
        storage_uri = storage.save_evidence(feed_path, raw_xml, content_type="application/rss+xml")

        items_count = len(channel.findall("item"))

        return {
            "platform_post_id": guid,
            "live_url": storage_uri,
            "status": "published",
            "feed_name": feed_name,
            "items_count": items_count,
        }

    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        feed_name = connection.get("feed_name", "default_feed")
        tree, channel = self._load_or_create_tree(feed_name, connection)

        for item in channel.findall("item"):
            guid_el = item.find("guid")
            if guid_el is not None and guid_el.text == platform_post_id:
                title_el = item.find("title")
                return {
                    "platform_post_id": platform_post_id,
                    "status": "published",
                    "title": title_el.text if title_el is not None else "",
                }

        return {
            "platform_post_id": platform_post_id,
            "status": "deleted",
        }

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        feed_name = connection.get("feed_name", "default_feed")
        tree, channel = self._load_or_create_tree(feed_name, connection)

        removed = False
        for item in list(channel.findall("item")):
            guid_el = item.find("guid")
            if guid_el is not None and guid_el.text == platform_post_id:
                channel.remove(item)
                removed = True

        if removed:
            raw_xml = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)
            storage = get_storage_client()
            feed_path = self._get_feed_path(feed_name)
            storage.save_evidence(feed_path, raw_xml, content_type="application/rss+xml")

        return {
            "platform_post_id": platform_post_id,
            "status": "deleted",
            "removed": removed,
        }

    def live_check(
        self,
        platform_post_id: str,
        destination: dict[str, Any],
    ) -> bool:
        feed_name = self._get_feed_name(destination)
        tree, channel = self._load_or_create_tree(feed_name, destination)
        for item in channel.findall("item"):
            guid_el = item.find("guid")
            if guid_el is not None and guid_el.text == platform_post_id:
                return True
        return False

    def build_assist_pack(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": "mrss_assisted",
            "instructions": "Append item snippet to your external RSS/MRSS feed manager.",
            "item_snippet": {
                "title": rendition.get("title", ""),
                "description": rendition.get("body", ""),
                "link": rendition.get("canonical_url", ""),
            },
        }
